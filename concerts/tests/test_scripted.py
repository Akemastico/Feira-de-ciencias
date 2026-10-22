import asyncio

from fakes import FakeWebSocket
from backend.app.scripted import ScriptedPipeline


def run(token: bytes) -> FakeWebSocket:
    ws = FakeWebSocket()
    asyncio.run(ScriptedPipeline().process(ws, token))
    return ws


def test_cenario_ok_segue_o_protocolo_atual():
    ws = run(b"ok")

    assert ws.tipos[0] == "transcricao"
    assert ws.jsons[0]["texto"] == "oi bmo"
    assert {"type": "estado", "estado": "pensando"} in ws.jsons
    assert ws.tipos.count("audio_meta") == 1
    assert ws.tipos.index("audio_meta") < ws.tipos.index("frase")
    assert ws.tipos[-1] == "estado"
    assert ws.jsons[-1]["estado"] == "pronto"
    assert ws.bytes


def test_cenario_erro_avisa_e_libera_a_tela():
    ws = run(b"erro")

    assert ws.tipos[0] == "erro"
    assert "teste de erro" in ws.texto_de("erro")[0]
    assert ws.jsons[-1]["estado"] == "pronto"


def test_cenario_longo_tem_varias_frases():
    ws = run(b"longo")

    assert len(ws.texto_de("frase")) >= 3
    assert ws.jsons[-1]["estado"] == "pronto"


def test_cenario_acoes_manda_as_cinco_acoes_depois_da_emocao():
    ws = run(b"acoes")

    acoes = [p for p in ws.jsons if p.get("type") == "acao"]
    assert [a["nome"] for a in acoes] == ["expressao", "animacao", "texto", "led", "som"]
    assert acoes[1]["args"] == {"nome": "pular", "duracao": 5.0}
    assert acoes[3]["args"] == {"cor": "#ff0000", "piscar": False}
    # A ação vem depois da emoção: o BMO já sabe que está feliz.
    assert ws.tipos.index("emocao") < ws.tipos.index("acao")
    assert ws.texto_de("frase") == ["Olha eu pulando!"]
    assert ws.jsons[-1]["estado"] == "pronto"


def test_cenario_acao_invalida_manda_o_que_o_modelo_pediu():
    # O modo de ensaio manda a ação crua, sem filtrar: quem descarta o que
    # não vale é o frontend (a allowlist do dispatcher).
    ws = run(b"acao_invalida")

    acoes = [p for p in ws.jsons if p.get("type") == "acao"]
    assert [a["nome"] for a in acoes] == ["hackear", "animacao", "led"]
    assert ws.texto_de("frase") == ["Continuo aqui!"]
    assert ws.jsons[-1]["estado"] == "pronto"


def test_token_desconhecido_cai_no_cenario_padrao():
    ws = run(b"qualquer-coisa")

    assert ws.jsons[0]["texto"] == "oi bmo"
    assert ws.jsons[-1]["estado"] == "pronto"


def test_status_do_modo_ensaio_e_sempre_ok():
    status = ScriptedPipeline().status()

    assert set(status) == {"stt", "llm", "tts"}
    assert all(item["estado"] == "ok" for item in status.values())
