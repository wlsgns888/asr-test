from collections.abc import Iterator
from pathlib import Path

import pytest
from app.config import (
    AlignmentEngine,
    AppEnv,
    DiarizationEngine,
    LLMProvider,
    Settings,
)
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import SecretStr


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env=AppEnv.TESTING,
        asr_engine="fake",
        asr_model="mlx-community/Qwen3-ASR-0.6B-4bit",
        asr_language="ko",
        alignment_engine=AlignmentEngine.DISABLED,
        diarization_engine=DiarizationEngine.FAKE,
        llm_provider=LLMProvider.FAKE,
        llm_base_url="https://api.z.ai/api/paas/v4",
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        wav_dir=tmp_path / "wav",
        transcript_dir=tmp_path / "transcripts",
        minutes_dir=tmp_path / "minutes",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
