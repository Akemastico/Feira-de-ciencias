from fastapi.testclient import TestClient

from backend.app.main import app


def test_servidor_sobe_mesmo_sem_engines_carregadas():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code in (200, 503)
    corpo = response.json()
    assert corpo["servidor"] == "ok"
    assert set(corpo["engines"]) == {"stt", "llm", "tts"}
    for estado in corpo["engines"].values():
        assert estado["estado"] in ("ok", "erro", "nao_carregado")
    assert "estado" in corpo["ollama"]


def test_health_sem_ollama_nao_mente():
    with TestClient(app) as client:
        corpo = client.get("/health").json()

    assert corpo["pronto"] is False
    assert corpo["ollama"]["estado"] in ("ok", "indisponivel")


def test_pagina_inicial_e_assets_ausentes_nao_quebram():
    with TestClient(app) as client:
        pagina = client.get("/")
        ausente = client.get("/assets/nao-existe.glb")
        modelo = client.get("/assets/bmo.glb")

    assert pagina.status_code == 200
    assert "text/html" in pagina.headers["content-type"]
    # Caminho que não existe tem que dar 404 sem derrubar o servidor.
    assert ausente.status_code == 404
    # O modelo do BMO está versionado e tem que ser servido.
    assert modelo.status_code == 200


def test_pagina_de_teste_sem_3d_e_servida():
    with TestClient(app) as client:
        resposta = client.get("/test.html")

    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
