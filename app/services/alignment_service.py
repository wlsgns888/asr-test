import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from pydantic import TypeAdapter

from app.config import AlignmentEngine, Settings
from app.schemas.transcript import TimedTranscriptSegment, TranscriptDocument

ALIGNMENT_WORKER_TIMEOUT_SECONDS = 7200
FFMPEG_CLIP_TIMEOUT_SECONDS: Final = 900
MAX_ALIGNMENT_WINDOW_SECONDS: Final = 295.0
SEGMENT_ADAPTER: Final = TypeAdapter(list[TimedTranscriptSegment])


class TranscriptAlignmentBackend(Protocol):
    def align(
        self,
        wav_path: Path,
        transcript: TranscriptDocument,
    ) -> TranscriptDocument: ...


@dataclass(frozen=True, slots=True)
class DisabledTranscriptAlignmentBackend:
    def align(
        self,
        wav_path: Path,
        transcript: TranscriptDocument,
    ) -> TranscriptDocument:
        _ = wav_path
        return transcript


@dataclass(frozen=True, slots=True)
class Qwen3ForcedAlignmentBackend:
    settings: Settings

    def align(
        self,
        wav_path: Path,
        transcript: TranscriptDocument,
    ) -> TranscriptDocument:
        if transcript.text == "":
            return transcript
        segments = self._align_segments(wav_path, transcript)
        if len(segments) == 0:
            return transcript
        return transcript.model_copy(
            update={
                "timed_segments": segments,
                "segments": [segment.text for segment in segments],
            }
        )

    def _align_segments(
        self,
        wav_path: Path,
        transcript: TranscriptDocument,
    ) -> list[TimedTranscriptSegment]:
        if len(transcript.timed_segments) == 0:
            return self._align_text(wav_path, transcript.text)
        aligned_segments: list[TimedTranscriptSegment] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for window in _alignment_windows(transcript.timed_segments):
                clip_path = Path(temp_dir) / f"alignment-{len(aligned_segments)}.wav"
                _write_wav_clip(wav_path, clip_path, window)
                aligned_segments.extend(
                    _offset_segments(
                        self._align_text(clip_path, window.text),
                        window.start,
                    )
                )
        return aligned_segments

    def _align_text(
        self,
        wav_path: Path,
        text: str,
    ) -> list[TimedTranscriptSegment]:
        command = [
            sys.executable,
            "-m",
            "app.workers.qwen3_forced_aligner_worker",
            "--audio",
            str(wav_path),
            "--model",
            self.settings.alignment_model,
            "--language",
            self.settings.asr_language,
        ]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                input=text,
                text=True,
                timeout=ALIGNMENT_WORKER_TIMEOUT_SECONDS,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise AlignmentWorkerError(_worker_error_message(error)) from error
        return SEGMENT_ADAPTER.validate_json(completed.stdout)


@dataclass(frozen=True, slots=True)
class AlignmentWindow:
    text: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def _alignment_windows(
    segments: list[TimedTranscriptSegment],
) -> list[AlignmentWindow]:
    windows: list[AlignmentWindow] = []
    for segment in segments:
        start = segment.start if segment.start is not None else 0.0
        end = _segment_end(segment, start)
        if segment.text == "" or end <= start:
            continue
        if end - start <= MAX_ALIGNMENT_WINDOW_SECONDS:
            windows.append(AlignmentWindow(text=segment.text, start=start, end=end))
            continue
        windows.extend(_split_window(segment.text, start, end))
    return windows


def _split_window(text: str, start: float, end: float) -> list[AlignmentWindow]:
    tokens = text.split()
    if len(tokens) == 0:
        return []
    duration = end - start
    window_count = int(duration // MAX_ALIGNMENT_WINDOW_SECONDS) + 1
    token_count = len(tokens)
    windows: list[AlignmentWindow] = []
    for index in range(window_count):
        window_start = start + (duration * index / window_count)
        window_end = start + (duration * (index + 1) / window_count)
        token_start = token_count * index // window_count
        token_end = token_count * (index + 1) // window_count
        window_text = " ".join(tokens[token_start:token_end])
        if window_text != "":
            windows.append(
                AlignmentWindow(text=window_text, start=window_start, end=window_end)
            )
    return windows


def _segment_end(segment: TimedTranscriptSegment, start: float) -> float:
    if segment.end is not None:
        return segment.end
    if segment.duration is not None:
        return start + segment.duration
    return start


def _write_wav_clip(
    source: Path,
    destination: Path,
    window: AlignmentWindow,
) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{window.start:.3f}",
        "-t",
        f"{window.duration:.3f}",
        "-i",
        str(source),
        "-ar",
        "16000",
        "-ac",
        "1",
        str(destination),
    ]
    try:
        _ = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=FFMPEG_CLIP_TIMEOUT_SECONDS,
        )
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as error:
        raise AlignmentWorkerError(_worker_error_message(error)) from error


def _offset_segments(
    segments: list[TimedTranscriptSegment],
    offset: float,
) -> list[TimedTranscriptSegment]:
    return [
        segment.model_copy(
            update={
                "start": _offset_time(segment.start, offset),
                "end": _offset_time(segment.end, offset),
            }
        )
        for segment in segments
    ]


def _offset_time(value: float | None, offset: float) -> float | None:
    if value is None:
        return None
    return value + offset


def _worker_error_message(
    error: FileNotFoundError
    | subprocess.CalledProcessError
    | subprocess.TimeoutExpired,
) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        return f"Alignment worker failed with exit code {error.returncode}"
    if isinstance(error, subprocess.TimeoutExpired):
        return "Alignment worker timed out"
    return "Alignment worker executable was not found"


def create_alignment_backend(settings: Settings) -> TranscriptAlignmentBackend:
    match settings.alignment_engine:
        case AlignmentEngine.DISABLED:
            return DisabledTranscriptAlignmentBackend()
        case AlignmentEngine.QWEN3_FORCED_MLX:
            return Qwen3ForcedAlignmentBackend(settings)


class AlignmentWorkerError(RuntimeError):
    pass
