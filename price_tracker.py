"""항공권 특가 알리미 - 가격 이력 추적 모듈

SQLite를 사용하여 검색 결과를 저장하고 가격 추이를 추적합니다.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from models import FlightOffer, PriceRecord

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "price_history.db"


class PriceTracker:
    """가격 이력 추적 및 분석"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """데이터베이스 테이블을 초기화합니다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    carrier TEXT,
                    is_direct INTEGER,
                    checked_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_route_date
                ON price_history (origin, destination, departure_date, return_date)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lowest_prices (
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    lowest_price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    found_at TEXT NOT NULL,
                    PRIMARY KEY (origin, destination, departure_date, return_date)
                )
            """)
        logger.info("가격 이력 DB 초기화 완료: %s", self.db_path)

    def save_offers(self, offers: list[FlightOffer]):
        """검색 결과를 이력에 저장합니다."""
        if not offers:
            return

        now = datetime.now().isoformat()
        records = []
        for offer in offers:
            carrier = ""
            if offer.outbound_segments:
                carrier = offer.outbound_segments[0].carrier_name
            records.append((
                offer.origin,
                offer.destination,
                offer.departure_date,
                offer.return_date,
                offer.total_price,
                offer.currency,
                carrier,
                1 if offer.is_direct else 0,
                now,
            ))

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO price_history
                (origin, destination, departure_date, return_date,
                 price, currency, carrier, is_direct, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)

            # 최저가 갱신
            for offer in offers:
                carrier = ""
                if offer.outbound_segments:
                    carrier = offer.outbound_segments[0].carrier_name
                conn.execute("""
                    INSERT INTO lowest_prices
                    (origin, destination, departure_date, return_date,
                     lowest_price, currency, found_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (origin, destination, departure_date, return_date)
                    DO UPDATE SET
                        lowest_price = MIN(excluded.lowest_price, lowest_prices.lowest_price),
                        found_at = CASE
                            WHEN excluded.lowest_price < lowest_prices.lowest_price
                            THEN excluded.found_at
                            ELSE lowest_prices.found_at
                        END
                """, (
                    offer.origin, offer.destination,
                    offer.departure_date, offer.return_date,
                    offer.total_price, offer.currency, now,
                ))

        logger.info("%d건의 가격 정보 저장 완료", len(records))

    def get_lowest_price(
        self, origin: str, destination: str,
        departure_date: str = "", return_date: str = "",
    ) -> float | None:
        """특정 노선/날짜의 역대 최저가를 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            if departure_date and return_date:
                row = conn.execute("""
                    SELECT lowest_price FROM lowest_prices
                    WHERE origin = ? AND destination = ?
                      AND departure_date = ? AND return_date = ?
                """, (origin, destination, departure_date, return_date)).fetchone()
            else:
                row = conn.execute("""
                    SELECT MIN(lowest_price) FROM lowest_prices
                    WHERE origin = ? AND destination = ?
                """, (origin, destination)).fetchone()

            return row[0] if row and row[0] is not None else None

    def get_price_history(
        self, origin: str, destination: str, limit: int = 50
    ) -> list[PriceRecord]:
        """특정 노선의 가격 이력을 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT origin, destination, departure_date, return_date,
                       price, currency, checked_at, carrier, is_direct
                FROM price_history
                WHERE origin = ? AND destination = ?
                ORDER BY checked_at DESC
                LIMIT ?
            """, (origin, destination, limit)).fetchall()

        return [
            PriceRecord(
                origin=r[0], destination=r[1],
                departure_date=r[2], return_date=r[3],
                price=r[4], currency=r[5],
                checked_at=r[6], carrier=r[7],
                is_direct=bool(r[8]),
            )
            for r in rows
        ]

    def get_best_deals(
        self, origin: str, destination: str, top_n: int = 10
    ) -> list[PriceRecord]:
        """특정 노선의 최저가 Top N을 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT origin, destination, departure_date, return_date,
                       lowest_price, currency, found_at
                FROM lowest_prices
                WHERE origin = ? AND destination = ?
                ORDER BY lowest_price ASC
                LIMIT ?
            """, (origin, destination, top_n)).fetchall()

        return [
            PriceRecord(
                origin=r[0], destination=r[1],
                departure_date=r[2], return_date=r[3],
                price=r[4], currency=r[5],
                checked_at=r[6],
            )
            for r in rows
        ]

    def is_new_low(self, offer: FlightOffer) -> bool:
        """현재 가격이 역대 최저가인지 확인합니다."""
        prev = self.get_lowest_price(
            offer.origin, offer.destination,
            offer.departure_date, offer.return_date,
        )
        if prev is None:
            return True
        return offer.total_price < prev

    def get_stats(self, origin: str, destination: str) -> dict:
        """특정 노선의 가격 통계를 반환합니다."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT MIN(price), MAX(price), AVG(price), COUNT(*)
                FROM price_history
                WHERE origin = ? AND destination = ?
            """, (origin, destination)).fetchone()

        if not row or row[3] == 0:
            return {}

        return {
            "min_price": row[0],
            "max_price": row[1],
            "avg_price": round(row[2]),
            "total_records": row[3],
        }

    def get_price_trend(
        self, origin: str, destination: str, limit: int = 200
    ) -> list[dict]:
        """노선별 가격 추이 데이터를 조회합니다 (차트용)."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT checked_at, MIN(price) as min_price,
                       AVG(price) as avg_price, COUNT(*) as cnt
                FROM price_history
                WHERE origin = ? AND destination = ?
                GROUP BY date(checked_at)
                ORDER BY checked_at ASC
                LIMIT ?
            """, (origin, destination, limit)).fetchall()

        return [
            {
                "date": r[0][:10],
                "min_price": r[1],
                "avg_price": round(r[2]),
                "count": r[3],
            }
            for r in rows
        ]

    def get_all_routes(self) -> list[dict]:
        """DB에 저장된 모든 노선 목록을 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT DISTINCT origin, destination
                FROM price_history
                ORDER BY destination
            """).fetchall()
        return [{"origin": r[0], "destination": r[1]} for r in rows]

    def get_recent_searches(self, limit: int = 50) -> list[dict]:
        """최근 검색 결과를 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT origin, destination, departure_date, return_date,
                       price, currency, carrier, is_direct, checked_at
                FROM price_history
                ORDER BY checked_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return [
            {
                "origin": r[0],
                "destination": r[1],
                "departure_date": r[2],
                "return_date": r[3],
                "price": r[4],
                "currency": r[5],
                "carrier": r[6] or "-",
                "is_direct": bool(r[7]),
                "checked_at": r[8],
            }
            for r in rows
        ]
