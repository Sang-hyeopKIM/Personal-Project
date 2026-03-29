"""LG 트윈스 분석 엔진 — Claude API 기반 AI 분석"""

import anthropic

SYSTEM_PROMPT = """당신은 KBO 프로야구 전문 분석가입니다.
특히 LG 트윈스에 대한 깊은 전문 지식을 갖고 있습니다.

분석 시 다음 원칙을 따릅니다:
1. 데이터 기반 분석: 제공된 통계를 근거로 객관적 분석을 제공합니다.
2. 비교 분석: 리그 평균, 타 팀과의 비교를 통해 상대적 전력을 평가합니다.
3. 트렌드 분석: 시즌 중 성적 추이, 선수 컨디션 변화를 고려합니다.
4. 종합 평가: 공격력, 투수력, 수비력, 주루, 벤치 전력 등을 종합합니다.

응답은 한국어로 작성하며, 야구 팬이 이해할 수 있는 수준으로 설명합니다.
전문 용어는 사용하되 필요시 부연설명을 추가합니다."""


class LGTwinsAnalyzer:
    """Claude API를 활용한 LG 트윈스 분석기"""

    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config["anthropic_api_key"])
        self.model = config.get("model", "claude-sonnet-4-6")
        self.conversation_history: list[dict] = []

    def _call_claude(self, user_message: str, team_context: str = "") -> str:
        """Claude API 호출"""
        messages = list(self.conversation_history)

        if team_context:
            content = f"[현재 팀 데이터]\n{team_context}\n\n[질문]\n{user_message}"
        else:
            content = user_message

        messages.append({"role": "user", "content": content})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        assistant_msg = response.content[0].text

        # 대화 히스토리 유지
        self.conversation_history.append({"role": "user", "content": content})
        self.conversation_history.append(
            {"role": "assistant", "content": assistant_msg}
        )

        # 히스토리가 너무 길면 오래된 것부터 제거
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        return assistant_msg

    def analyze_team_power(self, team_data_summary: str) -> str:
        """팀 전력 종합 분석"""
        prompt = (
            "다음 LG 트윈스 데이터를 바탕으로 팀 전력을 종합 분석해주세요.\n"
            "공격력, 투수력, 핵심선수, 약점 등을 포함해서 분석해주세요."
        )
        return self._call_claude(prompt, team_context=team_data_summary)

    def analyze_win_loss_factors(self, team_data_summary: str) -> str:
        """승리/패배 요인 분석"""
        prompt = (
            "LG 트윈스의 승리 요인과 패배 요인을 분석해주세요.\n"
            "주요 승리 패턴, 패배 패턴, 개선이 필요한 부분을 구체적으로 설명해주세요."
        )
        return self._call_claude(prompt, team_context=team_data_summary)

    def predict_season_ranking(self, team_data_summary: str) -> str:
        """시즌 순위 전망"""
        prompt = (
            "현재 데이터를 기반으로 LG 트윈스의 시즌 최종 순위를 전망해주세요.\n"
            "포스트시즌 진출 가능성, 다른 팀과의 경쟁 구도, "
            "순위에 영향을 줄 변수들도 함께 분석해주세요."
        )
        return self._call_claude(prompt, team_context=team_data_summary)

    def analyze_key_players(self, team_data_summary: str) -> str:
        """핵심 선수 분석"""
        prompt = (
            "LG 트윈스의 핵심 선수들을 분석해주세요.\n"
            "시즌 성패를 좌우할 키플레이어, 기대주, "
            "부진 선수의 반등 가능성 등을 포함해주세요."
        )
        return self._call_claude(prompt, team_context=team_data_summary)

    def free_chat(self, question: str, team_data_summary: str = "") -> str:
        """자유 질문 응답"""
        return self._call_claude(question, team_context=team_data_summary)

    def reset_conversation(self):
        """대화 히스토리 초기화"""
        self.conversation_history.clear()
