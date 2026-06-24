from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.main_dependencies import ASRDep
from app.schemas import TranscriptCreateRequest, TranscriptSummary
from app.services.audio_service import AudioConversionError
from app.services.diarization_service import (
    DiarizationConfigurationError,
    DiarizationWorkerError,
)
from app.services.storage_service import ArtifactNotFoundError, InvalidArtifactIdError

router = APIRouter(tags=["transcripts"])


@router.post(
    "/transcripts",
    status_code=status.HTTP_201_CREATED,
)
async def create_transcript(
    payload: TranscriptCreateRequest,
    asr: ASRDep,
) -> TranscriptSummary:
    try:
        return await run_in_threadpool(asr.transcribe_upload, payload.upload_id)
    except ArtifactNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        ) from error
    except InvalidArtifactIdError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid upload id",
        ) from error
    except AudioConversionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Audio conversion failed",
        ) from error
    except DiarizationConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diarization is not configured",
        ) from error
    except DiarizationWorkerError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Diarization worker failed",
        ) from error
