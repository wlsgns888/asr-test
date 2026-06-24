import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

FFMPEG_TIMEOUT_SECONDS = 900


class AudioConversionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AudioService:
    settings: Settings

    def convert_to_wav(self, source: Path) -> Path:
        self.settings.ensure_directories()
        destination = self.settings.wav_dir / f"{source.stem}.wav"
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(destination),
        ]
        try:
            _ = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=FFMPEG_TIMEOUT_SECONDS,
            )
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as error:
            raise AudioConversionError from error
        return destination
