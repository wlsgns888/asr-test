import subprocess
from pathlib import Path

import pytest
from app.config import AppEnv, Settings
from app.schemas import TimedTranscriptSegment, TranscriptDocument
from app.services.alignment_service import Qwen3ForcedAlignmentBackend


def test_forced_alignment_uses_timestamped_audio_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: ASR has already divided a long recording into timed text segments.
    wav_path = tmp_path / "long.wav"
    _ = wav_path.write_bytes(b"fake-wav")
    transcript = TranscriptDocument(
        model="test",
        language="ko",
        text="첫 번째 발화 두 번째 발화",
        segments=["첫 번째 발화", "두 번째 발화"],
        timed_segments=[
            TimedTranscriptSegment(text="첫 번째 발화", start=0.0, end=30.0),
            TimedTranscriptSegment(text="두 번째 발화", start=360.0, end=390.0),
        ],
    )
    aligner_audio_paths: list[str] = []
    aligner_inputs: list[str | None] = []

    def fake_run(
        command: list[str],
        **kwargs: str | bool | int | None,
    ) -> subprocess.CompletedProcess[str]:
        request_input = kwargs.get("input")
        if command[0] == "ffmpeg":
            _ = Path(command[-1]).write_bytes(b"clip")
            return subprocess.CompletedProcess(command, 0, "", "")
        aligner_audio_paths.append(command[command.index("--audio") + 1])
        aligner_inputs.append(request_input if isinstance(request_input, str) else None)
        return subprocess.CompletedProcess(
            command,
            0,
            '[{"text":"정렬","start":0.0,"end":1.0}]',
            "",
        )

    monkeypatch.setattr("app.services.alignment_service.subprocess.run", fake_run)
    settings = Settings(app_env=AppEnv.TESTING)
    backend = Qwen3ForcedAlignmentBackend(settings)

    # When: forced alignment runs.
    aligned = backend.align(wav_path, transcript)

    # Then: each aligner call receives a clipped window, not the original long WAV.
    assert len(aligner_audio_paths) == 2
    assert str(wav_path) not in aligner_audio_paths
    assert aligner_inputs == ["첫 번째 발화", "두 번째 발화"]
    assert aligned.timed_segments[0].start == 0.0
    assert aligned.timed_segments[1].start == 360.0
