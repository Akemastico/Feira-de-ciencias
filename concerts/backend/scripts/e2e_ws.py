"""Teste de ponta a ponta contra o servidor rodando, sem navegador e sem microfone.

Manda um arquivo de áudio pelo WebSocket no mesmo formato que o MediaRecorder
produz (webm/opus), imprime cada mensagem com o tempo de chegada e salva a
resposta falada do BMO em WAV para conferir depois.

Útil no dia da apresentação: se o microfone der problema, este script prova
que STT, LLM, TTS e WebSocket continuam funcionando.

Uso:
    python backend/scripts/e2e_ws.py audio.webm
    python backend/scripts/e2e_ws.py audio.wav --url ws://127.0.0.1:8000/ws
"""

import argparse
import asyncio
import json
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import websockets  # noqa: E402

SAMPLE_RATE = 24000


async def rodar(url: str, origem: Path, destino: Path) -> int:
    dados = origem.read_bytes()
    print(f"enviando {origem.name} ({len(dados)} bytes) para {url}\n")

    pcm = bytearray()
    marcos: dict[str, float] = {}
    ultimo_audio = 0.0
    erro = False

    t0 = time.perf_counter()
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(dados)
        while True:
            mensagem = await asyncio.wait_for(ws.recv(), timeout=240)
            agora = time.perf_counter() - t0

            if isinstance(mensagem, bytes):
                pcm += mensagem
                marcos.setdefault("primeiro_audio", agora)
                ultimo_audio = agora
                continue

            corpo = json.loads(mensagem)
            tipo = corpo.get("type")
            marcos.setdefault(tipo, agora)
            print(f"[{agora:6.2f}s] {tipo}: {json.dumps(corpo, ensure_ascii=False)[:150]}")

            if tipo == "erro":
                erro = True
            if tipo in ("audio_fim", "erro"):
                break

    if pcm:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destino), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(bytes(pcm))

    print("\n== tempos ==")
    for nome, valor in marcos.items():
        print(f"{nome:15s} {valor:6.2f}s")

    if pcm:
        print(f"último áudio    {ultimo_audio:6.2f}s")
        print(
            f"\nresposta falada: {len(pcm)} bytes "
            f"({len(pcm) / 2 / SAMPLE_RATE:.2f}s) em {destino}"
        )
    else:
        print("nenhum áudio recebido")

    if erro:
        return 1
    if not pcm:
        print("RESSALVA: o BMO não falou nada")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Teste de ponta a ponta via WebSocket")
    ap.add_argument("audio", help="arquivo de áudio (webm/opus ou wav)")
    ap.add_argument("--url", default="ws://127.0.0.1:8000/ws")
    ap.add_argument("--out", default="/tmp/bmo_resposta.wav")
    args = ap.parse_args()

    origem = Path(args.audio)
    if not origem.exists():
        print(f"FALHOU: áudio não encontrado: {origem}")
        return 2

    return asyncio.run(rodar(args.url, origem, Path(args.out)))


if __name__ == "__main__":
    raise SystemExit(main())
