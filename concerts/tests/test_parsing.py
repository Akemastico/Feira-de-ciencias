from backend.app.parsing import ResponseParser


def test_extrai_emocao_e_texto_com_stream_quebrado():
    parser = ResponseParser()
    saida = ""
    for pedaco in ['{"emo', 'cao": "feliz", "respo', 'sta": "Oi! Tudo', ' bem?"}']:
        parser.feed(pedaco)
        saida += parser.drain_text()

    assert parser.emotion == "feliz"
    assert saida == "Oi! Tudo bem?"


def test_nao_engole_caractere_de_escape_partido():
    parser = ResponseParser()
    parser.feed('{"emocao":"neutro","resposta":"linha1\\nlin')
    assert parser.drain_text() == "linha1\nlin"  # não corta no meio do "\n" pendente

    parser.feed('ha2"}')
    assert parser.drain_text() == "ha2"


def test_acentos_em_unicode_escape():
    parser = ResponseParser()
    parser.feed('{"emocao":"feliz","resposta":"ol\\u00e1"}')
    saida = parser.drain_text()

    assert saida == "olá"


def test_resposta_ausente_nao_quebra():
    parser = ResponseParser()
    parser.feed('{"emocao":"triste"}')

    assert parser.emotion == "triste"
    assert parser.drain_text() == ""
