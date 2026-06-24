from pathlib import Path

import pytest
from app.artifact_id import InvalidArtifactIdError
from app.config import AppEnv, LLMProvider, Settings
from app.schemas import UploadSummary
from app.services.storage_service import ArtifactNotFoundError, StorageService
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError


def test_upload_filename_path_traversal_is_sanitized(client: TestClient) -> None:
    # Given: a filename attempts path traversal.
    response = client.post(
        "/uploads",
        files={"file": ("../secret.wav", b"RIFF....WAVEfmt ", "audio/wav")},
    )
    assert response.status_code == 201

    # When: the stored upload summary is parsed.
    upload = UploadSummary.model_validate_json(response.text)

    # Then: the artifact remains inside the configured upload directory.
    assert Path(upload.path).name.endswith(".wav")
    assert ".." not in Path(upload.path).parts


def test_fake_adapters_are_rejected_outside_testing() -> None:
    # Given: production settings attempt to use fake adapters.
    # When/Then: settings construction rejects the unsafe configuration.
    with pytest.raises(ValidationError):
        _ = Settings(
            app_env=AppEnv.PRODUCTION,
            asr_engine="fake",
            llm_provider=LLMProvider.FAKE,
            llm_api_key=SecretStr("test-key"),
            llm_model="fake",
        )


def test_artifact_ids_reject_path_traversal(settings: Settings) -> None:
    # Given: storage receives traversal-shaped artifact IDs.
    storage = StorageService(settings)

    # When/Then: every artifact lookup rejects path separators.
    with pytest.raises(InvalidArtifactIdError):
        _ = storage.find_upload("../outside")
    with pytest.raises(InvalidArtifactIdError):
        _ = storage.load_transcript("../outside")
    with pytest.raises(InvalidArtifactIdError):
        _ = storage.load_minutes("../outside")


def test_missing_valid_artifact_id_is_not_found(settings: Settings) -> None:
    # Given: a syntactically valid artifact id does not exist.
    storage = StorageService(settings)

    # When/Then: storage reports not found rather than escaping directories.
    with pytest.raises(ArtifactNotFoundError):
        _ = storage.find_upload("0" * 32)


def test_route_artifact_ids_reject_path_traversal(client: TestClient) -> None:
    # Given: API callers submit traversal-shaped artifact IDs.
    transcript_response = client.post("/transcripts", json={"upload_id": "../outside"})
    minutes_response = client.post("/minutes", json={"transcript_id": "../outside"})

    # When/Then: request parsing rejects both before storage access.
    assert transcript_response.status_code == 422
    assert minutes_response.status_code == 422


def test_production_rejects_external_llm_provider() -> None:
    # Given: production settings attempt to use the development z.ai provider.
    # When/Then: settings construction rejects the external provider.
    with pytest.raises(ValidationError):
        _ = Settings(
            app_env=AppEnv.PRODUCTION,
            llm_provider=LLMProvider.ZAI,
            llm_api_key=SecretStr("test-key"),
            llm_model="glm-test",
        )


def test_production_rejects_default_external_base_url() -> None:
    # Given: production settings use internal provider but keep z.ai URL.
    # When/Then: settings construction rejects the external base URL.
    with pytest.raises(ValidationError):
        _ = Settings(
            app_env=AppEnv.PRODUCTION,
            llm_provider=LLMProvider.INTERNAL,
            llm_api_key=SecretStr("test-key"),
            llm_model="internal-model",
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.z.ai/api/paas/v4/",
        "HTTPS://api.z.ai/api/paas/v4",
        "https://api.openai.com/v1",
    ],
)
def test_production_rejects_known_external_base_url_variants(base_url: str) -> None:
    # Given: production settings use an external AI host variant.
    # When/Then: settings construction rejects the external base URL.
    with pytest.raises(ValidationError):
        _ = Settings(
            app_env=AppEnv.PRODUCTION,
            llm_provider=LLMProvider.INTERNAL,
            llm_base_url=base_url,
            llm_api_key=SecretStr("test-key"),
            llm_model="internal-model",
        )
