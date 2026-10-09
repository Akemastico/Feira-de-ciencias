import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.llm import LLMEngine


async def main():
    engine = LLMEngine()
    prompt = "Oi, BMO! Como você está?"
    print(f"[LLM] conectando em {engine.url} ...")
    t0 = time.perf_counter()
    tokens = 0
    full = ""
    async for chunk, done in engine.generate(prompt):
        tokens += 1
        full += chunk
        print(chunk, end="", flush=True)
    dt = time.perf_counter() - t0
    print()
    print(f"[LLM] {tokens} tokens em {dt:.2f}s ({tokens/dt:.2f} tok/s)")
    print(f"[LLM] resposta bruta: {full!r}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[LLM] ERRO: {e}")
        print("Verifique se o Ollama esta rodando (ollama serve) e se 'qwen3:4b' foi baixado.")
