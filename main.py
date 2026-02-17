#!/usr/bin/env python3
"""항공권 특가 알리미 - 메인 실행 파일

사용법:
    python main.py                  # 1회 검색 (설정된 데이터 소스 사용)
    python main.py --source kiwi    # Kiwi API로 검색
    python main.py --source amadeus # Amadeus API로 검색
    python main.py --links          # 검색 링크만 생성 (API 호출 없음)
    python main.py --schedule       # 주기적 자동 검색
    python main.py --best-deals     # 최저가 목록 조회
    python main.py --dashboard      # 웹 대시보드 실행
"""

import argparse
import logging
import sys
import time
from datetime import date
from pathlib import Path

import schedule as schedule_lib
import yaml

from models import Passenger, PriceAlert, SearchPeriod, SearchRoute
from notifier import ConsoleNotifier, EmailNotifier, TelegramNotifier
from price_tracker import PriceTracker
from search_links import generate_all_links

CONFIG_PATH = Path(__file__).parent / "config.yaml"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            Path(__file__).parent / "flight_alert.log", encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)


def load_config(path: Path = CONFIG_PATH) -> dict:
    """설정 파일을 로드합니다."""
    if not path.exists():
        logger.error("설정 파일이 없습니다: %s", path)
        logger.info("config.example.yaml을 복사하여 config.yaml을 만들어주세요.")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_routes(config: dict) -> list[SearchRoute]:
    return [
        SearchRoute(
            origin=r["origin"],
            destination=r["destination"],
            destination_name=r["name"],
        )
        for r in config.get("routes", [])
    ]


def build_periods(config: dict) -> list[SearchPeriod]:
    return [
        SearchPeriod(
            departure_start=date.fromisoformat(p["departure_start"]),
            departure_end=date.fromisoformat(p["departure_end"]),
            min_stay_days=p.get("min_stay_days", 3),
            max_stay_days=p.get("max_stay_days", 7),
        )
        for p in config.get("periods", [])
    ]


def build_passengers(config: dict) -> Passenger:
    return Passenger(
        adults=config.get("passengers", {}).get("adults", 2),
        children=config.get("passengers", {}).get("children", 2),
        infants=config.get("passengers", {}).get("infants", 0),
    )


def build_alerts(config: dict, routes: list[SearchRoute]) -> list[PriceAlert]:
    alerts_cfg = config.get("alerts", {})
    alerts = []
    for route in routes:
        dest_cfg = alerts_cfg.get(route.destination, alerts_cfg.get("default", {}))
        alerts.append(PriceAlert(
            route=route,
            threshold_total=dest_cfg.get("threshold_total", 2_000_000),
            threshold_per_person=dest_cfg.get("threshold_per_person", 500_000),
            currency=dest_cfg.get("currency", "KRW"),
        ))
    return alerts


def build_notifiers(config: dict) -> list:
    notifiers = [ConsoleNotifier()]
    notifier_cfg = config.get("notifications", {})

    email_cfg = notifier_cfg.get("email", {})
    if email_cfg.get("enabled"):
        notifiers.append(EmailNotifier(
            smtp_host=email_cfg["smtp_host"],
            smtp_port=email_cfg["smtp_port"],
            username=email_cfg["username"],
            password=email_cfg["password"],
            sender=email_cfg["sender"],
            recipients=email_cfg["recipients"],
            use_tls=email_cfg.get("use_tls", True),
        ))
        logger.info("이메일 알림 활성화")

    telegram_cfg = notifier_cfg.get("telegram", {})
    if telegram_cfg.get("enabled"):
        notifiers.append(TelegramNotifier(
            bot_token=telegram_cfg["bot_token"],
            chat_id=str(telegram_cfg["chat_id"]),
        ))
        logger.info("텔레그램 알림 활성화")

    return notifiers


def create_checker(config: dict, source: str):
    """설정된 데이터 소스에 맞는 checker를 생성합니다."""
    if source == "kiwi":
        from kiwi_checker import KiwiChecker
        kiwi_cfg = config.get("kiwi_api", {})
        api_key = kiwi_cfg.get("api_key", "")
        if not api_key or api_key.startswith("YOUR_"):
            logger.error("Kiwi API 키가 설정되지 않았습니다. config.yaml의 kiwi_api.api_key를 확인하세요.")
            sys.exit(1)
        return KiwiChecker(api_key=api_key)
    else:
        from flight_checker import FlightChecker
        api_cfg = config.get("amadeus_api", {})
        api_key = api_cfg.get("api_key", "")
        if not api_key or api_key.startswith("YOUR_"):
            logger.error("Amadeus API 키가 설정되지 않았습니다. config.yaml의 amadeus_api를 확인하세요.")
            sys.exit(1)
        return FlightChecker(
            api_key=api_key,
            api_secret=api_cfg["api_secret"],
            test_mode=api_cfg.get("test_mode", True),
        )


