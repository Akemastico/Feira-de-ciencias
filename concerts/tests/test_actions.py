import asyncio
import json
from pathlib import Path

from backend.app.actions import ActionStreamParser, acoes_schema, normalizar_acoes
from backend.app.config import settings
from fakes import FakeLLM, FakeSTT, FakeTTS, FakeWebSocket, make_pipeline


def parse(pedacos):
    parser = ActionStreamParser()
    saida = []
    for pedaco in pedacos:
        saida.extend(parser.feed(pedaco))
    return saida


def test_extrai_acao_antes_da_resposta():
    acoes = parse([
        '{"emocao":"feliz","acoes":[{"nome":"animacao",',
        '{"args":{"nome":"pular"}}],"resposta":"Oi!"}',
    ])

    assert [(a.nome, a.args) for a in acoes] == [("animacao", {"nome": "pular", "duracao": 1.5})]


def test_extrai_acao_depois_da_resposta():
    acoes = parse([
        '{"emocao":"neutro","resposta":"Oi!",',
        '"acoes":[{"nome":"som","args":{"tipo":"bip"}}]}',
    ])

    assert [a.nome for a in acoes] == ["som"]


def test_espera_array_fechar_antes_de_executar():
    parser = ActionStreamParser()
    assert parser.feed('{"acoes":[{"nome":"animacao",') == []
    assert parser.feed('"args":{"nome":"dancar"}}]') != []


def test_descarta_acao_desconhecida_e_args_invalidos():
    acoes = normalizar_acoes([
        {"nome": "hackear", "args": {}},
        {"nome": "animacao", "args": {"nome": "voar"}},
        {"nome": "led", "args": {"cor": "vermelho"}},
        {"nome": "som", "args": {"tipo": "bip"}},
    ])

    assert [a.nome for a in acoes] == ["som"]


def test_limita_a_oito_acoes():
    raw = [{"nome": "som", "args": {"tipo": "bip"}}] * 20

    assert len(normalizar_acoes(raw)) == 8


def test_json_quebrado_nao_derruba_a_fala():
    acoes = parse(['{"acoes":[{"nome":', '###}],"resposta":"Oi!"}'])

    assert acoes == []


def test_exemplos_de_modelo_viram_acoes():
    fixture = Path(__file__).parent / "fixtures" / "model_output_examples.json"
    exemplos = json.loads(fixture.read_text(encoding="utf-8"))

    for exemplo in exemplos:
        parser = ActionStreamParser()
        acoes = []
        for pedaco in exemplo["chunks"]:
            acoes.extend(parser.feed(pedaco))
        assert [a.nome for a in acoes] == exemplo["esperado"]


# --- normalização em detalhe (o que o frontend vai receber) ---


def test_expressao_aceita_so_emocao_conhecida():
    acoes = normalizar_acoes([
        {"nome": "expressao", "args": {"emocao": "feliz"}},
        {"nome": "expressao", "args": {"emocao": "bravo-de-verdade"}},
    ])

    assert [(a.nome, a.args) for a in acoes] == [("expressao", {"emocao": "feliz"})]


def test_texto_precisa_de_texto_e_corta_texto_longo():
    acoes = normalizar_acoes([
        {"nome": "texto", "args": {"texto": "   "}},
        {"nome": "texto", "args": {"texto": "x" * 250}},
    ])

    assert len(acoes) == 1
    assert acoes[0].args["texto"] == "x" * 200
    assert acoes[0].args["duracao"] == 4.0


def test_led_precisa_de_cor_hexadecimal():
    acoes = normalizar_acoes([
        {"nome": "led", "args": {"cor": "#FF00aa", "piscar": True}},
        {"nome": "led", "args": {"cor": "vermelho"}},
    ])

    assert [(a.nome, a.args) for a in acoes] == [("led", {"cor": "#FF00aa", "piscar": True})]


def test_duracao_fora_da_faixa_usa_o_padrao():
    acoes = normalizar_acoes([
        {"nome": "animacao", "args": {"nome": "dancar", "duracao": 900}},
        {"nome": "animacao", "args": {"nome": "dancar", "duracao": "muito"}},
    ])

    assert [a.args["duracao"] for a in acoes] == [1.5, 1.5]


def test_chaves_extras_dos_args_sao_descartadas():
    acoes = normalizar_acoes([
        {"nome": "som", "args": {"tipo": "bip", "volume": 99, "url": "http://x"}},
    ])

    assert acoes[0].args == {"tipo": "bip"}


