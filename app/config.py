from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Final
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ASR_MODEL: Final = "models/Qwen3-ASR-0.6B-4bit"
DEFAULT_ALIGNMENT_MODEL: Final = "models/Qwen3-ForcedAligner-0.6B-8bit"
DEFAULT_DIARIZATION_MODEL: Final = "models/pyannote-speaker-diarization-community-1"
DEFAULT_LLM_BASE_URL: Final = "https://api.z.ai/api/paas/v4"
FAKE_ADAPTER_ERROR_CODE: Final = "fake_adapter_environment"
FAKE_ADAPTER_ERROR_MESSAGE: Final = "fake adapters require APP_ENV=testing"
PRODUCTION_PROVIDER_ERROR_CODE: Final = "production_llm_provider"
PRODUCTION_PROVIDER_ERROR_MESSAGE: Final = "production requires LLM_PROVIDER=internal"
PRODUCTION_BASE_URL_ERROR_CODE: Final = "production_llm_base_url"
PRODUCTION_BASE_URL_ERROR_MESSAGE: Final = (
    "production requires an internal LLM_BASE_URL"
)
EXTERNAL_LLM_HOST_SUFFIXES: Final = (
    "api.z.ai",
    "z.ai",
    "api.openai.com",
    "openai.com",
)


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LLMProvider(StrEnum):
    ZAI = "zai"
    INTERNAL = "internal"
    FAKE = "fake"


class DiarizationEngine(StrEnum):
    DISABLED = "disabled"
    FAKE = "fake"
    PYANNOTE = "pyannote"


class AlignmentEngine(StrEnum):
    DISABLED = "disabled"
    QWEN3_FORCED_MLX = "qwen3_forced_mlx"


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    asr_engine: str = "qwen3_asr_mlx"
    asr_model: str = DEFAULT_ASR_MODEL
    asr_language: str = "ko"
    alignment_engine: AlignmentEngine = AlignmentEngine.QWEN3_FORCED_MLX
    alignment_model: str = DEFAULT_ALIGNMENT_MODEL
    diarization_engine: DiarizationEngine = DiarizationEngine.DISABLED
    diarization_model: str = DEFAULT_DIARIZATION_MODEL
    diarization_hf_token: SecretStr = Field(default=SecretStr(""))
    llm_provider: LLMProvider = LLMProvider.ZAI
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_model: str = ""
    data_dir: Path = Path("./data")
    upload_dir: Path = Path("./data/uploads")
    wav_dir: Path = Path("./data/wav")
    transcript_dir: Path = Path("./data/transcripts")
    minutes_dir: Path = Path("./data/minutes")

    @model_validator(mode="after")
    def reject_fake_adapters_outside_testing(self) -> "Settings":
        if self.app_env is AppEnv.TESTING:
            return self
        if (
            self.asr_engine == "fake"
            or self.llm_provider is LLMProvider.FAKE
            or self.diarization_engine is DiarizationEngine.FAKE
        ):
            raise PydanticCustomError(
                FAKE_ADAPTER_ERROR_CODE,
                FAKE_ADAPTER_ERROR_MESSAGE,
            )
        if (
            self.app_env is AppEnv.PRODUCTION
            and self.llm_provider is not LLMProvider.INTERNAL
        ):
            raise PydanticCustomError(
                PRODUCTION_PROVIDER_ERROR_CODE,
                PRODUCTION_PROVIDER_ERROR_MESSAGE,
            )
        if self.app_env is AppEnv.PRODUCTION and is_external_llm_base_url(
            self.llm_base_url
        ):
            raise PydanticCustomError(
                PRODUCTION_BASE_URL_ERROR_CODE,
                PRODUCTION_BASE_URL_ERROR_MESSAGE,
            )
        return self

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.upload_dir,
            self.wav_dir,
            self.transcript_dir,
            self.minutes_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def is_external_llm_base_url(value: str) -> bool:
    host = urlparse(value).hostname
    if host is None:
        return False
    normalized_host = host.lower().rstrip(".")
    return any(
        normalized_host == suffix or normalized_host.endswith(f".{suffix}")
        for suffix in EXTERNAL_LLM_HOST_SUFFIXES
    )
