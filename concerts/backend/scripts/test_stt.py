import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.stt import STTEngine
from backend.app.config import settings


def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/scripts/test_stt.py <arquivo.wav>")
        return
    audio = Path(sys.argv[1])
    if not audio.exists():
        print(f"Arquivo nao encontrado: {audio}")
        return

    t0 = time.perf_counter()
    engine = STTEngine()
    t_load = time.perf_counter() - t0
    print(f"[STT] modelo carregado em {t_load:.2f}s (model={settings.WHISPER_MODEL})")

    t0 = time.perf_counter()
    texto = engine.transcribe(audio)
    dt = time.perf_counter() - t0
    print(f"[STT] transcrito em {dt:.2f}s")
    print(f"[STT] texto: {texto}")


if __name__ == "__main__":
    main()