def test_normalizar_aceita_qualquer_coisa_fora_de_lista():
    assert normalizar_acoes(None) == []
    assert normalizar_acoes({"nome": "som"}) == []
    assert normalizar_acoes("som") == []


def test_parser_nao_repete_acao_apos_o_array_fechar():
    parser = ActionStreamParser()
    primeiro = parser.feed('{"acoes":[{"nome":"som","args":{"tipo":"bip"}}]')
    segundo = parser.feed('"resposta":"Oi!"}')

    assert [a.nome for a in primeiro] == ["som"]
    assert segundo == []


def test_schema_de_acoes_lista_a_allowlist():
    schema = acoes_schema()

    assert schema["type"] == "array"
    assert schema["maxItems"] == 8
    assert schema["items"]["properties"]["nome"]["enum"] == [
        "expressao",
        "animacao",
        "texto",
        "led",
        "som",
    ]
    assert schema["items"]["required"] == ["nome", "args"]


# --- ligação com o LLM e com o pipeline ---


def test_llm_so_pede_acoes_com_a_flag_ligada(monkeypatch):
    from backend.app import llm as llm_mod

    monkeypatch.setattr(settings, "ACTIONS_ENABLED", False)
    desligado = llm_mod.LLMEngine()

    assert "acoes" not in desligado.schema["properties"]
    assert desligado.schema["required"] == ["emocao", "resposta"]
    assert "acoes" not in desligado.system_prompt

    monkeypatch.setattr(settings, "ACTIONS_ENABLED", True)
    ligado = llm_mod.LLMEngine()

    assert ligado.schema["properties"]["acoes"] == acoes_schema()
    assert "acoes" in ligado.system_prompt


def test_pipeline_manda_mensagem_de_acao_e_continua_falando(monkeypatch):
    monkeypatch.setattr(settings, "ACTIONS_ENABLED", True)
    chunks = [('{"emocao":"feliz","acoes":[{"nome":"som","args":{"tipo":"bip"}}],"resposta":"Oi!"}', True)]
    pipeline = make_pipeline(stt=FakeSTT("oi"), llm=FakeLLM(chunks), tts=FakeTTS())

    ws = FakeWebSocket()
    asyncio.run(pipeline.process(ws, b"audio-fake"))

    assert {"type": "acao", "nome": "som", "args": {"tipo": "bip"}} in ws.jsons
    assert ws.texto_de("frase") == ["Oi!"]
    assert ws.jsons[-1] == {"type": "estado", "estado": "pronto"}


def test_pipeline_ignora_acao_invalida_sem_quebrar_a_fala(monkeypatch):
    monkeypatch.setattr(settings, "ACTIONS_ENABLED", True)
    chunks = [('{"emocao":"feliz","acoes":[{"nome":"hackear","args":{}}],"resposta":"Oi!"}', True)]
    pipeline = make_pipeline(stt=FakeSTT("oi"), llm=FakeLLM(chunks), tts=FakeTTS())

    ws = FakeWebSocket()
    asyncio.run(pipeline.process(ws, b"audio-fake"))

    assert "acao" not in ws.tipos
    assert ws.texto_de("frase") == ["Oi!"]


def test_pipeline_so_manda_acao_com_a_flag_ligada(monkeypatch):
    """A flag é o botão do operador: desligada, nenhuma ação sai do backend."""
    chunks = [('{"emocao":"feliz","acoes":[{"nome":"som","args":{"tipo":"bip"}}],"resposta":"Oi!"}', True)]

    monkeypatch.setattr(settings, "ACTIONS_ENABLED", False)
    pipeline = make_pipeline(stt=FakeSTT("oi"), llm=FakeLLM(chunks), tts=FakeTTS())

    ws = FakeWebSocket()
    asyncio.run(pipeline.process(ws, b"audio-fake"))

    assert "acao" not in ws.tipos
    assert ws.texto_de("frase") == ["Oi!"]  # a fala continua normal

    monkeypatch.setattr(settings, "ACTIONS_ENABLED", True)
    pipeline = make_pipeline(stt=FakeSTT("oi"), llm=FakeLLM(chunks), tts=FakeTTS())

    ws = FakeWebSocket()
    asyncio.run(pipeline.process(ws, b"audio-fake"))

    assert {"type": "acao", "nome": "som", "args": {"tipo": "bip"}} in ws.jsons
    assert ws.texto_de("frase") == ["Oi!"]
