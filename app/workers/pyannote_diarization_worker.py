# pyright: reportMissingImports=false, reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportAny=false, reportExplicitAny=false
import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.transcript import SpeakerSegment

MISSING_DEPENDENCY_PREFIX = "pyannote.audio is not installed."
MISSING_DEPENDENCY_ACTION = "Install the optional diarization dependencies"
MISSING_DEPENDENCY_TARGET = "in a Python version supported by pyannote.audio."
MISSING_DEPENDENCY_MESSAGE = (
    f"{MISSING_DEPENDENCY_PREFIX} "
    f"{MISSING_DEPENDENCY_ACTION} "
    f"{MISSING_DEPENDENCY_TARGET}"
)


@dataclass(frozen=True, slots=True)
class WorkerArgs:
    audio: Path
    model: str


def parse_args() -> WorkerArgs:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--audio", required=True)
    _ = parser.add_argument("--model", required=True)
    args = parser.parse_args()
    return WorkerArgs(audio=Path(str(args.audio)), model=str(args.model))


def diarize(audio: Path, model: str) -> list[SpeakerSegment]:
    token = os.environ.get("PYANNOTE_AUTH_TOKEN", "")
    if token == "":
        message = "PYANNOTE_AUTH_TOKEN is required"
        raise WorkerConfigurationError(message)

    try:
        from pyannote.audio import Pipeline
    except ModuleNotFoundError as error:
        raise WorkerConfigurationError(MISSING_DEPENDENCY_MESSAGE) from error

    try:
        pipeline = Pipeline.from_pretrained(model, token=token)
    except TypeError:
        pipeline = Pipeline.from_pretrained(model, use_auth_token=token)
    output = pipeline(str(audio))
    annotation = getattr(output, "speaker_diarization", output)
    return [
        SpeakerSegment(
            speaker=str(speaker),
            start=float(turn.start),
            end=float(turn.end),
        )
        for turn, speaker in _iter_speaker_turns(annotation)
    ]


def _iter_speaker_turns(annotation: Any) -> list[tuple[Any, str]]:
    if hasattr(annotation, "itertracks"):
        return [
            (turn, str(speaker))
            for turn, _, speaker in annotation.itertracks(yield_label=True)
        ]
    return [(turn, str(speaker)) for turn, speaker in annotation]


def main() -> None:
    args = parse_args()
    payload = [
        segment.model_dump(mode="json") for segment in diarize(args.audio, args.model)
    ]
    print(json.dumps(payload, ensure_ascii=False))


class WorkerConfigurationError(RuntimeError):
    pass


if __name__ == "__main__":
    main()
