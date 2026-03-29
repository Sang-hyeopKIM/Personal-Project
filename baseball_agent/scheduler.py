"""LG 트윈스 경기 전후 자동 분석 알림 스케줄러

경기 1시간 전: 프리뷰 분석 (상대팀 분석, 선발투수 매치업, 승부 전망)
경기 종료 후 ~1시간 이내: 결과 분석 (승패 요인, 주요 장면, 선수 평가)

하루 2번 텔레그램으로 알림을 보냅니다.
"""

import argparse
import logging
import time
from datetime import datetime, timedelta

import requests
import schedule as sched
from bs4 import BeautifulSoup

from .config import load_config
from .analyzer import LGTwinsAnalyzer
from .data_collector import KBODataCollector

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """텔레그램 알림 전송"""

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"
    MAX_LENGTH = 4000  # 텔레그램 메시지 최대 길이

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.url = self.API_URL.format(token=bot_token)

    def send(self, message: str, parse_mode: str = "HTML"):
        """메시지 전송 (긴 메시지는 분할)"""
        chunks = self._split_message(message)
        for chunk in chunks:
            payload = {
                "chat_id": self.chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
            }
            try:
                resp = requests.post(self.url, json=payload, timeout=10)
                resp.raise_for_status()
                logger.info("텔레그램 전송 완료")
            except requests.RequestException as e:
                logger.error("텔레그램 전송 실패: %s", e)

    def _split_message(self, text: str) -> list[str]:
        """긴 메시지를 분할"""
        if len(text) <= self.MAX_LENGTH:
            return [text]
        chunks = []
        while text:
            if len(text) <= self.MAX_LENGTH:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, self.MAX_LENGTH)
            if split_at == -1:
                split_at = self.MAX_LENGTH
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks


