import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, TypeAdapter

MLX_ALIGNMENT_TIMEOUT_SECONDS = 7200
ARG_COUNT = 7


@dataclass(frozen=True, slots=True)
class WorkerArgs:
    audio: Path
    model: str
    language: str
    text: str


class AlignerSegment(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    text: str
    start: float | None = None
    end: float | None = None
    duration: float | None = None


class AlignerOutput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    text: str
    segments: list[AlignerSegment] = []


def parse_args() -> WorkerArgs:
    if len(sys.argv) != ARG_COUNT:
        raise WorkerArgumentError
    args = sys.argv
    return WorkerArgs(
        audio=Path(args[2]),
        model=args[4],
        language=args[6],
        text=sys.stdin.read(),
    )


def align(args: WorkerArgs) -> list[AlignerSegment]:
    with tempfile.TemporaryDirectory() as output_dir:
        output_base = Path(output_dir) / "alignment"
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
                "--text",
                args.text,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=MLX_ALIGNMENT_TIMEOUT_SECONDS,
        )
        output = AlignerOutput.model_validate_json(
            output_base.with_suffix(".json").read_text(encoding="utf-8"),
        )
    return output.segments


def main() -> None:
    payload = TypeAdapter(list[AlignerSegment]).dump_json(
        align(parse_args()),
    )
    print(payload.decode("utf-8"))


class WorkerArgumentError(RuntimeError):
    pass


if __name__ == "__main__":
    main()
