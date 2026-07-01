from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.artifact_id import (
    ARTIFACT_ID_ERROR_CODE,
    ARTIFACT_ID_ERROR_MESSAGE,
    ensure_artifact_id,
)

DEFAULT_MINUTES_PROMPT: Final = (
    "아래 음성 변환 원본을 바탕으로 공식 회의록을 작성해주세요.\n"
    "원본에 없는 내용은 추정하거나 보강하지 마세요.\n\n"
    "[회의 정보]\n"
    "- 회의명: 원본에서 확인되면 기재, 없으면 '확인 필요'\n"
    "- 일시: 원본에서 확인되면 기재, 없으면 '확인 필요'\n"
    "- 참석자: 자동 추정하지 않음. 원본에 확인된 이름이 있을 때만 기재하고, "
    "없으면 '확인 필요'\n"
    "- 화자: SPEAKER_00 같은 라벨은 참석자 이름이 아니라 발화 구분 참고로만 사용\n\n"
    "[작성 형식]\n"
    "1. 회의 개요 (2-3줄 요약)\n"
    "2. 주요 논의사항 (항목별 정리)\n"
    "3. 결정사항 (번호 매겨서)\n"
    "4. 액션 아이템 (담당자/업무내용/마감일 표 형식)\n\n"
    "액션 아이템의 담당자나 마감일이 원본에 없으면 '확인 필요'로 표시하세요."
)
MINUTES_PROMPT_FILENAME: Final = "minutes_prompt.md"
BLANK_MINUTES_PROMPT_ERROR_CODE: Final = "blank_minutes_prompt"
BLANK_MINUTES_PROMPT_ERROR_MESSAGE: Final = "minutes prompt must not be blank"


class MinutesCreateRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    transcript_id: str
    prompt: str = DEFAULT_MINUTES_PROMPT

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

    @field_validator("prompt")
    @classmethod
    def default_blank_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            return DEFAULT_MINUTES_PROMPT
        return normalized


class MinutesPrompt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    prompt: str
    source: Literal["default", "saved"]


class MinutesPromptUpdateRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    prompt: str

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise PydanticCustomError(
                BLANK_MINUTES_PROMPT_ERROR_CODE,
                BLANK_MINUTES_PROMPT_ERROR_MESSAGE,
            )
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
