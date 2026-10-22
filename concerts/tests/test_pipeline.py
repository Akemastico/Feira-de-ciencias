import asyncio

from fakes import FakeLLM, FakeSTT, FakeTTS, FakeWebSocket, make_pipeline

JSON_OK = [
    ('{"emocao":"feliz","resposta":"Oi! ', False),
    ("Tudo bem? Sou o BMO.", False),
    ('"}', True),
]


def run(pipeline, audio=b"audio-fake"):
    ws = FakeWebSocket()
    asyncio.run(pipeline.process(ws, audio))
    return ws


def test_fluxo_completo_manda_audio_e_legenda():
    tts = FakeTTS()
    llm = FakeLLM(JSON_OK)
    pipeline = make_pipeline(stt=FakeSTT("oi bmo"), llm=llm, tts=tts)

    ws = run(pipeline)

    assert ws.tipos[0] == "transcricao"
    assert ws.jsons[0]["texto"] == "oi bmo"
    assert ws.jsons[1] == {"type": "estado", "estado": "pensando"}
    assert {"type": "emocao", "emocao": "feliz"} in ws.jsons
    assert ws.tipos[-1] == "estado" and ws.jsons[-1]["estado"] == "pronto"

    # uma única declaração de formato de áudio, antes do primeiro chunk
    assert ws.tipos.count("audio_meta") == 1
    indice_meta = [i for i, e in enumerate(ws.events) if e[0] == "json" and e[1]["type"] == "audio_meta"][0]
    indice_bytes = next(i for i, e in enumerate(ws.events) if e[0] == "bytes")
    assert indice_meta < indice_bytes

    assert ws.texto_de("frase") == ["Oi!", "Tudo bem?", "Sou o BMO."]
    assert len(ws.bytes) == 3
    assert ws.tipos.index("audio_fim") < len(ws.tipos) - 1

    assert llm.prompts == ["oi bmo"]  # LLM recebe texto, não áudio
    assert tts.falas == ["Oi!", "Tudo bem?", "Sou o BMO."]


def test_audio_sem_fala_pede_para_repetir():
    llm = FakeLLM(JSON_OK)
    pipeline = make_pipeline(stt=FakeSTT(""), llm=llm, tts=FakeTTS())

    ws = run(pipeline)

    assert "Não ouvi nada" in " ".join(ws.texto_de("frase"))
    assert llm.prompts == []  # não chama o LLM à toa
    assert ws.jsons[-1] == {"type": "estado", "estado": "pronto"}


def test_falha_no_stt_vira_erro_amigavel_e_libera_a_tela():
    pipeline = make_pipeline(
        stt=FakeSTT(erro=RuntimeError("ffmpeg explodiu")),
        llm=FakeLLM(JSON_OK),
        tts=FakeTTS(),
    )

    ws = run(pipeline)

    assert ws.tipos[0] == "erro"
    assert "entender o áudio" in ws.texto_de("erro")[0]
    assert "ffmpeg" not in ws.texto_de("erro")[0]  # detalhe técnico só no log
    assert ws.jsons[-1] == {"type": "estado", "estado": "pronto"}


def test_ollama_fora_do_ar_avisa_e_nao_trava():
    from backend.app.llm import LLMError

    pipeline = make_pipeline(
        stt=FakeSTT("oi"),
        llm=FakeLLM(erro=LLMError("Não consegui falar com o Ollama. Ele está aberto?")),
        tts=FakeTTS(),
    )

    ws = run(pipeline)

    assert ws.tipos[0] == "transcricao"
    assert "Ollama" in ws.texto_de("erro")[0]
    assert ws.jsons[-1] == {"type": "estado", "estado": "pronto"}


def test_tts_quebrado_ainda_mostra_legenda():
    pipeline = make_pipeline(
        stt=FakeSTT("oi"),
        llm=FakeLLM(JSON_OK),
        tts=FakeTTS(erro=RuntimeError("espeak-ng ausente")),
    )

    ws = run(pipeline)

    assert ws.texto_de("frase") == ["Oi!", "Tudo bem?", "Sou o BMO."]
    assert ws.bytes == []
    assert ws.tipos.count("audio_meta") == 0
    assert ws.jsons[-1]["estado"] == "pronto"


def test_resposta_vazia_do_llm_nao_deixa_a_tela_pendurada():
    vazio = [("", False), ("", True)]
    pipeline = make_pipeline(stt=FakeSTT("oi"), llm=FakeLLM(vazio), tts=FakeTTS())

    ws = run(pipeline)

    assert "me perdi" in " ".join(ws.texto_de("frase")).lower()
    assert ws.jsons[-1] == {"type": "estado", "estado": "pronto"}


def test_engine_que_nao_carrega_nao_derruba_o_processo():
    from backend.app.pipeline import BmoPipeline

    class PipelineQuebrado(BmoPipeline):
        def _build(self, name):
            raise RuntimeError("espeak-ng: command not found")

    pipeline = PipelineQuebrado()
    ws = run(pipeline)

    assert "reconhecimento de voz" in ws.texto_de("erro")[0]
    assert ws.jsons[-1]["estado"] == "pronto"

    status = pipeline.status()
    assert status["stt"]["estado"] == "erro"
    assert "espeak-ng" in status["stt"]["detalhe"]
    assert status["llm"]["estado"] == "nao_carregado"


def test_emoji_sozinho_nao_vira_fala():
    chunks = [('{"emocao":"feliz","resposta":"Oi! Que legal! 😊"}', True)]
    tts = FakeTTS()
    pipeline = make_pipeline(stt=FakeSTT("oi"), llm=FakeLLM(chunks), tts=tts)

    ws = run(pipeline)

    assert ws.texto_de("frase") == ["Oi!", "Que legal!"]
    assert all("😊" not in fala for fala in tts.falas)
    assert ws.jsons[-1]["estado"] == "pronto"


def test_warmup_carrega_engines_e_aquece_o_llm():
    llm = FakeLLM([('{"emocao":"neutro","resposta":"oi"}', True)])
    pipeline = make_pipeline(stt=FakeSTT(), llm=llm, tts=FakeTTS())

    asyncio.run(pipeline.warmup())

    assert llm.prompts == ["oi"]  # pergunta mínima para carregar o modelo
    assert pipeline.status()["stt"]["estado"] == "ok"


def test_warmup_nao_explode_quando_falta_dependencia():
    from backend.app.pipeline import BmoPipeline

    class PipelineQuebrado(BmoPipeline):
        def _build(self, name):
            raise RuntimeError("sem modulo")

    pipeline = PipelineQuebrado()
    asyncio.run(pipeline.warmup())  # não deve levantar

    assert pipeline.status()["tts"]["estado"] == "erro"
