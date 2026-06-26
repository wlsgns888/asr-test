from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core import PydanticCustomError

from app.artifact_id import (
    ARTIFACT_ID_ERROR_CODE,
    ARTIFACT_ID_ERROR_MESSAGE,
    ensure_artifact_id,
)


class UploadSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    upload_id: str
    filename: str
    path: Path


class TranscriptCreateRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    upload_id: str
    speaker_separation_enabled: bool = True

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


class TimedTranscriptSegment(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    text: str
    start: float | None = None
    end: float | None = None
    duration: float | None = None


class SpeakerSegment(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    speaker: str
    start: float
    end: float
    text: str = ""


class TranscriptDocument(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    model: str
    language: str
    text: str
    segments: list[str]
    timed_segments: list[TimedTranscriptSegment] = []
    speaker_segments: list[SpeakerSegment] = []
    speaker_transcript: str = ""


class TranscriptSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    transcript_id: str
    upload_id: str
    model: str
    language: str
    text: str
    speaker_transcript: str = ""
    speaker_segments: list[SpeakerSegment] = []
    path: Path
