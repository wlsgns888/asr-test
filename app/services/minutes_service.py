from dataclasses import dataclass

from app.schemas.minutes import MinutesSummary
from app.services.llm_service import LLMService
from app.services.storage_service import StorageService


@dataclass(frozen=True, slots=True)
class MinutesService:
    storage: StorageService
    llm: LLMService

    def create_minutes(self, transcript_id: str, template: str) -> MinutesSummary:
        transcript = self.storage.load_transcript(transcript_id)
        source_text = transcript.speaker_transcript or transcript.text
        markdown = self.llm.generate_minutes(source_text, template)
        return self.storage.save_minutes(transcript_id, markdown)
