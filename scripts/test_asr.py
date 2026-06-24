# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastapi>=0.115.0",
#   "mlx-audio>=0.4.4",
#   "pydantic>=2.11.0",
#   "pydantic-settings>=2.9.0",
#   "orjson>=3.10.0",
# ]
# ///
# How to run:
# uv run scripts/test_asr.py path/to/audio.wav

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.services.asr_service import create_asr_engine

EXPECTED_ARG_COUNT = 2
USAGE_ERROR = 2


def main() -> int:
    if len(sys.argv) != EXPECTED_ARG_COUNT:
        print("usage: uv run scripts/test_asr.py path/to/audio.wav")
        return USAGE_ERROR

    settings = Settings()
    transcript = create_asr_engine(settings).transcribe(Path(sys.argv[1]))
    print(transcript.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
