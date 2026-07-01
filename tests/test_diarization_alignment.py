from app.schemas import SpeakerSegment, TimedTranscriptSegment, TranscriptDocument
from app.services.diarization_service import apply_speaker_labels


def test_coarse_asr_segment_is_split_across_speaker_turns() -> None:
    # Given: ASR returns one coarse segment spanning multiple diarization turns.
    text = "안녕하세요 오늘 회의 시작합니다 네 일정 공유하겠습니다 감사합니다"
    transcript = TranscriptDocument(
        model="test-asr",
        language="ko",
        text=text,
        segments=[text],
        timed_segments=[
            TimedTranscriptSegment(
                text=text,
                start=0.0,
                end=9.0,
            )
        ],
    )
    speaker_turns = [
        SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=3.0),
        SpeakerSegment(speaker="SPEAKER_01", start=3.0, end=6.0),
        SpeakerSegment(speaker="SPEAKER_00", start=6.0, end=9.0),
    ]

    # When: speaker labels are applied.
    labeled = apply_speaker_labels(transcript, speaker_turns)

    # Then: the transcript keeps both speakers instead of collapsing to one.
    assert "[SPEAKER_00]" in labeled.speaker_transcript
    assert "[SPEAKER_01]" in labeled.speaker_transcript
    assert "[SPEAKER_00]" in labeled.text
    assert "[SPEAKER_01]" in labeled.text
    assert {segment.speaker for segment in labeled.speaker_segments} == {
        "SPEAKER_00",
        "SPEAKER_01",
    }