def run_search(config: dict, source: str = "amadeus"):
    """1회 검색을 실행합니다."""
    checker = create_checker(config, source)
    passengers = build_passengers(config)
    routes = build_routes(config)
    periods = build_periods(config)
    alerts = build_alerts(config, routes)
    notifiers = build_notifiers(config)
    tracker = PriceTracker()

    search_cfg = config.get("search_options", {})
    nonstop_only = search_cfg.get("nonstop_only", False)
    sample_interval = search_cfg.get("sample_interval_days", 3)
    max_results = search_cfg.get("max_results_per_search", 3)

    logger.info(
        "검색 시작 [%s]: %d개 노선, %d개 기간, 탑승객 %d명 (성인%d 아동%d)",
        source.upper(), len(routes), len(periods), passengers.total,
        passengers.adults, passengers.children,
    )

    alert_map = {a.route.destination: a for a in alerts}

    for route in routes:
        for period in periods:
            logger.info(
                "--- %s → %s (%s ~ %s) 검색 중 ---",
                route.origin, route.destination_name,
                period.departure_start, period.departure_end,
            )

            offers = checker.search_period(
                route=route,
                period=period,
                passengers=passengers,
                max_results_per_search=max_results,
                nonstop_only=nonstop_only,
                sample_interval_days=sample_interval,
            )

            if not offers:
                logger.info("검색 결과 없음")
                continue

            tracker.save_offers(offers)

            alert = alert_map.get(route.destination)
            cheap_offers = []
            has_new_low = False

            for offer in offers:
                is_cheap = (
                    (alert and offer.total_price <= alert.threshold_total) or
                    (alert and offer.price_per_person <= alert.threshold_per_person)
                )
                if is_cheap:
                    cheap_offers.append(offer)
                    if tracker.is_new_low(offer):
                        has_new_low = True

            if cheap_offers:
                logger.info(
                    "특가 %d건 발견! (역대 최저가: %s)",
                    len(cheap_offers), "예" if has_new_low else "아니오",
                )
                for notifier in notifiers:
                    notifier.send_flight_alert(cheap_offers, has_new_low)
            else:
                top3 = offers[:3]
                logger.info("특가 기준 미달, 최저가 Top 3:")
                for offer in top3:
                    logger.info("  %s", offer.summary())

    # 통계 출력
    print("\n📊 노선별 가격 통계:")
    for route in routes:
        stats = tracker.get_stats(route.origin, route.destination)
        if stats:
            print(
                f"  {route.destination_name}: "
                f"최저 {stats['min_price']:,.0f} / "
                f"평균 {stats['avg_price']:,.0f} / "
                f"최고 {stats['max_price']:,.0f} KRW "
                f"(총 {stats['total_records']}건)"
            )


def show_links(config: dict):
    """검색 링크를 생성하여 출력합니다."""
    routes = build_routes(config)
    periods = build_periods(config)
    passengers = build_passengers(config)
    sample_interval = config.get("search_options", {}).get("sample_interval_days", 7)

    output = generate_all_links(routes, periods, passengers, sample_interval)
    print(output)


def show_best_deals(config: dict):
    """수집된 최저가 목록을 표시합니다."""
    routes = build_routes(config)
    tracker = PriceTracker()

    print("\n🏆 노선별 최저가 Top 10:")
    print("=" * 70)

    for route in routes:
        deals = tracker.get_best_deals(route.origin, route.destination, top_n=10)
        if not deals:
            print(f"\n  {route.destination_name}: 데이터 없음")
            continue

        print(f"\n  📍 {route.destination_name} ({route.origin}→{route.destination})")
        for i, deal in enumerate(deals, 1):
            print(
                f"    #{i:2d} {deal.departure_date} ~ {deal.return_date} | "
                f"{deal.price:>12,.0f} {deal.currency} | "
                f"조회: {deal.checked_at[:10]}"
            )

    print(f"\n{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description="항공권 특가 알리미 - 동남아/일본 항공권 가격 모니터링"
    )
    parser.add_argument(
        "--source", choices=["amadeus", "kiwi"], default="amadeus",
        help="데이터 소스 선택 (기본: amadeus)",
    )
    parser.add_argument(
        "--links", action="store_true",
        help="검색 링크 생성 (API 호출 없이 네이버/구글/스카이스캐너 링크 출력)",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="주기적 자동 검색 모드",
    )
    parser.add_argument(
        "--best-deals", action="store_true",
        help="수집된 최저가 목록 조회",
    )
    parser.add_argument(
        "--dashboard", action="store_true",
        help="웹 대시보드 실행 (기본 포트: 5000)",
    )
    parser.add_argument(
        "--port", type=int, default=5000,
        help="대시보드 포트 번호 (기본: 5000)",
    )
    parser.add_argument(
        "--config", type=str, default=str(CONFIG_PATH),
        help="설정 파일 경로 (기본: config.yaml)",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))

    if args.dashboard:
        from dashboard import run_dashboard
        run_dashboard(port=args.port)
        return

    if args.links:
        show_links(config)
        return

    if args.best_deals:
        show_best_deals(config)
        return

    if args.schedule:
        interval = config.get("schedule", {}).get("interval_hours", 6)
        logger.info("자동 검색 모드 시작 (간격: %d시간)", interval)
        run_search(config, args.source)
        schedule_lib.every(interval).hours.do(run_search, config, args.source)
        try:
            while True:
                schedule_lib.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("자동 검색 종료")
    else:
        run_search(config, args.source)


if __name__ == "__main__":
    main()
