import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.schemas.transcript import TranscriptDocument, TranscriptSummary
from app.services.audio_service import AudioService
from app.services.storage_service import StorageService

ASR_WORKER_TIMEOUT_SECONDS = 7200


class ASREngine(Protocol):
    def transcribe(self, wav_path: Path) -> TranscriptDocument: ...


@dataclass(frozen=True, slots=True)
class FakeASREngine:
    settings: Settings

    def transcribe(self, wav_path: Path) -> TranscriptDocument:
        return TranscriptDocument(
            model=self.settings.asr_model,
            language=self.settings.asr_language,
            text=f"전사 테스트 결과: {wav_path.name}",
            segments=[],
        )


@dataclass(frozen=True, slots=True)
class Qwen3ASRMlxEngine:
    settings: Settings

    def transcribe(self, wav_path: Path) -> TranscriptDocument:
        command = [
            sys.executable,
            "-m",
            "app.workers.qwen3_asr_worker",
            "--audio",
            str(wav_path),
            "--model",
            self.settings.asr_model,
            "--language",
            self.settings.asr_language,
        ]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=ASR_WORKER_TIMEOUT_SECONDS,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise ASRWorkerError from error
        return TranscriptDocument.model_validate_json(completed.stdout)


@dataclass(frozen=True, slots=True)
class ASRService:
    storage: StorageService
    audio: AudioService
    engine: ASREngine

    def transcribe_upload(self, upload_id: str) -> TranscriptSummary:
        source = self.storage.find_upload(upload_id)
        wav_path = self.audio.convert_to_wav(source)
        transcript = self.engine.transcribe(wav_path)
        return self.storage.save_transcript(upload_id, transcript)


def create_asr_engine(settings: Settings) -> ASREngine:
    if settings.asr_engine == "fake":
        return FakeASREngine(settings)
    return Qwen3ASRMlxEngine(settings)


class ASRWorkerError(RuntimeError):
    pass
