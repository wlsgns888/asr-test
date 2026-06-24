from typing import ClassVar, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["capabilities"])


class SpeakerSeparationCapability(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    available: bool
    status: Literal["not_available"]
    technical_feasibility: Literal["possible_with_external_diarization_backend"]
    current_limitation: str
    implementation_note: str


class CapabilitiesResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    speaker_separation: SpeakerSeparationCapability


@router.get("/capabilities")
async def get_capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        speaker_separation=SpeakerSeparationCapability(
            available=False,
            status="not_available",
            technical_feasibility="possible_with_external_diarization_backend",
            current_limitation=(
                "Qwen3-ASR MLX currently returns transcript text and text "
                "segments only; it does not return speaker labels or "
                "speaker-timestamp alignment."
            ),
            implementation_note=(
                "Speaker separation is technically possible by adding a "
                "separate diarization backend and aligning its speaker turns "
                "with ASR transcript segments."
            ),
        )
    )
