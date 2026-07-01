from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.main_dependencies import MinutesDep, StorageDep
from app.schemas import (
    MinutesCreateRequest,
    MinutesPrompt,
    MinutesPromptUpdateRequest,
    MinutesResult,
    MinutesSummary,
)
from app.services.llm_service import LLMConfigurationError
from app.services.storage_service import ArtifactNotFoundError, InvalidArtifactIdError

router = APIRouter(tags=["minutes"])


@router.post(
    "/minutes",
    status_code=status.HTTP_201_CREATED,
)
async def create_minutes(
    payload: MinutesCreateRequest,
    minutes: MinutesDep,
) -> MinutesSummary:
    try:
        summary = await run_in_threadpool(
            minutes.create_minutes,
            payload.transcript_id,
            payload.prompt,
        )
    except ArtifactNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        ) from error
    except InvalidArtifactIdError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid transcript id",
        ) from error
    except LLMConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM is not configured",
        ) from error
    return summary


@router.get("/prompts/minutes")
async def get_minutes_prompt(storage: StorageDep) -> MinutesPrompt:
    return await run_in_threadpool(storage.load_minutes_prompt)


@router.put("/prompts/minutes")
async def save_minutes_prompt(
    payload: MinutesPromptUpdateRequest,
    storage: StorageDep,
) -> MinutesPrompt:
    return await run_in_threadpool(storage.save_minutes_prompt, payload.prompt)


@router.get("/results/{minutes_id}")
async def get_result(
    minutes_id: str,
    storage: StorageDep,
) -> MinutesResult:
    try:
        return await run_in_threadpool(storage.load_minutes, minutes_id)
    except ArtifactNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Minutes not found",
        ) from error
    except InvalidArtifactIdError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid minutes id",
        ) from error
