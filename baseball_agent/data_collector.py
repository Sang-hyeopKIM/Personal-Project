"""KBO LG 트윈스 데이터 수집 모듈

Statiz(sporki.com) 및 KBO 공식 사이트에서 팀/선수 데이터를 수집합니다.
"""

import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field


@dataclass
class PlayerStats:
    name: str
    position: str
    games: int = 0
    # 타자
    avg: float = 0.0
    obp: float = 0.0
    slg: float = 0.0
    ops: float = 0.0
    hr: int = 0
    rbi: int = 0
    sb: int = 0
    war: float = 0.0
    # 투수
    era: float = 0.0
    wins: int = 0
    losses: int = 0
    innings: float = 0.0
    strikeouts: int = 0
    whip: float = 0.0


@dataclass
class TeamStats:
    team_name: str = "LG 트윈스"
    season: int = 2026
    wins: int = 0
    losses: int = 0
    draws: int = 0
    rank: int = 0
    team_avg: float = 0.0
    team_era: float = 0.0
    team_ops: float = 0.0
    runs_scored: int = 0
    runs_allowed: int = 0
    run_differential: int = 0
    batters: list = field(default_factory=list)
    pitchers: list = field(default_factory=list)
    recent_results: list = field(default_factory=list)


class KBODataCollector:
    """KBO 데이터 수집기"""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def __init__(self, config: dict):
        self.config = config
        self.season = config.get("season_year", 2026)
        self.statiz_url = config["data_sources"]["statiz_base_url"]
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def fetch_team_standings(self) -> dict | None:
        """KBO 팀 순위표 수집"""
        url = f"{self.statiz_url}/season/?m=teamRank&s_season={self.season}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return self._parse_standings(resp.text)
        except requests.RequestException as e:
            print(f"[경고] 순위표 수집 실패: {e}")
            return None

    def _parse_standings(self, html: str) -> dict:
        """순위표 HTML 파싱"""
        soup = BeautifulSoup(html, "html.parser")
        standings = {}
        table = soup.select_one("table.table-striped")
        if not table:
            return standings

        rows = table.select("tbody tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 5:
                continue
            team_name = cols[1].get_text(strip=True)
            standings[team_name] = {
                "rank": cols[0].get_text(strip=True),
                "games": cols[2].get_text(strip=True),
                "wins": cols[3].get_text(strip=True),
                "losses": cols[4].get_text(strip=True),
                "draws": cols[5].get_text(strip=True) if len(cols) > 5 else "0",
                "win_rate": cols[6].get_text(strip=True) if len(cols) > 6 else "",
            }
        return standings

    def fetch_team_batting_stats(self) -> list[PlayerStats]:
        """LG 트윈스 타자 성적 수집"""
        url = (
            f"{self.statiz_url}/season/?m=teamBatter"
            f"&s_season={self.season}&t_code=2002"
        )
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return self._parse_batter_stats(resp.text)
        except requests.RequestException as e:
            print(f"[경고] 타자 성적 수집 실패: {e}")
            return []

    def _parse_batter_stats(self, html: str) -> list[PlayerStats]:
        """타자 성적 HTML 파싱"""
        soup = BeautifulSoup(html, "html.parser")
        players = []
        table = soup.select_one("table.table-striped")
        if not table:
            return players

        rows = table.select("tbody tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 10:
                continue
            try:
                player = PlayerStats(
                    name=cols[1].get_text(strip=True),
                    position="타자",
                    games=int(cols[2].get_text(strip=True) or 0),
                    avg=float(cols[3].get_text(strip=True) or 0),
                    obp=float(cols[4].get_text(strip=True) or 0),
                    slg=float(cols[5].get_text(strip=True) or 0),
                    hr=int(cols[7].get_text(strip=True) or 0),
                    rbi=int(cols[8].get_text(strip=True) or 0),
                )
                player.ops = round(player.obp + player.slg, 3)
                players.append(player)
            except (ValueError, IndexError):
                continue
        return players

    def fetch_team_pitching_stats(self) -> list[PlayerStats]:
        """LG 트윈스 투수 성적 수집"""
        url = (
            f"{self.statiz_url}/season/?m=teamPitcher"
            f"&s_season={self.season}&t_code=2002"
        )
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return self._parse_pitcher_stats(resp.text)
        except requests.RequestException as e:
            print(f"[경고] 투수 성적 수집 실패: {e}")
            return []

    def _parse_pitcher_stats(self, html: str) -> list[PlayerStats]:
        """투수 성적 HTML 파싱"""
        soup = BeautifulSoup(html, "html.parser")
        players = []
        table = soup.select_one("table.table-striped")
        if not table:
            return players

        rows = table.select("tbody tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 10:
                continue
            try:
                player = PlayerStats(
                    name=cols[1].get_text(strip=True),
                    position="투수",
                    games=int(cols[2].get_text(strip=True) or 0),
                    wins=int(cols[3].get_text(strip=True) or 0),
                    losses=int(cols[4].get_text(strip=True) or 0),
                    era=float(cols[6].get_text(strip=True) or 0),
                    innings=float(cols[7].get_text(strip=True) or 0),
                    strikeouts=int(cols[9].get_text(strip=True) or 0),
                )
                players.append(player)
            except (ValueError, IndexError):
                continue
        return players

    def collect_all(self) -> TeamStats:
        """모든 데이터를 수집하여 TeamStats 반환"""
        team = TeamStats(season=self.season)

        standings = self.fetch_team_standings()
        if standings:
            lg_data = standings.get("LG", {})
            team.rank = int(lg_data.get("rank", 0) or 0)
            team.wins = int(lg_data.get("wins", 0) or 0)
            team.losses = int(lg_data.get("losses", 0) or 0)
            team.draws = int(lg_data.get("draws", 0) or 0)

        team.batters = self.fetch_team_batting_stats()
        team.pitchers = self.fetch_team_pitching_stats()

        return team

    def format_team_summary(self, team: TeamStats) -> str:
        """팀 데이터를 텍스트 요약으로 변환"""
        lines = [
            f"=== {team.team_name} {team.season} 시즌 현황 ===",
            f"순위: {team.rank}위 | 성적: {team.wins}승 {team.losses}패 {team.draws}무",
            "",
        ]

        if team.batters:
            lines.append("--- 주요 타자 성적 ---")
            for b in sorted(team.batters, key=lambda x: x.ops, reverse=True)[:10]:
                lines.append(
                    f"  {b.name}: 타율 {b.avg:.3f} | OBP {b.obp:.3f} | "
                    f"SLG {b.slg:.3f} | OPS {b.ops:.3f} | "
                    f"HR {b.hr} | RBI {b.rbi}"
                )
            lines.append("")

        if team.pitchers:
            lines.append("--- 주요 투수 성적 ---")
            for p in sorted(team.pitchers, key=lambda x: x.innings, reverse=True)[:10]:
                lines.append(
                    f"  {p.name}: {p.wins}승 {p.losses}패 | "
                    f"ERA {p.era:.2f} | IP {p.innings:.1f} | "
                    f"SO {p.strikeouts}"
                )
            lines.append("")

        return "\n".join(lines)
