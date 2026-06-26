import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.schemas.conversion_job import ConversionJobProgress, ConversionJobStage
from app.schemas.transcript import (
    SpeakerSegment,
    TimedTranscriptSegment,
    TranscriptDocument,
    TranscriptSummary,
)
from app.services.alignment_service import TranscriptAlignmentBackend
from app.services.audio_service import AudioService
from app.services.diarization_service import (
    DiarizationBackend,
    apply_speaker_labels,
)
from app.services.storage_service import StorageService

ASR_WORKER_TIMEOUT_SECONDS = 7200


class ProgressReporter(Protocol):
    def __call__(self, progress: ConversionJobProgress) -> None: ...


class ASREngine(Protocol):
    def transcribe(self, wav_path: Path) -> TranscriptDocument: ...


@dataclass(frozen=True, slots=True)
class FakeASREngine:
    settings: Settings

    def transcribe(self, wav_path: Path) -> TranscriptDocument:
        return TranscriptDocument(
            model=self.settings.asr_model,
            language=self.settings.asr_language,
            text=f"변환 테스트 결과: {wav_path.name}",
            segments=[
                "안녕하세요 오늘 회의 시작하겠습니다.",
                "네 액션아이템을 정리하겠습니다.",
            ],
            timed_segments=[
                TimedTranscriptSegment(
                    text="안녕하세요 오늘 회의 시작하겠습니다.",
                    start=0.0,
                    end=1.8,
                ),
                TimedTranscriptSegment(
                    text="네 액션아이템을 정리하겠습니다.",
                    start=2.1,
                    end=3.7,
                ),
            ],
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
    diarization: DiarizationBackend
    alignment: TranscriptAlignmentBackend

    def transcribe_upload(
        self,
        upload_id: str,
        speaker_separation_enabled: bool = True,
        progress: ProgressReporter | None = None,
    ) -> TranscriptSummary:
        _report_progress(progress, "loading", 5, "업로드 파일을 확인하고 있습니다.")
        source = self.storage.find_upload(upload_id)
        _report_progress(
            progress, "converting", 15, "음성을 처리 가능한 WAV로 변환 중입니다."
        )
        wav_path = self.audio.convert_to_wav(source)
        _report_progress(progress, "recognizing", 35, "음성을 텍스트로 변환 중입니다.")
        transcript = self.engine.transcribe(wav_path)
        speaker_turns: list[SpeakerSegment] = []
        if speaker_separation_enabled:
            _report_progress(progress, "diarizing", 60, "화자를 구분하고 있습니다.")
            speaker_turns = self.diarization.diarize(wav_path)
            if len(speaker_turns) > 0:
                _report_progress(
                    progress, "aligning", 78, "텍스트와 화자 시간을 맞추고 있습니다."
                )
                transcript = self.alignment.align(wav_path, transcript)
        _report_progress(progress, "saving", 92, "변환 결과를 저장하고 있습니다.")
        transcript = apply_speaker_labels(transcript, speaker_turns)
        summary = self.storage.save_transcript(upload_id, transcript)
        _report_progress(progress, "completed", 100, "음성 변환이 완료됐습니다.")
        return summary


def create_asr_engine(settings: Settings) -> ASREngine:
    if settings.asr_engine == "fake":
        return FakeASREngine(settings)
    return Qwen3ASRMlxEngine(settings)


class ASRWorkerError(RuntimeError):
    pass


def _report_progress(
    reporter: ProgressReporter | None,
    stage: ConversionJobStage,
    percent: int,
    message: str,
) -> None:
    if reporter is None:
        return
    reporter(
        ConversionJobProgress(
            stage=stage,
            percent=percent,
            message=message,
        )
    )
