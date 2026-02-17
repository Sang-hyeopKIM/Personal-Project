"""항공권 특가 알리미 - 웹 대시보드

Flask 기반 웹 대시보드로 가격 추이, 최저가 목록, 노선별 통계를 시각화합니다.

사용법:
    python dashboard.py                  # 기본 실행 (포트 5000)
    python dashboard.py --port 8080      # 포트 지정
    python main.py --dashboard           # 메인에서 실행
"""

import json
import logging
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template

from price_tracker import PriceTracker

CONFIG_PATH = Path(__file__).parent / "config.yaml"

logger = logging.getLogger(__name__)

app = Flask(__name__)
tracker = PriceTracker()


def load_config() -> dict:
    """설정 파일을 로드합니다."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_route_name_map(config: dict) -> dict[str, str]:
    """공항 코드 → 도시 이름 매핑을 반환합니다."""
    name_map = {}
    for r in config.get("routes", []):
        name_map[r["destination"]] = r["name"]
    return name_map


# ── 페이지 라우트 ──────────────────────────────────

@app.route("/")
def index():
    """메인 대시보드 페이지"""
    config = load_config()
    name_map = get_route_name_map(config)
    routes = config.get("routes", [])
    alerts_cfg = config.get("alerts", {})

    route_stats = []
    for route in routes:
        dest = route["destination"]
        origin = route["origin"]
        stats = tracker.get_stats(origin, dest)
        alert = alerts_cfg.get(dest, alerts_cfg.get("default", {}))

        route_stats.append({
            "origin": origin,
            "destination": dest,
            "name": route["name"],
            "stats": stats,
            "threshold_total": alert.get("threshold_total", 0),
            "threshold_per_person": alert.get("threshold_per_person", 0),
        })

    return render_template(
        "dashboard.html",
        route_stats=route_stats,
        name_map=name_map,
    )


@app.route("/route/<origin>/<destination>")
def route_detail(origin: str, destination: str):
    """노선 상세 페이지"""
    config = load_config()
    name_map = get_route_name_map(config)
    dest_name = name_map.get(destination, destination)

    stats = tracker.get_stats(origin, destination)
    best_deals = tracker.get_best_deals(origin, destination, top_n=20)
    history = tracker.get_price_history(origin, destination, limit=100)
    trend = tracker.get_price_trend(origin, destination)

    return render_template(
        "route_detail.html",
        origin=origin,
        destination=destination,
        dest_name=dest_name,
        stats=stats,
        best_deals=best_deals,
        history=history,
        trend_json=json.dumps(trend, ensure_ascii=False),
    )


# ── API 라우트 (차트 데이터) ──────────────────────

@app.route("/api/trend/<origin>/<destination>")
def api_trend(origin: str, destination: str):
    """가격 추이 JSON 데이터"""
    trend = tracker.get_price_trend(origin, destination)
    return jsonify(trend)


@app.route("/api/stats")
def api_stats():
    """전체 노선 통계 JSON"""
    config = load_config()
    routes = config.get("routes", [])
    result = []
    for route in routes:
        stats = tracker.get_stats(route["origin"], route["destination"])
        if stats:
            stats["name"] = route["name"]
            stats["destination"] = route["destination"]
            result.append(stats)
    return jsonify(result)


@app.route("/api/recent")
def api_recent():
    """최근 검색 결과 JSON"""
    config = load_config()
    name_map = get_route_name_map(config)
    results = tracker.get_recent_searches(limit=50)
    for r in results:
        r["dest_name"] = name_map.get(r["destination"], r["destination"])
    return jsonify(results)


# ── 실행 ──────────────────────────────────────────

def run_dashboard(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """대시보드 서버를 실행합니다."""
    logger.info("웹 대시보드 시작: http://%s:%d", host, port)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="항공권 특가 알리미 - 웹 대시보드")
    parser.add_argument("--host", default="0.0.0.0", help="바인드 주소")
    parser.add_argument("--port", type=int, default=5000, help="포트 번호")
    parser.add_argument("--debug", action="store_true", help="디버그 모드")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    run_dashboard(host=args.host, port=args.port, debug=args.debug)
