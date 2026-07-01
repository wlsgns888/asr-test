from app.config import AlignmentEngine, AppEnv, DiarizationEngine, LLMProvider, Settings
from app.main import create_app
from app.routes.capabilities import CapabilitiesResponse
from fastapi.testclient import TestClient
from pydantic import SecretStr


def test_capabilities_explain_speaker_separation_status() -> None:
    settings = Settings(
        app_env=AppEnv.TESTING,
        alignment_engine=AlignmentEngine.DISABLED,
        diarization_engine=DiarizationEngine.DISABLED,
        diarization_model="models/pyannote-speaker-diarization-community-1",
        diarization_hf_token=SecretStr(""),
        llm_provider=LLMProvider.FAKE,
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
    )
    client = TestClient(create_app(settings))

    response = client.get("/capabilities")

    assert response.status_code == 200
    body = CapabilitiesResponse.model_validate_json(response.text)
    speaker = body.speaker_separation
    assert speaker.available is False
    assert speaker.status == "requires_configuration"
    assert speaker.engine == "disabled"
    assert "models/pyannote-speaker-diarization-community-1" in (
        speaker.implementation_note
    )


def test_capabilities_explain_local_pyannote_without_token() -> None:
    settings = Settings(
        app_env=AppEnv.TESTING,
        alignment_engine=AlignmentEngine.DISABLED,
        diarization_engine=DiarizationEngine.PYANNOTE,
        diarization_model="models/pyannote-speaker-diarization-community-1",
        diarization_hf_token=SecretStr(""),
        llm_provider=LLMProvider.FAKE,
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
    )
    client = TestClient(create_app(settings))

    response = client.get("/capabilities")

    assert response.status_code == 200
    body = CapabilitiesResponse.model_validate_json(response.text)
    speaker = body.speaker_separation
    assert speaker.available is True
    assert speaker.status == "configured"
    assert "bundled local pyannote model" in speaker.current_limitation
