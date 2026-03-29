"""LG 트윈스 AI 에이전트 — 메인 에이전트 오케스트레이터"""

from .config import load_config
from .data_collector import KBODataCollector, TeamStats
from .analyzer import LGTwinsAnalyzer


class LGTwinsAgent:
    """LG 트윈스 전력 분석 AI 에이전트

    데이터 수집 → AI 분석 → 사용자 응답의 파이프라인을 관리합니다.
    """

    MENU = """
╔══════════════════════════════════════════════╗
║       ⚾ LG 트윈스 AI 분석 에이전트 ⚾       ║
╠══════════════════════════════════════════════╣
║  1. 팀 전력 종합 분석                         ║
║  2. 승리/패배 요인 분석                       ║
║  3. 시즌 순위 전망                            ║
║  4. 핵심 선수 분석                            ║
║  5. 자유 질문                                 ║
║  6. 데이터 새로고침                           ║
║  7. 대화 초기화                               ║
║  0. 종료                                      ║
╚══════════════════════════════════════════════╝
"""

    def __init__(self, config_path: str = "baseball_config.yaml"):
        self.config = load_config(config_path)
        self.collector = KBODataCollector(self.config)
        self.analyzer = LGTwinsAnalyzer(self.config)
        self.team_data: TeamStats | None = None
        self.team_summary: str = ""

    def initialize(self):
        """에이전트 초기화: 데이터 수집"""
        print("데이터를 수집하는 중입니다...")
        self.team_data = self.collector.collect_all()
        self.team_summary = self.collector.format_team_summary(self.team_data)
        print("데이터 수집 완료!\n")
        print(self.team_summary)

    def run(self):
        """대화형 에이전트 실행"""
        print("\nLG 트윈스 AI 분석 에이전트를 시작합니다.")
        print("데이터를 로딩 중...")

        try:
            self.initialize()
        except Exception as e:
            print(f"\n[경고] 실시간 데이터 수집 실패: {e}")
            print("저장된 지식 기반으로 분석을 진행합니다.\n")
            self.team_summary = (
                "실시간 데이터를 가져올 수 없습니다. "
                "일반적인 LG 트윈스 지식을 바탕으로 응답해주세요."
            )

        while True:
            print(self.MENU)
            choice = input("선택 (0-7): ").strip()

            if choice == "0":
                print("\n에이전트를 종료합니다. 감사합니다!")
                break
            elif choice == "1":
                self._run_analysis("팀 전력 분석", self.analyzer.analyze_team_power)
            elif choice == "2":
                self._run_analysis(
                    "승패 요인 분석", self.analyzer.analyze_win_loss_factors
                )
            elif choice == "3":
                self._run_analysis(
                    "시즌 순위 전망", self.analyzer.predict_season_ranking
                )
            elif choice == "4":
                self._run_analysis(
                    "핵심 선수 분석", self.analyzer.analyze_key_players
                )
            elif choice == "5":
                self._free_chat()
            elif choice == "6":
                self.initialize()
            elif choice == "7":
                self.analyzer.reset_conversation()
                print("대화 히스토리가 초기화되었습니다.")
            else:
                print("잘못된 입력입니다. 0-7 사이의 숫자를 입력해주세요.")

    def _run_analysis(self, title: str, analysis_func):
        """분석 실행 및 결과 출력"""
        print(f"\n{'='*50}")
        print(f"  {title} 진행 중...")
        print(f"{'='*50}\n")

        try:
            result = analysis_func(self.team_summary)
            print(result)
        except Exception as e:
            print(f"\n[오류] 분석 중 문제가 발생했습니다: {e}")
            print("API 키를 확인하거나 잠시 후 다시 시도해주세요.")

    def _free_chat(self):
        """자유 질문 모드"""
        print("\n자유 질문 모드입니다. (돌아가려면 'q' 입력)")
        while True:
            question = input("\n질문: ").strip()
            if question.lower() == "q":
                break
            if not question:
                continue

            try:
                result = self.analyzer.free_chat(question, self.team_summary)
                print(f"\n{result}")
            except Exception as e:
                print(f"\n[오류] 응답 중 문제가 발생했습니다: {e}")
