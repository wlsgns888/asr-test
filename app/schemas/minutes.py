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
    "너는 전문 회의록 작성자다. 아래 회의 녹취록을 바탕으로 회사 내부 공유용 "
    "회의록을 작성해줘.\n\n"
    "목표:\n"
    "- 핵심 내용을 빠짐없이 정리한다.\n"
    "- 불필요한 잡담, 반복 표현, 말실수는 제거한다.\n"
    "- 발언 내용을 왜곡하지 않고, 추측은 하지 않는다.\n"
    "- 결정사항과 실행 항목이 명확히 보이게 작성한다.\n"
    "- 회사 내부 문서에 어울리는 간결하고 전문적인 톤으로 작성한다.\n\n"
    "회의록 형식:\n"
    "1. 회의 개요\n"
    "- 회의명:\n\n"
    "2. 회의 목적\n"
    "- 이번 회의가 열린 배경과 목적을 2~3문장으로 정리\n\n"
    "3. 주요 논의 내용\n"
    "주제별로 구분해서 정리:\n"
    "- 논의 주제\n"
    "- 핵심 내용\n"
    "- 주요 의견\n"
    "- 쟁점 또는 우려사항\n\n"
    "4. 결정사항\n"
    "- 회의에서 확정된 내용을 bullet point로 정리\n"
    "- 확정되지 않은 내용은 “논의 필요”로 구분\n\n"
    "5. 실행 항목\n"
    "아래 표 형식으로 정리:\n"
    "| 할 일 | 담당자 | 기한 | 비고 |\n"
    "|---|---|---|---|\n\n"
    "6. 리스크 및 이슈\n"
    "- 일정, 비용, 인력, 커뮤니케이션, 의사결정 관련 리스크 정리\n\n"
    "7. 후속 논의 필요 사항\n"
    "- 다음 회의나 별도 논의가 필요한 항목 정리\n\n"
    "8. 요약\n"
    "- 전체 회의 내용을 5줄 이내로 요약\n\n"
    "주의사항:\n"
    "- 녹취록에 없는 내용은 임의로 추가하지 말 것\n"
    "- 담당자나 기한이 명확하지 않으면 “미정”으로 표시\n"
    "- 애매한 표현은 “확인 필요”로 표시\n"
    "- 발언자 이름이 있는 경우, 중요한 의견에는 발언자를 함께 표시\n"
    "- 너무 장황하지 않게, 실제 회사에서 바로 공유 가능한 회의록으로 작성"
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