class KBOScheduleChecker:
    """KBO 경기 일정 확인"""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def get_today_lg_game(self) -> dict | None:
        """오늘 LG 트윈스 경기 정보 조회"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._find_lg_game(today)

    def _find_lg_game(self, date_str: str) -> dict | None:
        """특정 날짜의 LG 경기 검색"""
        url = (
            f"https://www.koreabaseball.com/Schedule/GameList/Main.aspx"
        )
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return self._parse_schedule(resp.text, date_str)
        except requests.RequestException as e:
            logger.warning("일정 조회 실패: %s", e)
            return self._fallback_game_info(date_str)

    def _parse_schedule(self, html: str, date_str: str) -> dict | None:
        """일정 HTML 파싱"""
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tr")

        for row in rows:
            text = row.get_text()
            if "LG" in text:
                cols = row.select("td")
                if len(cols) >= 3:
                    time_text = cols[0].get_text(strip=True)
                    teams = row.get_text()
                    return {
                        "date": date_str,
                        "time": time_text if ":" in time_text else "18:30",
                        "description": teams.strip(),
                        "has_game": True,
                    }
        return None

    def _fallback_game_info(self, date_str: str) -> dict | None:
        """스크래핑 실패 시 기본 경기 정보"""
        # KBO 시즌 중(3월~10월) 기본적으로 경기가 있다고 가정
        now = datetime.now()
        if 3 <= now.month <= 10:
            return {
                "date": date_str,
                "time": "18:30",
                "description": "LG 트윈스 경기 (상세 정보 미확인)",
                "has_game": True,
            }
        return None


class GameAnalysisScheduler:
    """경기 전후 분석 스케줄러"""

    def __init__(self, config_path: str = "baseball_config.yaml"):
        self.config = load_config(config_path)
        self.collector = KBODataCollector(self.config)
        self.analyzer = LGTwinsAnalyzer(self.config)
        self.schedule_checker = KBOScheduleChecker()
        self.notifier = self._init_notifier()
        self._today_pre_sent = False
        self._today_post_sent = False

    def _init_notifier(self) -> TelegramNotifier | None:
        """텔레그램 알림기 초기화"""
        tg_config = self.config.get("telegram", {})
        if not tg_config.get("enabled", False):
            logger.warning("텔레그램이 비활성화되어 있습니다. 콘솔 출력만 합니다.")
            return None

        return TelegramNotifier(
            bot_token=tg_config["bot_token"],
            chat_id=tg_config["chat_id"],
        )

    def _send_message(self, message: str):
        """알림 전송 (텔레그램 또는 콘솔)"""
        if self.notifier:
            self.notifier.send(message)
        print(message)

    def _get_team_summary(self) -> str:
        """팀 데이터 수집 및 요약"""
        try:
            team = self.collector.collect_all()
            return self.collector.format_team_summary(team)
        except Exception as e:
            logger.warning("데이터 수집 실패: %s", e)
            return "실시간 데이터를 가져올 수 없습니다. 기존 지식으로 분석해주세요."

    def send_pregame_analysis(self):
        """경기 전 프리뷰 분석 전송"""
        if self._today_pre_sent:
            return

        game = self.schedule_checker.get_today_lg_game()
        if not game:
            logger.info("오늘 LG 경기가 없습니다.")
            return

        logger.info("경기 전 분석 시작...")
        summary = self._get_team_summary()

        prompt = (
            f"오늘 경기 정보: {game['description']}\n\n"
            "오늘 LG 트윈스 경기 프리뷰 분석을 해주세요:\n"
            "1. 현재 팀 컨디션 및 최근 흐름\n"
            "2. 오늘 경기 승부 포인트\n"
            "3. 주목할 선수\n"
            "4. 승리 확률 및 전망\n\n"
            "간결하게 핵심만 정리해주세요."
        )

        try:
            analysis = self.analyzer.free_chat(prompt, summary)
            today = datetime.now().strftime("%Y.%m.%d")
            message = (
                f"<b>⚾ LG 트윈스 경기 프리뷰</b>\n"
                f"<b>📅 {today} | ⏰ {game['time']}</b>\n"
                f"<b>{game['description']}</b>\n\n"
                f"{analysis}"
            )
            self._send_message(message)
            self._today_pre_sent = True
            logger.info("경기 전 분석 전송 완료")
        except Exception as e:
            logger.error("경기 전 분석 실패: %s", e)

    def send_postgame_analysis(self):
        """경기 후 결과 분석 전송"""
        if self._today_post_sent:
            return

        game = self.schedule_checker.get_today_lg_game()
        if not game:
            return

        logger.info("경기 후 분석 시작...")
        summary = self._get_team_summary()

        prompt = (
            f"오늘 경기 정보: {game['description']}\n\n"
            "오늘 LG 트윈스 경기 결과 분석을 해주세요:\n"
            "1. 경기 결과 요약 및 승패 요인\n"
            "2. 주요 활약 선수 / 부진 선수\n"
            "3. 팀 순위 변동 및 시즌 영향\n"
            "4. 내일 경기 전망\n\n"
            "간결하게 핵심만 정리해주세요."
        )

        try:
            analysis = self.analyzer.free_chat(prompt, summary)
            today = datetime.now().strftime("%Y.%m.%d")
            message = (
                f"<b>⚾ LG 트윈스 경기 리뷰</b>\n"
                f"<b>📅 {today}</b>\n"
                f"<b>{game['description']}</b>\n\n"
                f"{analysis}"
            )
            self._send_message(message)
            self._today_post_sent = True
            logger.info("경기 후 분석 전송 완료")
        except Exception as e:
            logger.error("경기 후 분석 실패: %s", e)

    def reset_daily_flags(self):
        """매일 자정 플래그 리셋"""
        self._today_pre_sent = False
        self._today_post_sent = False
        self.analyzer.reset_conversation()
        logger.info("일일 플래그 리셋")

    def run(self):
        """스케줄러 실행"""
        print("=" * 50)
        print("  LG 트윈스 경기 분석 스케줄러 시작")
        print("  경기 전 프리뷰: 매일 17:30 (18:30 경기 기준)")
        print("  경기 후 리뷰:   매일 22:00")
        print("=" * 50)

        # 매일 17:30 — 경기 1시간 전 프리뷰 (18:30 경기 기준)
        sched.every().day.at("17:30").do(self.send_pregame_analysis)

        # 매일 22:00 — 경기 후 리뷰
        sched.every().day.at("22:00").do(self.send_postgame_analysis)

        # 매일 00:05 — 플래그 리셋
        sched.every().day.at("00:05").do(self.reset_daily_flags)

        # 즉시 실행 확인
        now = datetime.now()
        if now.hour < 17:
            logger.info("다음 프리뷰: 오늘 17:30")
        elif now.hour < 22:
            logger.info("다음 리뷰: 오늘 22:00")

        while True:
            sched.run_pending()
            time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="LG 트윈스 경기 분석 스케줄러")
    parser.add_argument("-c", "--config", default="baseball_config.yaml")
    parser.add_argument(
        "--test-pre", action="store_true", help="프리뷰 분석 즉시 테스트"
    )
    parser.add_argument(
        "--test-post", action="store_true", help="리뷰 분석 즉시 테스트"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scheduler = GameAnalysisScheduler(config_path=args.config)

    if args.test_pre:
        print("프리뷰 분석 테스트 실행...")
        scheduler.send_pregame_analysis()
        return
    if args.test_post:
        print("리뷰 분석 테스트 실행...")
        scheduler.send_postgame_analysis()
        return

    scheduler.run()


if __name__ == "__main__":
    main()
