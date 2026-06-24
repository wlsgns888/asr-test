from typing import Annotated

from fastapi import Depends

from app.config import Settings
from app.services.asr_service import ASRService, create_asr_engine
from app.services.audio_service import AudioService
from app.services.diarization_service import create_diarization_backend
from app.services.llm_service import LLMService
from app.services.minutes_service import MinutesService
from app.services.storage_service import StorageService


def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_storage_service(settings: SettingsDep) -> StorageService:
    return StorageService(settings)


StorageDep = Annotated[StorageService, Depends(get_storage_service)]


def get_asr_service(settings: SettingsDep) -> ASRService:
    storage = StorageService(settings)
    return ASRService(
        storage=storage,
        audio=AudioService(settings),
        engine=create_asr_engine(settings),
        diarization=create_diarization_backend(settings),
    )


ASRDep = Annotated[ASRService, Depends(get_asr_service)]


def get_minutes_service(settings: SettingsDep) -> MinutesService:
    return MinutesService(
        storage=StorageService(settings),
        llm=LLMService(settings),
    )


MinutesDep = Annotated[MinutesService, Depends(get_minutes_service)]
