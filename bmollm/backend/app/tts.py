from .config import settings

SAMPLE_RATE = 24000


class TTSEngine:
    """Text-to-speech usando Kokoro (pt-BR via espeak-ng).

    Imports de kokoro/numpy ficam aqui dentro: o servidor sobe sem eles e
    /health mostra o motivo da falha.
    """

    def __init__(self):
        from kokoro import KPipeline

        self.pipeline = KPipeline(lang_code=settings.KOKORO_LANG)
        self.voice = settings.KOKORO_VOICE
        self.speed = settings.KOKORO_SPEED

    def _to_pcm(self, audio) -> bytes:
        import numpy as np

        audio_np = audio.detach().cpu().numpy()
        return (np.clip(audio_np, -1.0, 1.0) * 32767).astype("<i2").tobytes()

    def synthesize_segments(self, text: str):
        generator = self.pipeline(text, voice=self.voice, speed=self.speed)
        for result in generator:
            if result.audio is None:
                continue
            yield result.graphemes, self._to_pcm(result.audio)

    def synthesize_sentence(self, text: str) -> bytes:
        chunks = [pcm for _g, pcm in self.synthesize_segments(text)]
        return b"".join(chunks)
