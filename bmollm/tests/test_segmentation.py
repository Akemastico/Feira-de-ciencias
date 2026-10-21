from backend.app.segmentation import SentenceSplitter


def test_quebra_uma_frase_por_vez_mesmo_com_texto_aos_poucos():
    splitter = SentenceSplitter()
    assert splitter.feed("Oi! Tu") == ["Oi!"]
    assert splitter.feed("do bem?") == ["Tudo bem?"]
    assert splitter.flush() == []


def test_nao_quebra_em_abreviacao():
    splitter = SentenceSplitter()
    assert splitter.feed("O Sr. Silva chegou.") == ["O Sr. Silva chegou."]


def test_resto_sem_pontuacao_sai_no_flush():
    splitter = SentenceSplitter()
    assert splitter.feed("sem ponto final") == []
    assert splitter.flush() == ["sem ponto final"]


def test_flush_vazio_nao_gera_frase():
    splitter = SentenceSplitter()
    assert splitter.flush() == []
