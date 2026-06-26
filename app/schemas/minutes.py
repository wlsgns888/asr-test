from pathlib import Path
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.artifact_id import (
    ARTIFACT_ID_ERROR_CODE,
    ARTIFACT_ID_ERROR_MESSAGE,
    ensure_artifact_id,
)

DEFAULT_SUMMARY_PROMPT: Final = (
    "회의 내용을 경영진과 실무자가 바로 활용할 수 있는 전문 회의록으로 "
    "요약하세요.\n"
    "핵심 논의, 결정사항, 액션아이템(담당자/기한이 언급된 경우 포함), "
    "리스크/이슈, 후속 확인사항을 명확히 구분하세요.\n"
    "발언의 뉘앙스를 유지하되 중복 표현은 정리하고, 근거가 불명확한 "
    '내용은 "확인 필요"로 표시하세요.'
)


class MinutesCreateRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    transcript_id: str
    summary_prompt: str = DEFAULT_SUMMARY_PROMPT
    template: str = (
        "- 회의 개요\n- 주요 논의사항\n- 결정사항\n- 액션아이템\n- 후속 확인사항"
    )

    @field_validator("transcript_id")
    @classmethod
    def validate_transcript_id(cls, value: str) -> str:
        try:
            return ensure_artifact_id(value)
        except RuntimeError as error:
            raise PydanticCustomError(
                ARTIFACT_ID_ERROR_CODE,
                ARTIFACT_ID_ERROR_MESSAGE,
            ) from error

    @field_validator("summary_prompt")
    @classmethod
    def default_blank_summary_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            return DEFAULT_SUMMARY_PROMPT
        return normalized


class MinutesSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    minutes_id: str
    transcript_id: str
    markdown_path: Path
    json_path: Path


class MinutesArtifact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    minutes_id: str
    transcript_id: str
    format: str
    markdown: str


class MinutesResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, populate_by_name=True)

    minutes_id: str
    transcript_id: str
    markdown: str
    markdown_path: Path
    json_path: Path
    result_json: dict[str, str] = Field(alias="json")
