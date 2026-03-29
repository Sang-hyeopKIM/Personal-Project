"""설정 관리 모듈"""

import os
import yaml


DEFAULT_CONFIG = {
    "anthropic_api_key": "",
    "model": "claude-sonnet-4-6",
    "kbo_team": "LG",
    "season_year": 2026,
    "language": "ko",
    "data_sources": {
        "statiz_base_url": "https://statiz.sporki.com",
        "kbo_base_url": "https://www.koreabaseball.com",
    },
}


def load_config(config_path: str = "baseball_config.yaml") -> dict:
    """YAML 설정 파일 로드. 없으면 기본값 사용."""
    config = DEFAULT_CONFIG.copy()

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
            config.update(user_config)

    # 환경변수 우선
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        config["anthropic_api_key"] = api_key

    return config
