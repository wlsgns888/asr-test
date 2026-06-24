from pathlib import Path

from app.config import AppEnv, LLMProvider, Settings
from pydantic import SecretStr


def test_settings_separates_development_and_internal_llm() -> None:
    # Given: an internal deployment environment.
    settings = Settings(
        app_env=AppEnv.PRODUCTION,
        llm_provider=LLMProvider.INTERNAL,
        llm_base_url="https://internal-llm.company.local/v1",
        llm_api_key=SecretStr("internal-key"),
        llm_model="internal-model-name",
        data_dir=Path("data"),
    )

    # When: the settings are read by service code.
    # Then: provider-specific values are environment driven, not hardcoded.
    assert settings.llm_provider is LLMProvider.INTERNAL
    assert str(settings.llm_base_url) == "https://internal-llm.company.local/v1"
    assert settings.llm_api_key.get_secret_value() == "internal-key"
    assert settings.llm_model == "internal-model-name"
