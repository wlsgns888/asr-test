from pathlib import Path
from typing import NoReturn

import app.services.conversion_job_service as conversion_job_module
import pytest
from app.config import AlignmentEngine, AppEnv, DiarizationEngine, LLMProvider, Settings
from app.main import create_app
from app.main_dependencies import get_asr_service
from app.schemas import (
    ConversionJobProgress,
    ConversionJobStartResponse,
    ConversionJobStatus,
    UploadSummary,
)
from app.services.asr_service import ASRWorkerError
from app.services.conversion_job_service import ConversionJobService
from fastapi.testclient import TestClient
from pydantic import SecretStr
from tests.test_api_pipeline import make_wav_bytes


def test_conversion_job_exposes_progress_until_completion(tmp_path: Path) -> None:
    # Given: a user uploaded a recording and starts an audio conversion job.
    settings = Settings(
        app_env=AppEnv.TESTING,
        asr_engine="fake",
        alignment_engine=AlignmentEngine.DISABLED,
        diarization_engine=DiarizationEngine.FAKE,
        llm_provider=LLMProvider.FAKE,
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        wav_dir=tmp_path / "wav",
        transcript_dir=tmp_path / "transcripts",
        minutes_dir=tmp_path / "minutes",
    )
    with TestClient(create_app(settings)) as client:
        upload_response = client.post(
            "/uploads",
            files={"file": ("standup.wav", make_wav_bytes(), "audio/wav")},
        )
        upload = UploadSummary.model_validate_json(upload_response.text)

        # When: the frontend starts and polls the conversion job.
        start_response = client.post(
            "/conversion-jobs",
            json={"upload_id": upload.upload_id},
        )

        # Then: the API returns a job that completes with a transcript id.
        assert start_response.status_code == 202
        started = ConversionJobStartResponse.model_validate_json(start_response.text)
        status_response = client.get(f"/conversion-jobs/{started.job_id}")
        assert status_response.status_code == 200
        payload = ConversionJobStatus.model_validate_json(status_response.text)
        assert payload.status == "completed"
        assert payload.stage == "completed"
        assert payload.percent == 100
        assert payload.transcript_id is not None


def test_asr_service_reports_conversion_stages_in_order(tmp_path: Path) -> None:
    settings = Settings(
        app_env=AppEnv.TESTING,
        asr_engine="fake",
        alignment_engine=AlignmentEngine.DISABLED,
        diarization_engine=DiarizationEngine.FAKE,
        llm_provider=LLMProvider.FAKE,
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        wav_dir=tmp_path / "wav",
        transcript_dir=tmp_path / "transcripts",
        minutes_dir=tmp_path / "minutes",
    )
    with TestClient(create_app(settings)) as client:
        upload_response = client.post(
            "/uploads",
            files={"file": ("standup.wav", make_wav_bytes(), "audio/wav")},
        )
        upload = UploadSummary.model_validate_json(upload_response.text)
        service = get_asr_service(settings)
        stages: list[str] = []
        percents: list[int] = []

        def collect_progress(progress: ConversionJobProgress) -> None:
            stages.append(progress.stage)
            percents.append(progress.percent)

        _ = service.transcribe_upload(
            upload.upload_id,
            progress=collect_progress,
        )

    assert stages == [
        "loading",
        "converting",
        "recognizing",
        "diarizing",
        "aligning",
        "saving",
        "completed",
    ]
    assert percents == sorted(percents)


def test_unknown_conversion_job_returns_404() -> None:
    client = TestClient(create_app())

    response = client.get("/conversion-jobs/00000000000000000000000000000000")

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversion job not found"


def test_conversion_job_reports_failed_when_asr_worker_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        app_env=AppEnv.TESTING,
        asr_engine="fake",
        alignment_engine=AlignmentEngine.DISABLED,
        diarization_engine=DiarizationEngine.FAKE,
        llm_provider=LLMProvider.FAKE,
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        wav_dir=tmp_path / "wav",
        transcript_dir=tmp_path / "transcripts",
        minutes_dir=tmp_path / "minutes",
    )
    settings.ensure_directories()
    upload_id = "a" * 32
    _ = settings.upload_dir.joinpath(f"{upload_id}.wav").write_bytes(make_wav_bytes())

    class FailingASREngine:
        def transcribe(self, _wav_path: Path) -> NoReturn:
            raise ASRWorkerError

    def failing_engine(_settings: Settings) -> FailingASREngine:
        return FailingASREngine()

    monkeypatch.setattr(
        conversion_job_module,
        "create_asr_engine",
        failing_engine,
    )
    service = ConversionJobService()
    job = service.create(upload_id)

    service.run(job.job_id, settings)

    status = service.get(job.job_id)
    assert status.status == "failed"
    assert status.stage == "failed"
    assert status.error == "음성을 텍스트로 변환하는 데 실패했습니다."


def test_conversion_job_reports_failed_when_unexpected_worker_error_occurs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        app_env=AppEnv.TESTING,
        asr_engine="fake",
        alignment_engine=AlignmentEngine.DISABLED,
        diarization_engine=DiarizationEngine.FAKE,
        llm_provider=LLMProvider.FAKE,
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        wav_dir=tmp_path / "wav",
        transcript_dir=tmp_path / "transcripts",
        minutes_dir=tmp_path / "minutes",
    )
    settings.ensure_directories()
    upload_id = "b" * 32
    _ = settings.upload_dir.joinpath(f"{upload_id}.wav").write_bytes(make_wav_bytes())

    class BrokenASREngine:
        def transcribe(self, _wav_path: Path) -> NoReturn:
            raise ValueError

    def broken_engine(_settings: Settings) -> BrokenASREngine:
        return BrokenASREngine()

    monkeypatch.setattr(
        conversion_job_module,
        "create_asr_engine",
        broken_engine,
    )
    service = ConversionJobService()
    job = service.create(upload_id)

    service.run(job.job_id, settings)

    status = service.get(job.job_id)
    assert status.status == "failed"
    assert status.stage == "failed"
    assert status.error == "예상하지 못한 변환 오류가 발생했습니다: ValueError"


def test_conversion_job_reports_failed_when_engine_factory_crashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        app_env=AppEnv.TESTING,
        asr_engine="fake",
        alignment_engine=AlignmentEngine.DISABLED,
        diarization_engine=DiarizationEngine.FAKE,
        llm_provider=LLMProvider.FAKE,
        llm_api_key=SecretStr("test-key"),
        llm_model="fake-minutes",
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        wav_dir=tmp_path / "wav",
        transcript_dir=tmp_path / "transcripts",
        minutes_dir=tmp_path / "minutes",
    )

    def broken_engine(_settings: Settings) -> NoReturn:
        raise ValueError

    monkeypatch.setattr(
        conversion_job_module,
        "create_asr_engine",
        broken_engine,
    )
    service = ConversionJobService()
    job = service.create("c" * 32)

    service.run(job.job_id, settings)

    status = service.get(job.job_id)
    assert status.status == "failed"
    assert status.stage == "failed"
    assert status.error == "예상하지 못한 변환 오류가 발생했습니다: ValueError"
