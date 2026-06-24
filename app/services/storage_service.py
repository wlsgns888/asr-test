from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import orjson
from fastapi import UploadFile

from app.artifact_id import InvalidArtifactIdError, ensure_artifact_id
from app.config import Settings
from app.schemas.minutes import MinutesArtifact, MinutesResult, MinutesSummary
from app.schemas.transcript import TranscriptDocument, TranscriptSummary, UploadSummary

SUPPORTED_AUDIO_EXTENSIONS = frozenset({".mp3", ".m4a", ".wav"})


class UnsupportedAudioError(RuntimeError):
    pass


class ArtifactNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StorageService:
    settings: Settings

    async def save_upload(self, upload_file: UploadFile) -> UploadSummary:
        filename = Path(upload_file.filename or "").name
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_AUDIO_EXTENSIONS:
            raise UnsupportedAudioError

        self.settings.ensure_directories()
        upload_id = uuid4().hex
        destination = self.settings.upload_dir / f"{upload_id}{extension}"
        content = await upload_file.read()
        _ = destination.write_bytes(content)
        return UploadSummary(upload_id=upload_id, filename=filename, path=destination)

    def find_upload(self, upload_id: str) -> Path:
        safe_upload_id = ensure_artifact_id(upload_id)
        matches = list(self.settings.upload_dir.glob(f"{safe_upload_id}.*"))
        if len(matches) != 1:
            raise ArtifactNotFoundError
        return matches[0]

    def save_transcript(
        self,
        upload_id: str,
        transcript: TranscriptDocument,
    ) -> TranscriptSummary:
        self.settings.ensure_directories()
        transcript_id = uuid4().hex
        path = self.settings.transcript_dir / f"{transcript_id}.json"
        _ = path.write_bytes(orjson.dumps(transcript.model_dump(mode="json")))
        return TranscriptSummary(
            transcript_id=transcript_id,
            upload_id=upload_id,
            model=transcript.model,
            language=transcript.language,
            text=transcript.text,
            speaker_transcript=transcript.speaker_transcript,
            speaker_segments=transcript.speaker_segments,
            path=path,
        )

    def load_transcript(self, transcript_id: str) -> TranscriptDocument:
        safe_transcript_id = ensure_artifact_id(transcript_id)
        path = self.settings.transcript_dir / f"{safe_transcript_id}.json"
        if not path.exists():
            raise ArtifactNotFoundError
        return TranscriptDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def save_minutes(
        self,
        transcript_id: str,
        markdown: str,
    ) -> MinutesSummary:
        self.settings.ensure_directories()
        minutes_id = uuid4().hex
        markdown_path = self.settings.minutes_dir / f"{minutes_id}.md"
        json_path = self.settings.minutes_dir / f"{minutes_id}.json"
        artifact = MinutesArtifact(
            minutes_id=minutes_id,
            transcript_id=transcript_id,
            format="markdown",
            markdown=markdown,
        )
        _ = markdown_path.write_text(markdown, encoding="utf-8")
        _ = json_path.write_bytes(
            orjson.dumps(artifact.model_dump(), option=orjson.OPT_INDENT_2),
        )
        return MinutesSummary(
            minutes_id=minutes_id,
            transcript_id=transcript_id,
            markdown_path=markdown_path,
            json_path=json_path,
        )

    def load_minutes(self, minutes_id: str) -> MinutesResult:
        safe_minutes_id = ensure_artifact_id(minutes_id)
        markdown_path = self.settings.minutes_dir / f"{safe_minutes_id}.md"
        json_path = self.settings.minutes_dir / f"{safe_minutes_id}.json"
        if not markdown_path.exists() or not json_path.exists():
            raise ArtifactNotFoundError
        artifact = MinutesArtifact.model_validate_json(
            json_path.read_text(encoding="utf-8"),
        )
        markdown = markdown_path.read_text(encoding="utf-8")
        artifact_json = {
            "minutes_id": artifact.minutes_id,
            "transcript_id": artifact.transcript_id,
            "format": artifact.format,
            "markdown": artifact.markdown,
        }
        return MinutesResult(
            minutes_id=safe_minutes_id,
            transcript_id=artifact.transcript_id,
            markdown=markdown,
            markdown_path=markdown_path,
            json_path=json_path,
            json=artifact_json,
        )


__all__ = [
    "ArtifactNotFoundError",
    "InvalidArtifactIdError",
    "StorageService",
    "UnsupportedAudioError",
]
