from app.main import create_app
from app.routes.capabilities import CapabilitiesResponse
from fastapi.testclient import TestClient


def test_capabilities_explain_speaker_separation_status() -> None:
    client = TestClient(create_app())

    response = client.get("/capabilities")

    assert response.status_code == 200
    body = CapabilitiesResponse.model_validate_json(response.text)
    speaker = body.speaker_separation
    assert speaker.available is False
    assert speaker.status == "requires_configuration"
    assert speaker.engine == "disabled"
    assert "pyannote/speaker-diarization-community-1" in speaker.implementation_note
