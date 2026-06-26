from threading import RLock
from time import perf_counter
from typing import Final

from app.config import Settings
from app.schemas.conversion_job import (
    ConversionJobProgress,
    ConversionJobStage,
    ConversionJobStatus,
    ConversionJobTiming,
    new_conversion_job_id,
)
from app.services.alignment_service import (
    AlignmentWorkerError,
    create_alignment_backend,
)
from app.services.asr_service import ASRService, ASRWorkerError, create_asr_engine
from app.services.audio_service import AudioConversionError, AudioService
from app.services.diarization_service import (
    DiarizationConfigurationError,
    DiarizationWorkerError,
    create_diarization_backend,
)
from app.services.storage_service import ArtifactNotFoundError, StorageService


class ConversionJobNotFoundError(RuntimeError):
    pass


STAGE_TIMING_LABELS: Final[tuple[tuple[ConversionJobStage, str], ...]] = (
    ("loading", "업로드 확인"),
    ("converting", "WAV 변환"),
    ("recognizing", "음성 인식"),
    ("diarizing", "화자 구분"),
    ("aligning", "화자 시간 정렬"),
    ("saving", "결과 저장"),
)


class ConversionJobService:
    def __init__(self) -> None:
        self._lock: RLock = RLock()
        self._jobs: dict[str, ConversionJobStatus] = {}
        self._stage_started_at: dict[str, float] = {}

    def create(
        self,
        upload_id: str,
        speaker_separation_enabled: bool = True,
    ) -> ConversionJobStatus:
        job_id = new_conversion_job_id()
        job = ConversionJobStatus(
            job_id=job_id,
            upload_id=upload_id,
            speaker_separation_enabled=speaker_separation_enabled,
            status="queued",
            stage="queued",
            percent=0,
            message="변환 작업을 준비 중입니다.",
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> ConversionJobStatus:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ConversionJobNotFoundError
        return job

    def update_progress(
        self,
        job_id: str,
        progress: ConversionJobProgress,
    ) -> None:
        now = perf_counter()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ConversionJobNotFoundError
            timings = job.timings
            if progress.stage != job.stage:
                started_at = self._stage_started_at.get(job_id)
                timings = _append_stage_timing(job, started_at, now)
                self._stage_started_at[job_id] = now
            elif job_id not in self._stage_started_at:
                self._stage_started_at[job_id] = now
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": "running",
                    "stage": progress.stage,
                    "percent": progress.percent,
                    "message": progress.message,
                    "timings": timings,
                }
            )

    def run(self, job_id: str, settings: Settings) -> None:
        job = self.get(job_id)
        self.update_progress(
            job_id,
            ConversionJobProgress(
                stage="loading",
                percent=3,
                message="변환 작업을 시작했습니다.",
            ),
        )
        try:
            service = ASRService(
                storage=StorageService(settings),
                audio=AudioService(settings),
                engine=create_asr_engine(settings),
                diarization=create_diarization_backend(settings),
                alignment=create_alignment_backend(settings),
            )
            transcript = service.transcribe_upload(
                job.upload_id,
                speaker_separation_enabled=job.speaker_separation_enabled,
                progress=lambda progress: self.update_progress(job_id, progress),
            )
        except (
            ArtifactNotFoundError,
            AudioConversionError,
            ASRWorkerError,
            DiarizationConfigurationError,
            DiarizationWorkerError,
            AlignmentWorkerError,
        ) as error:
            self._fail(job_id, _job_error_message(error))
            return
        except Exception as error:  # noqa: BLE001
            self._fail(job_id, _unexpected_job_error_message(error))
            return
        self._replace(
            self.get(job_id).model_copy(
                update={
                    "status": "completed",
                    "stage": "completed",
                    "percent": 100,
                    "message": "음성 변환이 완료됐습니다.",
                    "transcript_id": transcript.transcript_id,
                    "transcript": transcript,
                }
            )
        )
        with self._lock:
            _ = self._stage_started_at.pop(job_id, None)

    def _fail(self, job_id: str, message: str) -> None:
        now = perf_counter()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ConversionJobNotFoundError
            timings = _append_stage_timing(
                job,
                self._stage_started_at.get(job_id),
                now,
            )
            _ = self._stage_started_at.pop(job_id, None)
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": "failed",
                    "stage": "failed",
                    "percent": 100,
                    "message": message,
                    "timings": timings,
                    "error": message,
                }
            )

    def _replace(self, job: ConversionJobStatus) -> None:
        with self._lock:
            self._jobs[job.job_id] = job


def _job_error_message(error: RuntimeError) -> str:
    messages = (
        (ArtifactNotFoundError, "업로드 파일을 찾을 수 없습니다."),
        (AudioConversionError, "음성 파일 변환에 실패했습니다."),
        (ASRWorkerError, "음성을 텍스트로 변환하는 데 실패했습니다."),
        (DiarizationConfigurationError, "화자 구분 설정이 필요합니다."),
        (DiarizationWorkerError, "화자 구분 처리에 실패했습니다."),
        (AlignmentWorkerError, "텍스트와 화자 시간 정렬에 실패했습니다."),
    )
    for error_type, message in messages:
        if isinstance(error, error_type):
            return message
    return f"변환 작업에 실패했습니다: {type(error).__name__}"


def _unexpected_job_error_message(error: Exception) -> str:
    return f"예상하지 못한 변환 오류가 발생했습니다: {type(error).__name__}"


def _stage_timing_label(stage: ConversionJobStage) -> str | None:
    for timing_stage, label in STAGE_TIMING_LABELS:
        if stage == timing_stage:
            return label
    return None


def _append_stage_timing(
    job: ConversionJobStatus,
    started_at: float | None,
    now: float,
) -> list[ConversionJobTiming]:
    label = _stage_timing_label(job.stage)
    if label is None or started_at is None:
        return job.timings
    return [
        *job.timings,
        ConversionJobTiming(
            stage=job.stage,
            label=label,
            duration_seconds=round(now - started_at, 6),
        ),
    ]
