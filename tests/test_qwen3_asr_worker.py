import json
import subprocess
from pathlib import Path

import pytest
from app.workers import qwen3_asr_worker


def fake_executable_path(name: str) -> str:
    return f"/test-bin/{name}"


def test_long_audio_is_transcribed_in_bounded_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio = tmp_path / "meeting.wav"
    _ = audio.write_bytes(b"wav")
    mlx_calls: list[list[str]] = []
    ffmpeg_calls: list[list[str]] = []
    monkeypatch.setattr(
        "app.workers.qwen3_asr_worker.shutil.which", fake_executable_path
    )

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        assert timeout == qwen3_asr_worker.MLX_AUDIO_TIMEOUT_SECONDS
        executable = Path(command[0]).name
        if executable == "ffprobe":
            return subprocess.CompletedProcess(command, 0, stdout="610.0\n", stderr="")
        if executable == "ffmpeg":
            ffmpeg_calls.append(command)
            _ = Path(command[-1]).write_bytes(b"chunk")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        mlx_calls.append(command)
        output_path = Path(command[command.index("--output-path") + 1]).with_suffix(
            ".json",
        )
        chunk_index = len(mlx_calls) - 1
        segment_start = 1.0 if chunk_index == 0 else 0.0
        segment_end = 300.25 if chunk_index == 0 else 2.0
        _ = output_path.write_text(
            json.dumps(
                {
                    "text": f"chunk {chunk_index}",
                    "segments": [
                        {
                            "text": f"segment {chunk_index}",
                            "start": segment_start,
                            "end": segment_end,
                            "duration": segment_end - segment_start,
                        },
                    ],
                },
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("app.workers.qwen3_asr_worker.subprocess.run", fake_run)

    payload = qwen3_asr_worker.transcribe(
        qwen3_asr_worker.WorkerArgs(audio=audio, model="qwen", language="ko"),
    )

    assert len(ffmpeg_calls) == 3
    assert len(mlx_calls) == 3
    assert payload["text"] == "chunk 0\n\nchunk 1\n\nchunk 2"
    assert payload["segments"] == ["segment 0", "segment 1", "segment 2"]
    assert payload["timed_segments"] == [
        {"text": "segment 0", "start": 1.0, "end": 300.25, "duration": 299.25},
        {"text": "segment 1", "start": 300.25, "end": 302.0, "duration": 2.0},
        {"text": "segment 2", "start": 600.0, "end": 602.0, "duration": 2.0},
    ]
    assert all("--max-tokens" in call for call in mlx_calls)
    assert all(
        call[call.index("--gen-kwargs") + 1] == qwen3_asr_worker.GENERATION_KWARGS_JSON
        for call in mlx_calls
    )


def test_short_audio_uses_original_file_without_chunking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio = tmp_path / "short.wav"
    _ = audio.write_bytes(b"wav")
    mlx_calls: list[list[str]] = []
    monkeypatch.setattr(
        "app.workers.qwen3_asr_worker.shutil.which", fake_executable_path
    )

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        assert timeout == qwen3_asr_worker.MLX_AUDIO_TIMEOUT_SECONDS
        executable = Path(command[0]).name
        if executable == "ffprobe":
            return subprocess.CompletedProcess(command, 0, stdout="120.0\n", stderr="")
        if executable == "ffmpeg":
            pytest.fail("short audio should not be pre-split")
        mlx_calls.append(command)
        output_path = Path(command[command.index("--output-path") + 1]).with_suffix(
            ".json",
        )
        _ = output_path.write_text(
            json.dumps({"text": "short text", "segments": []}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("app.workers.qwen3_asr_worker.subprocess.run", fake_run)

    payload = qwen3_asr_worker.transcribe(
        qwen3_asr_worker.WorkerArgs(audio=audio, model="qwen", language="ko"),
    )

    assert len(mlx_calls) == 1
    assert mlx_calls[0][mlx_calls[0].index("--audio") + 1] == str(audio)
    assert payload["text"] == "short text"
