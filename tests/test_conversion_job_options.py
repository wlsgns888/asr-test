from app.schemas import ConversionJobStartResponse, ConversionJobStatus, UploadSummary
from fastapi.testclient import TestClient
from tests.test_api_pipeline import make_wav_bytes


def test_conversion_job_skips_speaker_stages_when_speaker_separation_disabled(
    client: TestClient,
) -> None:
    # Given: a user uploaded a recording and does not want speaker separation.
    upload_response = client.post(
        "/uploads",
        files={"file": ("standup.wav", make_wav_bytes(), "audio/wav")},
    )
    upload = UploadSummary.model_validate_json(upload_response.text)

    # When: the frontend starts the conversion job with speaker separation disabled.
    start_response = client.post(
        "/conversion-jobs",
        json={
            "upload_id": upload.upload_id,
            "speaker_separation_enabled": False,
        },
    )

    # Then: the completed transcript has no speaker output or speaker timings.
    assert start_response.status_code == 202
    started = ConversionJobStartResponse.model_validate_json(start_response.text)
    status_response = client.get(started.status_url)
    payload = ConversionJobStatus.model_validate_json(status_response.text)
    assert payload.status == "completed"
    assert payload.transcript is not None
    assert payload.transcript.speaker_transcript == ""
    assert payload.transcript.speaker_segments == []
    assert {timing.stage for timing in payload.timings}.isdisjoint(
        {"diarizing", "aligning"}
    )


def test_completed_conversion_job_includes_stage_timing_breakdown(
    client: TestClient,
) -> None:
    # Given: a user uploaded a recording for the default conversion pipeline.
    upload_response = client.post(
        "/uploads",
        files={"file": ("standup.wav", make_wav_bytes(), "audio/wav")},
    )
    upload = UploadSummary.model_validate_json(upload_response.text)

    # When: the conversion job completes.
    start_response = client.post(
        "/conversion-jobs",
        json={"upload_id": upload.upload_id},
    )

    # Then: status exposes UI-ready duration rows for each completed stage.
    assert start_response.status_code == 202
    started = ConversionJobStartResponse.model_validate_json(start_response.text)
    status_response = client.get(started.status_url)
    payload = ConversionJobStatus.model_validate_json(status_response.text)
    assert payload.status == "completed"
    assert [(timing.stage, timing.label) for timing in payload.timings] == [
        ("loading", "업로드 확인"),
        ("converting", "WAV 변환"),
        ("recognizing", "음성 인식"),
        ("diarizing", "화자 구분"),
        ("aligning", "화자 시간 정렬"),
        ("saving", "결과 저장"),
    ]
    assert all(timing.duration_seconds >= 0 for timing in payload.timings)
