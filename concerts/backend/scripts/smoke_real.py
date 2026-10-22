"""Teste real das três engines, isoladas e sem navegador.

Roda STT, LLM e TTS de verdade nesta máquina e mostra os tempos de cada etapa.
Serve como diagnóstico antes da apresentação e como teste de ponta a ponta
(TTS gera a fala, STT transcreve essa mesma fala e a gente compara).

Uso:
    python backend/scripts/smoke_real.py
    python backend/scripts/smoke_real.py --frase "Bom dia, eu sou o BMO!"
"""

import argparse
import asyncio
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.config import settings  # noqa: E402
from backend.app.llm import LLMEngine, LLMError  # noqa: E402
from backend.app.parsing import ResponseParser  # noqa: E402
from backend.app.stt import STTEngine  # noqa: E402
from backend.app.tts import SAMPLE_RATE, TTSEngine  # noqa: E402


def salvar_wav(pcm: bytes, destino: Path) -> None:
    with wave.open(str(destino), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)


def normalizar(texto: str) -> str:
    limpo = "".join(c if c.isalnum() or c.isspace() else " " for c in texto.lower())
    return " ".join(limpo.split())


def prova(stt, llm, tts, frase: str, out_dir: Path) -> bool:
    ok = True

    print("\n== TTS (Kokoro) ==")
    t0 = time.perf_counter()
    pcm = tts.synthesize_sentence(frase)
    dt = time.perf_counter() - t0
    if not pcm:
        print("FALHOU: nenhum áudio gerado")
        return False
    wav_path = out_dir / "bmo_tts.wav"
    salvar_wav(pcm, wav_path)
    duracao = len(pcm) / 2 / SAMPLE_RATE
    print(f"ok: {len(pcm)} bytes, {duracao:.2f}s de áudio em {dt:.2f}s ({wav_path})")

    print("\n== STT (Whisper) ==")
    t0 = time.perf_counter()
    ouvido = stt.transcribe(wav_path)
    dt = time.perf_counter() - t0
    print(f"falado:    {frase!r}")
    print(f"transcrito: {ouvido!r}  ({dt:.2f}s)")
    if not ouvido.strip():
        print("ATENÇÃO: transcrição vazia (VAD cortou?)")
        ok = False
    elif normalizar(ouvido) != normalizar(frase):
        print("ATENÇÃO: transcrição diferente do texto original (confira acima)")
    else:
        print("ok: transcrição igual ao texto original")

    print("\n== LLM (Ollama) ==")
    parser = ResponseParser()
    t0 = time.perf_counter()
    primeira = None
    try:

        async def consumir():
            nonlocal primeira
            async for chunk, done in llm.generate("Oi BMO, tudo bem?"):
                if primeira is None:
                    primeira = time.perf_counter() - t0
                parser.feed(chunk)
                parser.drain_text()
                if done:
                    break

        asyncio.run(consumir())
    except LLMError as exc:
        print(f"FALHOU: {exc}")
        return False

    total = time.perf_counter() - t0
    print(f"modelo:  {settings.OLLAMA_MODEL}")
    print(f"emocao:  {parser.emotion}")
    print(f"resposta: {parser.buffer.strip()[:200]}")
    print(f"primeiro chunk: {primeira and f'{primeira:.2f}s'} | total: {total:.2f}s")
    if parser.emotion is None:
        print("ATENÇÃO: o modelo não devolveu 'emocao' — confira o prompt/schema")
        ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Teste real de STT, LLM e TTS")
    ap.add_argument("--frase", default="Oi! Eu sou o BMO e eu adoro fazer amigos.")
    ap.add_argument("--out", default="/tmp/opencode/bmo-smoke")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Whisper: {settings.WHISPER_MODEL} ({settings.WHISPER_DEVICE}/{settings.WHISPER_COMPUTE_TYPE})")
    print(f"Kokoro:  voz {settings.KOKORO_VOICE} (lang {settings.KOKORO_LANG})")
    print(f"Ollama:  {settings.OLLAMA_MODEL} em {settings.OLLAMA_URL}")

    print("\n== Carregando engines ==")
    t0 = time.perf_counter()
    try:
        tts = TTSEngine()
        stt = STTEngine()
    except Exception as exc:
        print(f"FALHOU ao carregar: {exc.__class__.__name__}: {exc}")
        return 2
    print(f"ok: carregadas em {time.perf_counter() - t0:.2f}s")

    deu_certo = prova(stt, LLMEngine(), tts, args.frase, out_dir)
    print("\nRESULTADO:", "ok" if deu_certo else "com ressalvas")
    return 0 if deu_certo else 1


if __name__ == "__main__":
    raise SystemExit(main())
