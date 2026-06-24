import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from pydantic import TypeAdapter

from app.config import DiarizationEngine, Settings
from app.schemas.transcript import (
    SpeakerSegment,
    TimedTranscriptSegment,
    TranscriptDocument,
)

DIARIZATION_WORKER_TIMEOUT_SECONDS = 7200


class DiarizationBackend(Protocol):
    def diarize(self, wav_path: Path) -> list[SpeakerSegment]: ...


@dataclass(frozen=True, slots=True)
class DisabledDiarizationBackend:
    def diarize(self, wav_path: Path) -> list[SpeakerSegment]:
        _ = wav_path
        return []


@dataclass(frozen=True, slots=True)
class FakeDiarizationBackend:
    def diarize(self, wav_path: Path) -> list[SpeakerSegment]:
        _ = wav_path
        return [
            SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=2.0),
            SpeakerSegment(speaker="SPEAKER_01", start=2.0, end=4.0),
        ]


@dataclass(frozen=True, slots=True)
class PyannoteDiarizationBackend:
    settings: Settings

    def diarize(self, wav_path: Path) -> list[SpeakerSegment]:
        token = self.settings.diarization_hf_token.get_secret_value()
        if token == "":
            raise DiarizationConfigurationError

        env = os.environ.copy()
        env["PYANNOTE_AUTH_TOKEN"] = token
        command = [
            sys.executable,
            "-m",
            "app.workers.pyannote_diarization_worker",
            "--audio",
            str(wav_path),
            "--model",
            self.settings.diarization_model,
        ]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=DIARIZATION_WORKER_TIMEOUT_SECONDS,
                env=env,
            )
        except subprocess.TimeoutExpired as error:
            raise DiarizationWorkerError from error
        except subprocess.CalledProcessError as error:
            stderr_value = cast("object", error.stderr)
            stderr = stderr_value.strip() if isinstance(stderr_value, str) else ""
            raise DiarizationWorkerError(stderr.strip()) from error

        return TypeAdapter(list[SpeakerSegment]).validate_json(completed.stdout)


def create_diarization_backend(settings: Settings) -> DiarizationBackend:
    match settings.diarization_engine:
        case DiarizationEngine.DISABLED:
            return DisabledDiarizationBackend()
        case DiarizationEngine.FAKE:
            return FakeDiarizationBackend()
        case DiarizationEngine.PYANNOTE:
            return PyannoteDiarizationBackend(settings)


def apply_speaker_labels(
    transcript: TranscriptDocument,
    speaker_turns: list[SpeakerSegment],
) -> TranscriptDocument:
    if len(speaker_turns) == 0:
        return transcript

    if len(transcript.timed_segments) == 0:
        speaker = speaker_turns[0].speaker
        line = f"[{speaker}] {transcript.text}"
        return transcript.model_copy(
            update={
                "speaker_segments": [
                    speaker_turns[0].model_copy(update={"text": transcript.text})
                ],
                "speaker_transcript": line,
            }
        )

    aligned_segments = _align_transcript_segments(
        transcript.timed_segments,
        speaker_turns,
    )
    lines = _format_speaker_transcript(aligned_segments)
    return transcript.model_copy(
        update={
            "speaker_segments": aligned_segments,
            "speaker_transcript": "\n".join(lines),
        }
    )


def _align_transcript_segments(
    transcript_segments: list[TimedTranscriptSegment],
    speaker_turns: list[SpeakerSegment],
) -> list[SpeakerSegment]:
    aligned_segments: list[SpeakerSegment] = []
    for segment in transcript_segments:
        overlaps = _overlapping_turns(segment, speaker_turns)
        if len(overlaps) <= 1:
            aligned_segments.append(_assign_speaker(segment, speaker_turns))
            continue
        aligned_segments.extend(_split_segment_by_turns(segment, overlaps))
    return aligned_segments


def _overlapping_turns(
    segment: TimedTranscriptSegment,
    speaker_turns: list[SpeakerSegment],
) -> list[SpeakerSegment]:
    start = segment.start if segment.start is not None else 0.0
    end = _segment_end(segment)
    return [turn for turn in speaker_turns if _overlap(start, end, turn) > 0.0]


def _split_segment_by_turns(
    segment: TimedTranscriptSegment,
    speaker_turns: list[SpeakerSegment],
) -> list[SpeakerSegment]:
    start = segment.start if segment.start is not None else 0.0
    end = _segment_end(segment)
    tokens = _segment_tokens(segment.text)
    if end <= start or len(tokens) == 0:
        return [_assign_speaker(segment, speaker_turns)]

    token_duration = (end - start) / len(tokens)
    pieces: list[SpeakerSegment] = []
    for index, token in enumerate(tokens):
        token_start = start + (token_duration * index)
        token_end = token_start + token_duration
        token_segment = TimedTranscriptSegment(
            text=token,
            start=token_start,
            end=token_end,
        )
        pieces.append(_assign_speaker(token_segment, speaker_turns))
    return pieces


def _segment_tokens(text: str) -> list[str]:
    tokens = text.split()
    if len(tokens) > 0:
        return tokens
    return list(text)


def _assign_speaker(
    segment: TimedTranscriptSegment,
    speaker_turns: list[SpeakerSegment],
) -> SpeakerSegment:
    start = segment.start if segment.start is not None else 0.0
    end = _segment_end(segment)
    best_turn = max(speaker_turns, key=lambda turn: _overlap(start, end, turn))
    return SpeakerSegment(
        speaker=best_turn.speaker,
        start=start,
        end=end,
        text=segment.text,
    )


def _segment_end(segment: TimedTranscriptSegment) -> float:
    if segment.end is not None:
        return segment.end
    if segment.start is not None and segment.duration is not None:
        return segment.start + segment.duration
    if segment.start is not None:
        return segment.start
    return 0.0


def _overlap(start: float, end: float, turn: SpeakerSegment) -> float:
    return max(0.0, min(end, turn.end) - max(start, turn.start))


def _format_speaker_transcript(segments: list[SpeakerSegment]) -> list[str]:
    lines: list[str] = []
    current_speaker = ""
    current_parts: list[str] = []
    for segment in segments:
        if segment.speaker != current_speaker and len(current_parts) > 0:
            lines.append(f"[{current_speaker}] {' '.join(current_parts)}")
            current_parts = []
        current_speaker = segment.speaker
        current_parts.append(segment.text)

    if len(current_parts) > 0:
        lines.append(f"[{current_speaker}] {' '.join(current_parts)}")
    return lines


class DiarizationConfigurationError(RuntimeError):
    pass


class DiarizationWorkerError(RuntimeError):
    pass
