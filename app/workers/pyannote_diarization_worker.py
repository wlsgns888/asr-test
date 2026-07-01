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
DIARIZATION_DEVICE_ENV = "DIARIZATION_DEVICE"


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
    if token == "" and not Path(model).expanduser().exists():
        message = "PYANNOTE_AUTH_TOKEN is required"
        raise WorkerConfigurationError(message)

    try:
        from pyannote.audio import Pipeline
    except ModuleNotFoundError as error:
        raise WorkerConfigurationError(MISSING_DEPENDENCY_MESSAGE) from error

    pipeline = Pipeline.from_pretrained(model, token=token or None)
    if pipeline is None:
        message = "pyannote pipeline could not be loaded"
        raise WorkerConfigurationError(message)
    device_name = select_diarization_device_name()
    if device_name is not None:
        import torch

        _ = pipeline.to(torch.device(device_name))
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


def select_diarization_device_name() -> str | None:
    import torch

    requested_device = os.environ.get(DIARIZATION_DEVICE_ENV, "auto").strip().lower()
    if requested_device in ("", "auto"):
        if torch.cuda.is_available():
            return "cuda"
        mps_backend = getattr(torch.backends, "mps", None)
        if mps_backend is not None and mps_backend.is_available():
            return "mps"
        return None
    if requested_device == "cpu":
        return None
    if requested_device in ("cuda", "mps"):
        return requested_device
    message = f"{DIARIZATION_DEVICE_ENV} must be one of auto, cpu, cuda, or mps"
    raise WorkerConfigurationError(message)


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
