import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, settings
from .pipeline import BmoPipeline


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

pipeline = BmoPipeline()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.warmup_task = None
    if settings.PRELOAD:
        log.info("Carregando engines e aquecendo o Ollama (BMO_PRELOAD=1)")
        app.state.warmup_task = asyncio.create_task(pipeline.warmup())
    else:
        log.info("Pré-carregamento desligado (BMO_PRELOAD=0)")
    yield


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
                if task is not None and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        log.exception("Falha ao encerrar a resposta anterior")
                    try:
                        await ws.send_json({"type": "parar"})
                    except Exception:
                        pass
                task = asyncio.create_task(pipeline.process(ws, message["bytes"]))
    except WebSocketDisconnect:
        pass
    finally:
        if task is not None:
            task.cancel()
