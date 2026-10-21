from pathlib import Path

from .config import settings


class STTEngine:
    """Speech-to-text usando faster-whisper.

    O import de faster_whisper fica dentro do __init__ para que o backend
    suba mesmo em máquina sem a dependência instalada (o erro aparece em
    /health em vez de derrubar o processo).
    """

    def __init__(self):
        from faster_whisper import WhisperModel

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
            beam_size=1,
            vad_filter=True,  # sem isso, silêncio/ruído vira frase inventada
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
