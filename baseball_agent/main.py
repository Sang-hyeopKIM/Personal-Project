#!/usr/bin/env python3
"""LG 트윈스 AI 분석 에이전트 실행 스크립트"""

import argparse
import sys

from .agent import LGTwinsAgent


def main():
    parser = argparse.ArgumentParser(
        description="LG 트윈스 야구팀 AI 분석 에이전트"
    )
    parser.add_argument(
        "-c", "--config",
        default="baseball_config.yaml",
        help="설정 파일 경로 (기본: baseball_config.yaml)",
    )
    parser.add_argument(
        "--quick",
        choices=["power", "winloss", "ranking", "players"],
        help="대화형 모드 없이 바로 특정 분석 실행",
    )
    args = parser.parse_args()

    agent = LGTwinsAgent(config_path=args.config)

    if args.quick:
        try:
            agent.initialize()
        except Exception as e:
            print(f"데이터 수집 실패: {e}")
            agent.team_summary = (
                "실시간 데이터를 가져올 수 없습니다. "
                "일반적인 LG 트윈스 지식을 바탕으로 응답해주세요."
            )

        quick_map = {
            "power": agent.analyzer.analyze_team_power,
            "winloss": agent.analyzer.analyze_win_loss_factors,
            "ranking": agent.analyzer.predict_season_ranking,
            "players": agent.analyzer.analyze_key_players,
        }
        try:
            result = quick_map[args.quick](agent.team_summary)
            print(result)
        except Exception as e:
            print(f"분석 실패: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        agent.run()


if __name__ == "__main__":
    main()
