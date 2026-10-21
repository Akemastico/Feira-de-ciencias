"""Dublês usados nos testes: nada de modelo real, nada de GPU."""


def make_pipeline(**engines):
    """BmoPipeline com engines injetadas (nenhuma é carregada de verdade)."""
    from backend.app.pipeline import BmoPipeline

    return BmoPipeline(**engines)


class FakeWebSocket:
    """Captura o que o pipeline mandaria para o navegador."""

    def __init__(self):
        self.events = []

    async def send_json(self, payload):
        self.events.append(("json", payload))

    async def send_bytes(self, data):
        self.events.append(("bytes", data))

    @property
    def tipos(self):
        return [payload.get("type") for kind, payload in self.events if kind == "json"]

    @property
    def jsons(self):
        return [payload for kind, payload in self.events if kind == "json"]

    @property
    def bytes(self):
        return [data for kind, data in self.events if kind == "bytes"]

    def texto_de(self, tipo):
        return [p.get("texto", p.get("mensagem", "")) for p in self.jsons if p.get("type") == tipo]


class FakeSTT:
    def __init__(self, texto="oi bmo", erro=None):
        self.texto = texto
        self.erro = erro
        self.chamadas = 0

    def transcribe(self, audio_path):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return self.texto


class FakeLLM:
    """Entrega os chunks prontos, como o Ollama faria no streaming."""

    def __init__(self, chunks=None, erro=None):
        self.chunks = chunks if chunks is not None else []
        self.erro = erro
        self.prompts = []

    async def generate(self, user_text, max_tokens=None):
        self.prompts.append(user_text)
        if self.erro:
            raise self.erro
        for chunk, done in self.chunks:
            yield chunk, done


class FakeTTS:
    def __init__(self, pcm=b"\x00\x01" * 8, erro=None):
        self.pcm = pcm
        self.erro = erro
        self.falas = []

    def synthesize_sentence(self, text):
        self.falas.append(text)
        if self.erro:
            raise self.erro
        return self.pcm
