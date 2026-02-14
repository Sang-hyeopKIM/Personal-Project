"""항공권 특가 알리미 - 데이터 모델"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Passenger:
    """탑승객 정보"""
    adults: int = 2
    children: int = 2  # 만 2~11세
    infants: int = 0   # 만 2세 미만

    @property
    def total(self) -> int:
        return self.adults + self.children + self.infants


@dataclass
class SearchRoute:
    """검색 노선 정보"""
    origin: str              # 출발 공항 코드 (예: ICN)
    destination: str         # 도착 공항 코드 (예: NRT, HND, DAD, HAN, SGN)
    destination_name: str    # 도착지 한글명 (예: 도쿄 나리타)


@dataclass
class SearchPeriod:
    """검색 기간 설정"""
    departure_start: date    # 출발일 검색 시작
    departure_end: date      # 출발일 검색 끝
    min_stay_days: int = 3   # 최소 체류일
    max_stay_days: int = 7   # 최대 체류일


@dataclass
class FlightSegment:
    """개별 항공편 구간 정보"""
    carrier: str             # 항공사 코드
    carrier_name: str        # 항공사명
    flight_number: str       # 편명
    departure_airport: str   # 출발 공항
    arrival_airport: str     # 도착 공항
    departure_time: str      # 출발 시각
    arrival_time: str        # 도착 시각
    duration: str            # 비행 시간 (ISO 8601)
    stops: int = 0           # 경유 횟수


@dataclass
class FlightOffer:
    """항공권 검색 결과"""
    origin: str
    destination: str
    destination_name: str
    departure_date: str
    return_date: str
    total_price: float
    currency: str
    price_per_person: float
    outbound_segments: list[FlightSegment] = field(default_factory=list)
    return_segments: list[FlightSegment] = field(default_factory=list)
    booking_class: str = ""
    seats_remaining: Optional[int] = None
    checked_at: datetime = field(default_factory=datetime.now)

    @property
    def is_direct(self) -> bool:
        return (len(self.outbound_segments) == 1 and
                len(self.return_segments) == 1)

    @property
    def stay_days(self) -> int:
        dep = date.fromisoformat(self.departure_date)
        ret = date.fromisoformat(self.return_date)
        return (ret - dep).days

    def summary(self) -> str:
        direct_label = "직항" if self.is_direct else f"경유({len(self.outbound_segments)}편)"
        out_carrier = self.outbound_segments[0].carrier_name if self.outbound_segments else "?"
        return (
            f"[{self.destination_name}] {self.departure_date} ~ {self.return_date} "
            f"({self.stay_days}박) | {out_carrier} {direct_label} | "
            f"총 {self.total_price:,.0f} {self.currency} "
            f"(1인 {self.price_per_person:,.0f} {self.currency})"
        )


@dataclass
class PriceAlert:
    """가격 알림 기준"""
    route: SearchRoute
    threshold_total: float      # 4인 총액 기준 알림 가격
    threshold_per_person: float  # 1인 기준 알림 가격
    currency: str = "KRW"


@dataclass
class PriceRecord:
    """가격 이력 레코드"""
    origin: str
    destination: str
    departure_date: str
    return_date: str
    price: float
    currency: str
    checked_at: str
    carrier: str = ""
    is_direct: bool = False
