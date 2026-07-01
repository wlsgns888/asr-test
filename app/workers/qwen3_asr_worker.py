import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

ARG_COUNT = 7
MLX_AUDIO_TIMEOUT_SECONDS = 7200
DEFAULT_CHUNK_SECONDS = 300.0
MAX_TOKENS_PER_CHUNK = "2048"
GENERATION_KWARGS_JSON = json.dumps({"repetition_penalty": 1.15}, separators=(",", ":"))
TranscriptPayload = dict[
    str,
    str | list[str] | list[dict[str, float | str | None]],
]


@dataclass(frozen=True, slots=True)
class WorkerArgs:
    audio: Path
    model: str
    language: str


@dataclass(frozen=True, slots=True)
class AudioChunk:
    path: Path
    offset_seconds: float


class QwenSegment(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    text: str
    start: float | None = None
    end: float | None = None
    duration: float | None = None


class QwenOutput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    text: str
    segments: list[QwenSegment] = Field(default_factory=list)


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
        workspace = Path(output_dir)
        duration_seconds = _probe_duration_seconds(args.audio)
        chunks = _prepare_chunks(
            audio=args.audio,
            output_dir=workspace,
            duration_seconds=duration_seconds,
            chunk_seconds=_configured_chunk_seconds(),
        )
        outputs = [
            _transcribe_chunk(
                args=args,
                chunk=chunk,
                output_base=workspace / f"transcript_{index:04d}",
            )
            for index, chunk in enumerate(chunks)
        ]
    return _merge_outputs(args=args, outputs=outputs)


def _probe_duration_seconds(audio: Path) -> float:
    completed = subprocess.run(
        [
            _required_executable("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(audio),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=MLX_AUDIO_TIMEOUT_SECONDS,
    )
    return float(completed.stdout.strip())


def _configured_chunk_seconds() -> float:
    raw_value = os.getenv("ASR_CHUNK_SECONDS")
    if raw_value is None:
        return DEFAULT_CHUNK_SECONDS
    chunk_seconds = float(raw_value)
    if chunk_seconds <= 0:
        raise WorkerConfigurationError
    return chunk_seconds


def _prepare_chunks(
    *,
    audio: Path,
    output_dir: Path,
    duration_seconds: float,
    chunk_seconds: float,
) -> list[AudioChunk]:
    if duration_seconds <= chunk_seconds:
        return [AudioChunk(path=audio, offset_seconds=0.0)]

    chunks: list[AudioChunk] = []
    offset_seconds = 0.0
    index = 0
    while offset_seconds < duration_seconds:
        chunk_duration = min(chunk_seconds, duration_seconds - offset_seconds)
        chunk_path = output_dir / f"chunk_{index:04d}.wav"
        _split_chunk(
            audio=audio,
            chunk_path=chunk_path,
            offset_seconds=offset_seconds,
            chunk_duration=chunk_duration,
        )
        chunks.append(AudioChunk(path=chunk_path, offset_seconds=offset_seconds))
        offset_seconds += chunk_seconds
        index += 1
    return chunks


def _split_chunk(
    *,
    audio: Path,
    chunk_path: Path,
    offset_seconds: float,
    chunk_duration: float,
) -> None:
    _ = subprocess.run(
        [
            _required_executable("ffmpeg"),
            "-y",
            "-ss",
            f"{offset_seconds:.3f}",
            "-t",
            f"{chunk_duration:.3f}",
            "-i",
            str(audio),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(chunk_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=MLX_AUDIO_TIMEOUT_SECONDS,
    )


def _transcribe_chunk(
    *,
    args: WorkerArgs,
    chunk: AudioChunk,
    output_base: Path,
) -> tuple[QwenOutput, float]:
    _ = subprocess.run(
        [
            sys.executable,
            "-m",
            "mlx_audio.stt.generate",
            "--model",
            args.model,
            "--audio",
            str(chunk.path),
            "--output-path",
            str(output_base),
            "--format",
            "json",
            "--language",
            args.language,
            "--max-tokens",
            MAX_TOKENS_PER_CHUNK,
            "--gen-kwargs",
            GENERATION_KWARGS_JSON,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=MLX_AUDIO_TIMEOUT_SECONDS,
    )
    output = QwenOutput.model_validate_json(
        output_base.with_suffix(".json").read_text(encoding="utf-8"),
    )
    return output, chunk.offset_seconds


def _merge_outputs(
    *,
    args: WorkerArgs,
    outputs: list[tuple[QwenOutput, float]],
) -> TranscriptPayload:
    text_blocks: list[str] = []
    segments: list[str] = []
    timed_segments: list[dict[str, float | str | None]] = []
    last_end: float | None = None
    for output, offset_seconds in outputs:
        stripped_text = output.text.strip()
        if stripped_text:
            text_blocks.append(stripped_text)
        for segment in output.segments:
            segments.append(segment.text)
            timed_segment = _offset_segment(
                segment=segment,
                offset_seconds=offset_seconds,
                minimum_start=last_end,
            )
            timed_segments.append(timed_segment)
            if isinstance(timed_segment["end"], float):
                last_end = timed_segment["end"]
    return {
        "model": args.model,
        "language": args.language,
        "text": "\n\n".join(text_blocks),
        "segments": segments,
        "timed_segments": timed_segments,
    }


def _offset_segment(
    segment: QwenSegment,
    offset_seconds: float,
    minimum_start: float | None,
) -> dict[str, float | str | None]:
    start = _offset_time(segment.start, offset_seconds)
    if start is not None and minimum_start is not None and start < minimum_start:
        start = minimum_start
    end = _offset_time(segment.end, offset_seconds)
    if end is not None and start is not None and end < start:
        end = start
    return {
        "text": segment.text,
        "start": start,
        "end": end,
        "duration": segment.duration,
    }


def _offset_time(value: float | None, offset_seconds: float) -> float | None:
    if value is None:
        return None
    return value + offset_seconds


def _required_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise WorkerConfigurationError
    return executable


def main() -> None:
    payload = transcribe(parse_args())
    print(json.dumps(payload, ensure_ascii=False))


class WorkerArgumentError(RuntimeError):
    pass


class WorkerConfigurationError(RuntimeError):
    pass


if __name__ == "__main__":
    main()
