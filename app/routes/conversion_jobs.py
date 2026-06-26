from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.artifact_id import ensure_artifact_id
from app.config import Settings
from app.main_dependencies import SettingsDep, StorageDep
from app.schemas import (
    ConversionJobCreateRequest,
    ConversionJobStartResponse,
    ConversionJobStatus,
)
from app.services.conversion_job_service import (
    ConversionJobNotFoundError,
    ConversionJobService,
)
from app.services.storage_service import ArtifactNotFoundError, InvalidArtifactIdError

router = APIRouter(tags=["conversion-jobs"])
conversion_jobs = ConversionJobService()


@router.post(
    "/conversion-jobs",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_conversion_job(
    payload: ConversionJobCreateRequest,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    storage: StorageDep,
) -> ConversionJobStartResponse:
    try:
        _ = storage.find_upload(payload.upload_id)
    except ArtifactNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        ) from error
    job = conversion_jobs.create(
        payload.upload_id,
        speaker_separation_enabled=payload.speaker_separation_enabled,
    )
    if settings.app_env.value == "testing":
        await run_in_threadpool(conversion_jobs.run, job.job_id, settings)
    else:
        background_tasks.add_task(_run_conversion_job, job.job_id, settings)
    return ConversionJobStartResponse(
        job_id=job.job_id,
        status_url=f"/conversion-jobs/{job.job_id}",
    )


@router.get("/conversion-jobs/{job_id}")
async def get_conversion_job(job_id: str) -> ConversionJobStatus:
    try:
        safe_job_id = ensure_artifact_id(job_id)
        return conversion_jobs.get(safe_job_id)
    except InvalidArtifactIdError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid conversion job id",
        ) from error
    except ConversionJobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversion job not found",
        ) from error


def _run_conversion_job(job_id: str, settings: Settings) -> None:
    conversion_jobs.run(job_id, settings)
