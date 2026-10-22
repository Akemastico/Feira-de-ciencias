import asyncio
import json
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, settings
from .pipeline import BmoPipeline
from .scripted import ScriptedPipeline


def _setup_logging():
    handlers = [logging.StreamHandler()]
    if settings.LOG_TO_FILE:
        try:
            log_path = ROOT / settings.LOG_FILE
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
        except OSError:
            pass  # sem permissão de escrita, segue só no terminal
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


_setup_logging()
log = logging.getLogger(__name__)

FRONTEND_DIR = ROOT / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"

# A pasta não existe no clone. Sem ela, StaticFiles derrubava o app inteiro
# no import. Criar aqui mantém o servidor de pé mesmo sem o bmo.glb.
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Em BMO_E2E=1 o pipeline roteirizado assume: testes sem GPU nem modelos.
pipeline = ScriptedPipeline() if settings.E2E else BmoPipeline()
if settings.E2E:
    log.info("Modo ensaio E2E ligado (BMO_E2E=1): respostas roteirizadas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.warmup_task = None
    if settings.PRELOAD:
        log.info("Carregando engines e aquecendo o Ollama (BMO_PRELOAD=1)")
        app.state.warmup_task = asyncio.create_task(pipeline.warmup())
    else:
        log.info("Pré-carregamento desligado (BMO_PRELOAD=0)")
    yield
    if hasattr(pipeline, "aclose"):
        try:
            await pipeline.aclose()
        except Exception:
            log.exception("Falha ao fechar engines")


app = FastAPI(title="BMO-LLM", lifespan=lifespan)


@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/test.html")
async def pagina_de_teste():
    # Página sem 3D, útil para isolar problemas de STT/TTS em campo.
    return FileResponse(FRONTEND_DIR / "test.html")


async def _check_ollama() -> dict:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            response = await client.get(f"{settings.OLLAMA_URL}/api/tags")
            response.raise_for_status()
            nomes = [m.get("name", "") for m in response.json().get("models", [])]
    except Exception as exc:
        return {"estado": "indisponivel", "detalhe": str(exc)}

    modelo_ok = any(n == settings.OLLAMA_MODEL or n.startswith(settings.OLLAMA_MODEL) for n in nomes)
    return {
        "estado": "ok",
        "modelo": settings.OLLAMA_MODEL,
        "modelo_baixado": modelo_ok,
        "modelos": nomes,
    }


@app.get("/health")
async def health():
    engines = pipeline.status()
    ollama = await _check_ollama()
    pronto = (
        all(e["estado"] == "ok" for e in engines.values())
        and ollama.get("estado") == "ok"
        and ollama.get("modelo_baixado", False)
    )
    return JSONResponse(
        status_code=200 if pronto else 503,
        content={"servidor": "ok", "pronto": pronto, "engines": engines, "ollama": ollama},
    )


app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/src", StaticFiles(directory=FRONTEND_DIR / "src"), name="src")
app.mount("/vendor", StaticFiles(directory=FRONTEND_DIR / "vendor"), name="vendor")


async def _cancelar(task):
    """Corta a resposta em andamento. Devolve True se havia alguma coisa viva."""
    if task is None or task.done():
        return False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("Falha ao encerrar a resposta anterior")
    return True


async def _avisar_parar(ws):
    """Avisa o cliente que o BMO parou de falar."""
    try:
        await ws.send_json({"type": "parar"})
    except Exception:
        pass


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    task = None
    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes"):
                # Áudio novo: a resposta anterior é cortada na hora. O aviso
                # só sai quando havia mesmo uma resposta em andamento.
                if await _cancelar(task):
                    await _avisar_parar(ws)
                task = asyncio.create_task(pipeline.process(ws, message["bytes"]))
            elif message.get("text"):
                # Barge-in: o cliente apertou o botão de novo e quer o BMO
                # calado agora, sem esperar o áudio novo chegar.
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and payload.get("type") == "interromper":
                    await _cancelar(task)
                    task = None
                    await _avisar_parar(ws)
    except WebSocketDisconnect:
        pass
    finally:
        if task is not None:
            task.cancel()
