import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from app.config import AlignmentEngine, Settings
from app.schemas.transcript import TimedTranscriptSegment, TranscriptDocument

ALIGNMENT_WORKER_TIMEOUT_SECONDS = 7200


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
                input=transcript.text,
                text=True,
                timeout=ALIGNMENT_WORKER_TIMEOUT_SECONDS,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise AlignmentWorkerError from error
        segments = TypeAdapter(list[TimedTranscriptSegment]).validate_json(
            completed.stdout
        )
        if len(segments) == 0:
            return transcript
        return transcript.model_copy(
            update={
                "timed_segments": segments,
                "segments": [segment.text for segment in segments],
            }
        )


def create_alignment_backend(settings: Settings) -> TranscriptAlignmentBackend:
    match settings.alignment_engine:
        case AlignmentEngine.DISABLED:
            return DisabledTranscriptAlignmentBackend()
        case AlignmentEngine.QWEN3_FORCED_MLX:
            return Qwen3ForcedAlignmentBackend(settings)


class AlignmentWorkerError(RuntimeError):
    pass
