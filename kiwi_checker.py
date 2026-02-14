"""항공권 특가 알리미 - Kiwi.com Tequila API 모듈

Amadeus의 대안으로, Kiwi.com Tequila API를 사용합니다.
무료 티어: 월 3,000회 API 호출 (신용카드 불필요)
가입: https://tequila.kiwi.com/

특징:
  - Amadeus보다 6배 많은 무료 호출 횟수
  - LCC(저가항공) 포함 더 넓은 범위의 항공사 커버
  - 날짜 범위 검색이 1회 호출로 가능 (API 절약)
"""

import logging
from datetime import date

import requests

from models import FlightOffer, FlightSegment, Passenger, SearchPeriod, SearchRoute

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.tequila.kiwi.com/v2/search"


class KiwiChecker:
    """Kiwi Tequila API 기반 항공권 가격 조회기"""

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Tequila API Key (Dashboard → API Keys에서 확인)
        """
        self.api_key = api_key
        self.headers = {"apikey": api_key}
        logger.info("Kiwi Tequila API 클라이언트 초기화 완료")

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
        params = {
            "fly_from": route.origin,
            "fly_to": route.destination,
            "date_from": departure_date.strftime("%d/%m/%Y"),
            "date_to": departure_date.strftime("%d/%m/%Y"),
            "return_from": return_date.strftime("%d/%m/%Y"),
            "return_to": return_date.strftime("%d/%m/%Y"),
            "flight_type": "round",
            "adults": passengers.adults,
            "children": passengers.children,
            "infants": passengers.infants,
            "curr": "KRW",
            "locale": "ko",
            "limit": max_results,
            "sort": "price",
            "max_stopovers": 0 if nonstop_only else 2,
        }

        try:
            resp = requests.get(
                SEARCH_URL,
                headers=self.headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(
                "Kiwi API 호출 실패 [%s→%s]: %s",
                route.origin, route.destination, e,
            )
            return []

        return self._parse_results(data, route, passengers)

    def search_period(
        self,
        route: SearchRoute,
        period: SearchPeriod,
        passengers: Passenger,
        max_results_per_search: int = 5,
        nonstop_only: bool = False,
        **_kwargs,
    ) -> list[FlightOffer]:
        """기간 내 최저가를 검색합니다.

        Kiwi API는 날짜 범위 검색을 1회 호출로 지원하므로
        Amadeus보다 훨씬 적은 API 호출로 같은 결과를 얻습니다.
        """
        all_offers: list[FlightOffer] = []

        for stay_days in range(period.min_stay_days, period.max_stay_days + 1):
            params = {
                "fly_from": route.origin,
                "fly_to": route.destination,
                "date_from": period.departure_start.strftime("%d/%m/%Y"),
                "date_to": period.departure_end.strftime("%d/%m/%Y"),
                "nights_in_dst_from": stay_days,
                "nights_in_dst_to": stay_days,
                "flight_type": "round",
                "adults": passengers.adults,
                "children": passengers.children,
                "infants": passengers.infants,
                "curr": "KRW",
                "locale": "ko",
                "limit": max_results_per_search,
                "sort": "price",
                "max_stopovers": 0 if nonstop_only else 2,
            }

            logger.info(
                "검색 중: %s→%s %s~%s (%d박)",
                route.origin, route.destination_name,
                period.departure_start, period.departure_end, stay_days,
            )

            try:
                resp = requests.get(
                    SEARCH_URL,
                    headers=self.headers,
                    params=params,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                offers = self._parse_results(data, route, passengers)
                all_offers.extend(offers)
            except requests.RequestException as e:
                logger.error("Kiwi API 호출 실패: %s", e)
                continue

        all_offers.sort(key=lambda o: o.total_price)
        logger.info(
            "[%s→%s] 총 %d건 결과",
            route.origin, route.destination_name, len(all_offers),
        )
        return all_offers

    def _parse_results(
        self, data: dict, route: SearchRoute, passengers: Passenger
    ) -> list[FlightOffer]:
        """API 응답을 FlightOffer 목록으로 변환합니다."""
        offers = []
        for item in data.get("data", []):
            try:
                offer = self._parse_item(item, route, passengers)
                if offer:
                    offers.append(offer)
            except (KeyError, ValueError) as e:
                logger.warning("파싱 실패: %s", e)
                continue
        return offers

    def _parse_item(
        self, item: dict, route: SearchRoute, passengers: Passenger
    ) -> FlightOffer | None:
        """개별 검색 결과를 파싱합니다."""
        total_price = float(item.get("price", 0))
        if total_price <= 0:
            return None

        price_per_person = total_price / passengers.total

        # 구간 정보 파싱
        outbound_segs = []
        return_segs = []

        for seg_data in item.get("route", []):
            seg = FlightSegment(
                carrier=seg_data.get("airline", ""),
                carrier_name=seg_data.get("airline", ""),
                flight_number=f"{seg_data.get('airline', '')}{seg_data.get('flight_no', '')}",
                departure_airport=seg_data.get("flyFrom", ""),
                arrival_airport=seg_data.get("flyTo", ""),
                departure_time=seg_data.get("local_departure", ""),
                arrival_time=seg_data.get("local_arrival", ""),
                duration="",
                stops=0,
            )
            if seg_data.get("return") == 0:
                outbound_segs.append(seg)
            else:
                return_segs.append(seg)

        dep_date = item.get("local_departure", "")[:10]
        ret_date = item.get("local_arrival", "")[:10]

        # route에서 도착 날짜 추출
        for seg_data in item.get("route", []):
            if seg_data.get("return") == 1:
                ret_date = seg_data.get("local_departure", "")[:10]
                break

        # 가는편 마지막 구간의 날짜를 기준으로 출발일 결정
        if outbound_segs:
            dep_date = outbound_segs[0].departure_time[:10]

        return FlightOffer(
            origin=route.origin,
            destination=route.destination,
            destination_name=route.destination_name,
            departure_date=dep_date,
            return_date=ret_date,
            total_price=total_price,
            currency="KRW",
            price_per_person=price_per_person,
            outbound_segments=outbound_segs,
            return_segments=return_segs,
        )
