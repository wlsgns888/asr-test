import wave
from io import BytesIO

from app.schemas import (
    MinutesArtifact,
    MinutesResult,
    MinutesSummary,
    TranscriptSummary,
    UploadSummary,
)
from fastapi.testclient import TestClient


def make_wav_bytes() -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


def test_pipeline_creates_transcript_and_minutes_when_fake_adapters_enabled(
    client: TestClient,
) -> None:
    # Given: a user uploads a small valid WAV recording payload.
    upload_response = client.post(
        "/uploads",
        files={"file": ("standup.wav", make_wav_bytes(), "audio/wav")},
    )
    assert upload_response.status_code == 201
    upload = UploadSummary.model_validate_json(upload_response.text)
    upload_id = upload.upload_id

    # When: the recording is transcribed and minutes are generated.
    transcript_response = client.post("/transcripts", json={"upload_id": upload_id})
    assert transcript_response.status_code == 201
    transcript = TranscriptSummary.model_validate_json(transcript_response.text)
    transcript_id = transcript.transcript_id

    minutes_response = client.post(
        "/minutes",
        json={
            "transcript_id": transcript_id,
            "template": "- 회의 개요\n- 결정사항\n- 액션아이템",
        },
    )
    assert minutes_response.status_code == 201
    minutes = MinutesSummary.model_validate_json(minutes_response.text)
    minutes_id = minutes.minutes_id

    # Then: result lookup exposes JSON and Markdown artifacts.
    result_response = client.get(f"/results/{minutes_id}")
    assert result_response.status_code == 200
    result = MinutesResult.model_validate_json(result_response.text)
    assert result.minutes_id == minutes_id
    assert result.markdown.startswith("# 회의록")
    assert result.result_json["transcript_id"] == transcript_id
    assert result.markdown_path.exists()
    assert result.json_path.exists()


def test_upload_rejects_unsupported_file_types(client: TestClient) -> None:
    # Given: a user selects a non-audio file.
    # When: the file is posted to the upload API.
    response = client.post(
        "/uploads",
        files={"file": ("notes.txt", b"not audio", "text/plain")},
    )

    # Then: the API rejects it before storage.
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported audio extension"


def test_saved_artifacts_are_json_serializable(client: TestClient) -> None:
    # Given: a generated minutes result.
    upload_response = client.post(
        "/uploads",
        files={"file": ("planning.wav", make_wav_bytes(), "audio/wav")},
    )
    transcript_response = client.post(
        "/transcripts",
        json={
            "upload_id": UploadSummary.model_validate_json(
                upload_response.text
            ).upload_id
        },
    )
    minutes_response = client.post(
        "/minutes",
        json={
            "transcript_id": TranscriptSummary.model_validate_json(
                transcript_response.text,
            ).transcript_id,
        },
    )

    # When: the JSON artifact is loaded from disk.
    minutes = MinutesSummary.model_validate_json(minutes_response.text)
    result = MinutesResult.model_validate_json(
        client.get(f"/results/{minutes.minutes_id}").text,
    )
    payload = MinutesArtifact.model_validate_json(
        result.json_path.read_text(encoding="utf-8"),
    )

    # Then: it contains the public result contract.
    assert payload.minutes_id == minutes.minutes_id
    assert payload.format == "markdown"
    assert "회의 개요" in payload.markdown
