"""항공권 특가 알리미 - 항공권 가격 조회 모듈

Amadeus API를 사용하여 항공권 가격을 조회합니다.
무료 티어: 월 500회 API 호출 가능
가입: https://developers.amadeus.com/
"""

import logging
from datetime import date, timedelta
from itertools import product as iter_product

from amadeus import Client, ResponseError

from models import (
    FlightOffer,
    FlightSegment,
    Passenger,
    SearchPeriod,
    SearchRoute,
)

logger = logging.getLogger(__name__)

# 주요 항공사 코드 → 한글명 매핑
CARRIER_NAMES = {
    "KE": "대한항공",
    "OZ": "아시아나항공",
    "TW": "티웨이항공",
    "LJ": "진에어",
    "7C": "제주항공",
    "BX": "에어부산",
    "ZE": "이스타항공",
    "RS": "에어서울",
    "4V": "플라이강원",
    "NH": "전일본공수(ANA)",
    "JL": "일본항공(JAL)",
    "MM": "피치항공",
    "VN": "베트남항공",
    "VJ": "비엣젯항공",
    "QH": "밤부항공",
    "SQ": "싱가포르항공",
    "TG": "타이항공",
    "FD": "타이에어아시아",
    "AK": "에어아시아",
    "CX": "캐세이퍼시픽",
    "PR": "필리핀항공",
    "5J": "세부퍼시픽",
    "GA": "가루다인도네시아",
    "QZ": "에어아시아 인도네시아",
}


def get_carrier_name(code: str) -> str:
    return CARRIER_NAMES.get(code, code)


class FlightChecker:
    """Amadeus API 기반 항공권 가격 조회기"""

    def __init__(self, api_key: str, api_secret: str, test_mode: bool = True):
        """
        Args:
            api_key: Amadeus API Key
            api_secret: Amadeus API Secret
            test_mode: True면 테스트 환경(무료), False면 프로덕션
        """
        hostname = "test" if test_mode else "production"
        self.client = Client(
            client_id=api_key,
            client_secret=api_secret,
            hostname=hostname,
        )
        self.test_mode = test_mode
        logger.info(
            "Amadeus API 클라이언트 초기화 완료 (모드: %s)", hostname
        )

    def search_flights(
        self,
        route: SearchRoute,
        departure_date: date,
        return_date: date,
        passengers: Passenger,
        max_results: int = 5,
        nonstop_only: bool = False,
    ) -> list[FlightOffer]:
        """특정 날짜의 왕복 항공편을 검색합니다."""
        try:
            response = self.client.shopping.flight_offers_search.get(
                originLocationCode=route.origin,
                destinationLocationCode=route.destination,
                departureDate=departure_date.isoformat(),
                returnDate=return_date.isoformat(),
                adults=passengers.adults,
                children=passengers.children,
                infants=passengers.infants,
                currencyCode="KRW",
                nonStop=nonstop_only,
                max=max_results,
            )
        except ResponseError as e:
            logger.error(
                "API 호출 실패 [%s→%s %s~%s]: %s",
                route.origin, route.destination,
                departure_date, return_date, e,
            )
            return []

        offers = []
        for item in response.data:
            try:
                offer = self._parse_offer(item, route, passengers)
                if offer:
                    offers.append(offer)
            except (KeyError, IndexError, ValueError) as e:
                logger.warning("응답 파싱 실패: %s", e)
                continue

        offers.sort(key=lambda o: o.total_price)
        return offers

    def search_period(
        self,
        route: SearchRoute,
        period: SearchPeriod,
        passengers: Passenger,
        max_results_per_search: int = 3,
        nonstop_only: bool = False,
        sample_interval_days: int = 3,
    ) -> list[FlightOffer]:
        """기간 내 여러 날짜 조합으로 검색하여 최저가를 찾습니다.

        Args:
            sample_interval_days: 출발일 검색 간격 (API 호출 횟수 절약)
        """
        departure_dates = self._generate_dates(
            period.departure_start,
            period.departure_end,
            sample_interval_days,
        )
        stay_durations = range(period.min_stay_days, period.max_stay_days + 1)

        all_offers: list[FlightOffer] = []
        search_count = 0

        for dep_date, stay in iter_product(departure_dates, stay_durations):
            ret_date = dep_date + timedelta(days=stay)

            logger.info(
                "검색 중: %s→%s %s~%s (%d박)",
                route.origin, route.destination,
                dep_date, ret_date, stay,
            )

            offers = self.search_flights(
                route=route,
                departure_date=dep_date,
                return_date=ret_date,
                passengers=passengers,
                max_results=max_results_per_search,
                nonstop_only=nonstop_only,
            )
            all_offers.extend(offers)
            search_count += 1

        logger.info(
            "[%s→%s] 총 %d회 검색, %d건 결과",
            route.origin, route.destination,
            search_count, len(all_offers),
        )

        all_offers.sort(key=lambda o: o.total_price)
        return all_offers

    def _parse_offer(
        self, data: dict, route: SearchRoute, passengers: Passenger
    ) -> FlightOffer | None:
        """API 응답 데이터를 FlightOffer로 변환합니다."""
        price_info = data.get("price", {})
        total_price = float(price_info.get("grandTotal", 0))
        currency = price_info.get("currency", "KRW")

        if total_price <= 0:
            return None

        price_per_person = total_price / passengers.total

        itineraries = data.get("itineraries", [])
        if len(itineraries) < 2:
            return None

        outbound_segments = self._parse_segments(itineraries[0])
        return_segments = self._parse_segments(itineraries[1])

        departure_date = outbound_segments[0].departure_time[:10] if outbound_segments else ""
        return_date = return_segments[0].departure_time[:10] if return_segments else ""

        seats = None
        traveler_pricings = data.get("travelerPricings", [])
        if traveler_pricings:
            fare_details = traveler_pricings[0].get("fareDetailsBySegment", [])
            if fare_details:
                cabin = fare_details[0].get("cabin", "")
                seats_info = fare_details[0].get("availabilityClasses", [])
                if seats_info:
                    seats = seats_info[0].get("numberOfBookableSeats")

        return FlightOffer(
            origin=route.origin,
            destination=route.destination,
            destination_name=route.destination_name,
            departure_date=departure_date,
            return_date=return_date,
            total_price=total_price,
            currency=currency,
            price_per_person=price_per_person,
            outbound_segments=outbound_segments,
            return_segments=return_segments,
            seats_remaining=seats,
        )

    def _parse_segments(self, itinerary: dict) -> list[FlightSegment]:
        """여정 데이터에서 구간 정보를 파싱합니다."""
        segments = []
        for seg in itinerary.get("segments", []):
            carrier_code = seg.get("carrierCode", "")
            segments.append(FlightSegment(
                carrier=carrier_code,
                carrier_name=get_carrier_name(carrier_code),
                flight_number=f"{carrier_code}{seg.get('number', '')}",
                departure_airport=seg.get("departure", {}).get("iataCode", ""),
                arrival_airport=seg.get("arrival", {}).get("iataCode", ""),
                departure_time=seg.get("departure", {}).get("at", ""),
                arrival_time=seg.get("arrival", {}).get("at", ""),
                duration=seg.get("duration", ""),
                stops=seg.get("numberOfStops", 0),
            ))
        return segments

    @staticmethod
    def _generate_dates(
        start: date, end: date, interval_days: int
    ) -> list[date]:
        """시작~끝 사이 날짜를 interval_days 간격으로 생성합니다."""
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=interval_days)
        if dates and dates[-1] != end:
            dates.append(end)
        return dates
