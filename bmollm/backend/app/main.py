import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import ROOT
from .pipeline import BmoPipeline

app = FastAPI(title="BMO-LLM")
FRONTEND_DIR = ROOT / "frontend"

pipeline = BmoPipeline()


@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
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
                    except (asyncio.CancelledError, Exception):
                        pass
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
