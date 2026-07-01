# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastapi>=0.115.0",
#   "orjson>=3.10.0",
#   "openai>=1.90.0",
#   "pydantic>=2.11.0",
#   "pydantic-settings>=2.9.0",
# ]
# ///
# How to run:
# uv run scripts/test_llm.py "오늘 회의에서는 배포 일정을 논의했다."

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppEnv, LLMProvider, Settings
from app.schemas.minutes import DEFAULT_MINUTES_PROMPT
from app.services.llm_service import LLMService

EXPECTED_ARG_COUNT = 2
USAGE_ERROR = 2


def main() -> int:
    if len(sys.argv) != EXPECTED_ARG_COUNT:
        print('usage: uv run scripts/test_llm.py "전사문"')
        return USAGE_ERROR

    service = LLMService(
        Settings(app_env=AppEnv.TESTING, llm_provider=LLMProvider.FAKE)
    )
    markdown = service.generate_minutes(
        transcript=sys.argv[1],
        prompt=DEFAULT_MINUTES_PROMPT,
    )
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
