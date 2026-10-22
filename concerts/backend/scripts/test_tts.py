import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.tts import SAMPLE_RATE, TTSEngine


def _write_wav(path: Path, pcm: bytes):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


def main():
    texto = (
        "Oi! Eu sou o BMO. Estou muito feliz de te ver hoje. "
        "O que você quer fazer agora?"
    )

    t0 = time.perf_counter()
    engine = TTSEngine()
    t_load = time.perf_counter() - t0
    print(f"[TTS] modelo carregado em {t_load:.2f}s (voice={engine.voice})")

    t0 = time.perf_counter()
    first = None
    n = 0
    total = 0
    for i, (graphemes, pcm) in enumerate(engine.synthesize_segments(texto)):
        if first is None:
            first = time.perf_counter() - t0
        n += 1
        total += len(pcm)
        out = Path(f"_tts_seg_{i}.wav")
        _write_wav(out, pcm)
        print(f"[TTS] segmento {i}: '{graphemes}' {len(pcm)} bytes -> {out.name}")
    t_total = time.perf_counter() - t0

    print(f"[TTS] segmentos={n}, audio={total / 2 / SAMPLE_RATE:.2f}s")
    print(f"[TTS] primeiro segmento em {first:.2f}s, total em {t_total:.2f}s")


if __name__ == "__main__":
    main()
