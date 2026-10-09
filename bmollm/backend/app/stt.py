from pathlib import Path
from faster_whisper import WhisperModel
from .config import settings


class STTEngine:
    """Speech-to-text usando faster-whisper."""

    def __init__(self):
        self.model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
            cpu_threads=0,  # auto
        )

    def transcribe(self, audio_path: Path) -> str:
        segments, _info = self.model.transcribe(
            str(audio_path),
            language="pt",
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
