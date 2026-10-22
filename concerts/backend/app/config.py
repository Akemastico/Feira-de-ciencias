from pathlib import Path

import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


def _flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() not in ("0", "false", "no", "off")


class Settings:
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
    OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))
    OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.85"))
    OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "24h")
    OLLAMA_TIMEOUT_CONNECT = float(os.getenv("OLLAMA_TIMEOUT_CONNECT", "5"))
    OLLAMA_TIMEOUT_READ = float(os.getenv("OLLAMA_TIMEOUT_READ", "120"))

    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    KOKORO_VOICE = os.getenv("KOKORO_VOICE", "pf_dora")
    KOKORO_LANG = os.getenv("KOKORO_LANG", "p")
    KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))

    EMOTIONS = [
        e.strip()
        for e in os.getenv("EMOTIONS", "neutro,feliz,triste,surpreso,curioso,bravo").split(",")
        if e.strip()
    ]

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_FILE = _flag("LOG_TO_FILE", "1")
    LOG_FILE = os.getenv("LOG_FILE", "logs/bmo.log")

    # Carrega Whisper/Kokoro em segundo plano ao subir o servidor.
    # Com 0, tudo é carregado na primeira pergunta (útil em teste/máquina fraca).
    PRELOAD = _flag("BMO_PRELOAD", "1")

    # Modo ensaio dos testes E2E: respostas roteirizadas, sem modelos.
    # Fica desligado por padrão; só os testes Playwright ligam.
    E2E = _flag("BMO_E2E", "0")

    # Ações do modelo (expressao, animacao, texto, led, som) pelo WebSocket.
    # Fica desligado por padrão: só liga quando o modelo novo for validado.
    ACTIONS_ENABLED = _flag("BMO_ACOES", "0")


settings = Settings()
