"""LG 트윈스 AI 분석 에이전트 — 웹 대시보드

Flask 기반 웹 대시보드로 팀 전력, 선수 성적, AI 분석 결과를 시각화합니다.

사용법:
    python -m baseball_agent.web                # 기본 실행 (포트 5001)
    python -m baseball_agent.web --port 8080    # 포트 지정
"""

import argparse
import json
import logging
import threading

from flask import Flask, jsonify, render_template, request

from .config import load_config
from .data_collector import KBODataCollector
from .analyzer import LGTwinsAnalyzer

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="../templates/baseball")

# 글로벌 상태
_state = {
    "config": None,
    "collector": None,
    "analyzer": None,
    "team_data": None,
    "team_summary": "",
    "analysis_cache": {},
    "loading": False,
}
_lock = threading.Lock()


def init_app(config_path: str = "baseball_config.yaml"):
    """앱 초기화"""
    config = load_config(config_path)
    _state["config"] = config
    _state["collector"] = KBODataCollector(config)
    _state["analyzer"] = LGTwinsAnalyzer(config)
    _refresh_data()


def _refresh_data():
    """데이터 새로고침"""
    collector = _state["collector"]
    try:
        _state["loading"] = True
        _state["team_data"] = collector.collect_all()
        _state["team_summary"] = collector.format_team_summary(_state["team_data"])
        _state["analysis_cache"] = {}
    except Exception as e:
        logger.warning("데이터 수집 실패: %s", e)
        _state["team_summary"] = (
            "실시간 데이터를 가져올 수 없습니다. "
            "일반적인 LG 트윈스 지식을 바탕으로 응답해주세요."
        )
    finally:
        _state["loading"] = False


# ── 페이지 라우트 ──────────────────────────────────


@app.route("/")
def index():
    """메인 대시보드"""
    team = _state["team_data"]
    return render_template("baseball_dashboard.html", team=team, summary=_state["team_summary"])


# ── API 라우트 ─────────────────────────────────────


@app.route("/api/team")
def api_team():
    """팀 기본 데이터"""
    team = _state["team_data"]
    if not team:
        return jsonify({"error": "데이터 없음"}), 404

    return jsonify({
        "team_name": team.team_name,
        "season": team.season,
        "rank": team.rank,
        "wins": team.wins,
        "losses": team.losses,
        "draws": team.draws,
        "win_rate": round(team.wins / max(team.wins + team.losses, 1), 3),
    })


@app.route("/api/batters")
def api_batters():
    """타자 성적"""
    team = _state["team_data"]
    if not team:
        return jsonify([])

    batters = sorted(team.batters, key=lambda x: x.ops, reverse=True)
    return jsonify([
        {
            "name": b.name, "games": b.games,
            "avg": b.avg, "obp": b.obp, "slg": b.slg,
            "ops": b.ops, "hr": b.hr, "rbi": b.rbi,
        }
        for b in batters
    ])


@app.route("/api/pitchers")
def api_pitchers():
    """투수 성적"""
    team = _state["team_data"]
    if not team:
        return jsonify([])

    pitchers = sorted(team.pitchers, key=lambda x: x.innings, reverse=True)
    return jsonify([
        {
            "name": p.name, "games": p.games,
            "wins": p.wins, "losses": p.losses,
            "era": p.era, "innings": p.innings,
            "strikeouts": p.strikeouts,
        }
        for p in pitchers
    ])


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """AI 분석 요청"""
    data = request.get_json() or {}
    analysis_type = data.get("type", "power")
    force = data.get("force", False)

    # 캐시 확인
    if not force and analysis_type in _state["analysis_cache"]:
        return jsonify({"result": _state["analysis_cache"][analysis_type]})

    analyzer = _state["analyzer"]
    summary = _state["team_summary"]

    analysis_map = {
        "power": analyzer.analyze_team_power,
        "winloss": analyzer.analyze_win_loss_factors,
        "ranking": analyzer.predict_season_ranking,
        "players": analyzer.analyze_key_players,
    }

    func = analysis_map.get(analysis_type)
    if not func:
        return jsonify({"error": f"알 수 없는 분석 유형: {analysis_type}"}), 400

    try:
        result = func(summary)
        with _lock:
            _state["analysis_cache"][analysis_type] = result
        return jsonify({"result": result})
    except Exception as e:
        logger.error("분석 실패: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """자유 질문"""
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "질문을 입력해주세요."}), 400

    try:
        result = _state["analyzer"].free_chat(question, _state["team_summary"])
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """데이터 새로고침"""
    _refresh_data()
    return jsonify({"status": "ok"})


# ── 실행 ──────────────────────────────────────────


def run_dashboard(host: str = "0.0.0.0", port: int = 5001, debug: bool = False,
                  config_path: str = "baseball_config.yaml"):
    """대시보드 서버 실행"""
    init_app(config_path)
    logger.info("LG 트윈스 대시보드 시작: http://%s:%d", host, port)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LG 트윈스 AI 분석 대시보드")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("-c", "--config", default="baseball_config.yaml")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    run_dashboard(host=args.host, port=args.port, debug=args.debug,
                  config_path=args.config)
