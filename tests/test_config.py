import subprocess
from pathlib import Path
from typing import NotRequired, TypedDict, Unpack

import pytest
from app.config import (
    AppEnv,
    DiarizationEngine,
    LLMProvider,
    Settings,
)
from app.services.diarization_service import PyannoteDiarizationBackend
from pydantic import SecretStr


class RunKeywordArgs(TypedDict):
    check: bool
    capture_output: bool
    text: bool
    timeout: int
    env: dict[str, str]
    input: NotRequired[str]


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


def test_local_pyannote_model_does_not_require_hugging_face_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    local_model = tmp_path / "pyannote-local"
    local_model.mkdir()
    audio = tmp_path / "audio.wav"
    _ = audio.write_bytes(b"RIFF")
    settings = Settings(
        app_env=AppEnv.TESTING,
        asr_engine="fake",
        diarization_engine=DiarizationEngine.PYANNOTE,
        diarization_model=str(local_model),
        diarization_hf_token=SecretStr(""),
        llm_provider=LLMProvider.FAKE,
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
    )
    captured_env: dict[str, str] = {}

    def fake_run(
        command: list[str],
        **kwargs: Unpack[RunKeywordArgs],
    ) -> subprocess.CompletedProcess[str]:
        captured_env.update(kwargs["env"])
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='[{"speaker":"SPEAKER_00","start":0.0,"end":1.0}]',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    segments = PyannoteDiarizationBackend(settings).diarize(audio)

    assert segments[0].speaker == "SPEAKER_00"
    assert "PYANNOTE_AUTH_TOKEN" not in captured_env
