import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

ARG_COUNT = 7
MLX_AUDIO_TIMEOUT_SECONDS = 7200
TranscriptPayload = dict[
    str,
    str | list[str] | list[dict[str, float | str | None]],
]


@dataclass(frozen=True, slots=True)
class WorkerArgs:
    audio: Path
    model: str
    language: str


class QwenSegment(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    text: str
    start: float | None = None
    end: float | None = None
    duration: float | None = None


class QwenOutput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    text: str
    segments: list[QwenSegment] = []


def parse_args() -> WorkerArgs:
    if len(sys.argv) != ARG_COUNT:
        raise WorkerArgumentError
    args = sys.argv
    return WorkerArgs(
        audio=Path(args[2]),
        model=args[4],
        language=args[6],
    )


def transcribe(args: WorkerArgs) -> TranscriptPayload:
    with tempfile.TemporaryDirectory() as output_dir:
        output_base = Path(output_dir) / "transcript"
        _ = subprocess.run(
            [
                sys.executable,
                "-m",
                "mlx_audio.stt.generate",
                "--model",
                args.model,
                "--audio",
                str(args.audio),
                "--output-path",
                str(output_base),
                "--format",
                "json",
                "--language",
                args.language,
                "--max-tokens",
                "256",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=MLX_AUDIO_TIMEOUT_SECONDS,
        )
        output = QwenOutput.model_validate_json(
            output_base.with_suffix(".json").read_text(encoding="utf-8"),
        )
    return {
        "model": args.model,
        "language": args.language,
        "text": output.text,
        "segments": [segment.text for segment in output.segments],
        "timed_segments": [
            segment.model_dump(mode="json") for segment in output.segments
        ],
    }


def main() -> None:
    payload = transcribe(parse_args())
    print(json.dumps(payload, ensure_ascii=False))


class WorkerArgumentError(RuntimeError):
    pass


if __name__ == "__main__":
    main()
