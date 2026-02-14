"""항공권 특가 알리미 - 검색 링크 생성기

API 호출 없이 네이버 항공권, 구글 플라이트, 스카이스캐너의
검색 URL을 직접 생성하여 브라우저에서 바로 확인할 수 있습니다.
"""

from datetime import date, timedelta

from models import Passenger, SearchPeriod, SearchRoute


def naver_flight_url(
    route: SearchRoute,
    departure_date: date,
    return_date: date,
    passengers: Passenger,
) -> str:
    """네이버 항공권 검색 URL을 생성합니다."""
    dep = departure_date.strftime("%Y%m%d")
    ret = return_date.strftime("%Y%m%d")
    base = "https://flight.naver.com/flights/international"
    return (
        f"{base}/{route.origin}-{route.destination}-{dep}"
        f"/{route.destination}-{route.origin}-{ret}"
        f"?adult={passengers.adults}"
        f"&child={passengers.children}"
        f"&infant={passengers.infants}"
        f"&fareType=Y"
    )


def google_flights_url(
    route: SearchRoute,
    departure_date: date,
    return_date: date,
    passengers: Passenger,
) -> str:
    """구글 플라이트 검색 URL을 생성합니다."""
    dep = departure_date.isoformat()
    ret = return_date.isoformat()
    # 구글 플라이트 URL 형식
    return (
        f"https://www.google.com/travel/flights"
        f"?q=Flights+to+{route.destination}+from+{route.origin}"
        f"+on+{dep}+through+{ret}"
        f"&curr=KRW&hl=ko"
    )


def skyscanner_url(
    route: SearchRoute,
    departure_date: date,
    return_date: date,
    passengers: Passenger,
) -> str:
    """스카이스캐너 검색 URL을 생성합니다."""
    dep = departure_date.strftime("%y%m%d")
    ret = return_date.strftime("%y%m%d")
    adults = passengers.adults
    children_ages = "10,6"  # config에서 가져올 수도 있음
    return (
        f"https://www.skyscanner.co.kr/transport/flights"
        f"/{route.origin.lower()}/{route.destination.lower()}"
        f"/{dep}/{ret}"
        f"/?adults={adults}&children={passengers.children}"
        f"&childrenAge={children_ages}"
        f"&currency=KRW&locale=ko-KR&market=KR"
    )


def generate_all_links(
    routes: list[SearchRoute],
    periods: list[SearchPeriod],
    passengers: Passenger,
    sample_interval_days: int = 7,
) -> str:
    """모든 노선/기간에 대한 검색 링크를 생성합니다."""
    output_lines = []
    output_lines.append("=" * 70)
    output_lines.append("  항공권 검색 링크 모음")
    output_lines.append(f"  탑승객: 성인 {passengers.adults}명 + 아동 {passengers.children}명")
    output_lines.append("=" * 70)

    for route in routes:
        output_lines.append(f"\n{'─'*50}")
        output_lines.append(f"  {route.destination_name} ({route.origin} → {route.destination})")
        output_lines.append(f"{'─'*50}")

        for period in periods:
            current = period.departure_start
            mid_stay = (period.min_stay_days + period.max_stay_days) // 2

            while current <= period.departure_end:
                ret = current + timedelta(days=mid_stay)
                output_lines.append(
                    f"\n  {current.isoformat()} ~ {ret.isoformat()} ({mid_stay}박)"
                )
                output_lines.append(
                    f"    네이버:    {naver_flight_url(route, current, ret, passengers)}"
                )
                output_lines.append(
                    f"    구글:      {google_flights_url(route, current, ret, passengers)}"
                )
                output_lines.append(
                    f"    스카이스캐너: {skyscanner_url(route, current, ret, passengers)}"
                )
                current += timedelta(days=sample_interval_days)

    output_lines.append(f"\n{'='*70}")
    return "\n".join(output_lines)


def generate_quick_links(
    route: SearchRoute,
    departure_date: date,
    return_date: date,
    passengers: Passenger,
) -> str:
    """단일 검색 조건에 대한 링크를 빠르게 생성합니다."""
    stay = (return_date - departure_date).days
    lines = [
        f"{route.destination_name} | {departure_date} ~ {return_date} ({stay}박)",
        f"  네이버:      {naver_flight_url(route, departure_date, return_date, passengers)}",
        f"  구글:        {google_flights_url(route, departure_date, return_date, passengers)}",
        f"  스카이스캐너: {skyscanner_url(route, departure_date, return_date, passengers)}",
    ]
    return "\n".join(lines)
