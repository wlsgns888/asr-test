from typing import ClassVar, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.config import DiarizationEngine
from app.main_dependencies import SettingsDep

router = APIRouter(tags=["capabilities"])


class SpeakerSeparationCapability(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    available: bool
    status: Literal["configured", "requires_configuration"]
    engine: str
    model: str
    technical_feasibility: Literal["implemented_with_external_diarization_backend"]
    current_limitation: str
    implementation_note: str


class CapabilitiesResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    speaker_separation: SpeakerSeparationCapability


@router.get("/capabilities")
async def get_capabilities(settings: SettingsDep) -> CapabilitiesResponse:
    available = settings.diarization_engine is not DiarizationEngine.DISABLED
    status: Literal["configured", "requires_configuration"] = (
        "configured" if available else "requires_configuration"
    )
    enabled_prefix = "Diarization is enabled. pyannote mode still requires"
    enabled_limitation = (
        f"{enabled_prefix} a Hugging Face token with accepted model terms."
    )
    disabled_prefix = "Diarization is implemented but disabled."
    disabled_action = "Set DIARIZATION_ENGINE=pyannote and DIARIZATION_HF_TOKEN"
    disabled_terms = "after accepting the Hugging Face model terms."
    disabled_limitation = f"{disabled_prefix} {disabled_action} {disabled_terms}"
    limitation = enabled_limitation if available else disabled_limitation
    return CapabilitiesResponse(
        speaker_separation=SpeakerSeparationCapability(
            available=available,
            status=status,
            engine=settings.diarization_engine.value,
            model=settings.diarization_model,
            technical_feasibility="implemented_with_external_diarization_backend",
            current_limitation=limitation,
            implementation_note=(
                f"Speaker separation uses {settings.diarization_model} speaker turns "
                "aligned with Qwen3-ASR timestamped transcript segments."
            ),
        )
    )
