from typing import ClassVar, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.config import DiarizationEngine
from app.main_dependencies import SettingsDep
from app.services.diarization_service import is_local_model_reference

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
    local_model = is_local_model_reference(settings.diarization_model)
    enabled_limitation = (
        "Diarization is enabled with the bundled local pyannote model."
        if local_model
        else (
            "Diarization is enabled with a remote Hugging Face model and still "
            "requires a token with accepted model terms."
        )
    )
    disabled_prefix = "Diarization is implemented but disabled."
    disabled_action = "Set DIARIZATION_ENGINE=pyannote"
    disabled_terms = "to use the bundled local pyannote model without a token."
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
