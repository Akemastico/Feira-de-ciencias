"""Simula o navegador mandando áudio pelo WebSocket, sem modelo nenhum."""

from fastapi.testclient import TestClient

import backend.app.main as main
from backend.app.main import app


class PipelineFake:
    def __init__(self):
        self.recebidos = []

    async def process(self, ws, audio_bytes):
        self.recebidos.append(audio_bytes)
        await ws.send_json({"type": "transcricao", "texto": "oi bmo"})
        await ws.send_json({"type": "estado", "estado": "pronto"})


def test_bytes_do_frontend_chegam_no_pipeline(monkeypatch):
    fake = PipelineFake()
    monkeypatch.setattr(main, "pipeline", fake)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"\x1a\x2b\x3c")
            primeira = ws.receive_json()
            segunda = ws.receive_json()

    assert primeira == {"type": "transcricao", "texto": "oi bmo"}
    assert segunda == {"type": "estado", "estado": "pronto"}
    assert fake.recebidos == [b"\x1a\x2b\x3c"]


def test_duas_gravacoes_seguidas_nao_se_perdem(monkeypatch):
    fake = PipelineFake()
    monkeypatch.setattr(main, "pipeline", fake)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"primeira")
            ws.receive_json()
            ws.receive_json()
            ws.send_bytes(b"segunda")
            ws.receive_json()
            ws.receive_json()

    assert fake.recebidos == [b"primeira", b"segunda"]
