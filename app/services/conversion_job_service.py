from threading import RLock

from app.config import Settings
from app.schemas.conversion_job import (
    ConversionJobProgress,
    ConversionJobStatus,
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


class ConversionJobService:
    def __init__(self) -> None:
        self._lock: RLock = RLock()
        self._jobs: dict[str, ConversionJobStatus] = {}

    def create(self, upload_id: str) -> ConversionJobStatus:
        job_id = new_conversion_job_id()
        job = ConversionJobStatus(
            job_id=job_id,
            upload_id=upload_id,
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
        job = self.get(job_id)
        self._replace(
            job.model_copy(
                update={
                    "status": "running",
                    "stage": progress.stage,
                    "percent": progress.percent,
                    "message": progress.message,
                }
            )
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

    def _fail(self, job_id: str, message: str) -> None:
        self._replace(
            self.get(job_id).model_copy(
                update={
                    "status": "failed",
                    "stage": "failed",
                    "percent": 100,
                    "message": message,
                    "error": message,
                }
            )
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
