from typing import ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.artifact_id import (
    ARTIFACT_ID_ERROR_CODE,
    ARTIFACT_ID_ERROR_MESSAGE,
    ensure_artifact_id,
)
from app.schemas.transcript import TranscriptSummary

ConversionJobStatusValue = Literal["queued", "running", "completed", "failed"]
ConversionJobStage = Literal[
    "queued",
    "loading",
    "converting",
    "recognizing",
    "diarizing",
    "aligning",
    "saving",
    "completed",
    "failed",
]


class ConversionJobCreateRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    upload_id: str

    @field_validator("upload_id")
    @classmethod
    def validate_upload_id(cls, value: str) -> str:
        try:
            return ensure_artifact_id(value)
        except RuntimeError as error:
            raise PydanticCustomError(
                ARTIFACT_ID_ERROR_CODE,
                ARTIFACT_ID_ERROR_MESSAGE,
            ) from error


class ConversionJobStartResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    job_id: str
    status_url: str


class ConversionJobProgress(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    stage: ConversionJobStage
    percent: int = Field(ge=0, le=100)
    message: str


class ConversionJobStatus(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    job_id: str
    upload_id: str
    status: ConversionJobStatusValue
    stage: ConversionJobStage
    percent: int = Field(ge=0, le=100)
    message: str
    transcript_id: str | None = None
    transcript: TranscriptSummary | None = None
    error: str | None = None


def new_conversion_job_id() -> str:
    return uuid4().hex
