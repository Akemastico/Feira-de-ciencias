import json

import httpx

from .actions import acoes_schema
from .config import settings


class LLMError(RuntimeError):
    """Falha ao falar com o Ollama. A mensagem já está pronta para o usuário."""


class LLMEngine:
    """Cliente Ollama com saída JSON estruturada e streaming."""

    def __init__(self):
        self.url = f"{settings.OLLAMA_URL}/api/generate"
        self._client = None
        self.schema = {
            "type": "object",
            "properties": {
                "emocao": {"enum": settings.EMOTIONS},
                "resposta": {"type": "string"},
            },
            "required": ["emocao", "resposta"],
        }
        self.system_prompt = (
            "/no_think "
            "Você é o BMO, um robô pequeno, gentil e curioso do Adventure Time. "
            "Responda SEMPRE em português do Brasil, com 1 a 3 frases curtas. "
            "Você DEVE responder em JSON estrito com as chaves 'emocao' e 'resposta', nessa ordem. "
            "A emocao deve ser exatamente uma destas: "
            + ", ".join(settings.EMOTIONS)
            + ". Escolha a emocao que melhor combina com o conteudo da resposta e "
              "varie entre respostas consecutivas (evite repetir a mesma emocao). "
              "Guia: neutro=informacao, feliz=boas noticias/elogio, triste=empatia, "
              "surpreso=novidade, curioso=pergunta/interesse, bravo=protesto leve. "
              "Nao inclua raciocinio, tags de pensamento ou markdown."
        )

        # Ações só entram no schema e no prompt quando a flag está ligada.
        # Com a flag desligada o modelo nem é perguntado por elas.
        if settings.ACTIONS_ENABLED:
            self.schema["properties"]["acoes"] = acoes_schema()
            self.system_prompt = (
                self.system_prompt
                + " Se fizer sentido, inclua 'acoes' antes de 'resposta': uma lista de "
                  "objetos com 'nome' e 'args'. Ações permitidas: expressao, animacao, "
                  "texto, led, som. Nunca invente nomes ou argumentos."
            )

    def _timeout(self) -> httpx.Timeout:
        # read generoso: o Ollama pode levar dezenas de segundos para carregar
        # o modelo na primeira chamada. O importante é não esperar para sempre.
        return httpx.Timeout(
            connect=settings.OLLAMA_TIMEOUT_CONNECT,
            read=settings.OLLAMA_TIMEOUT_READ,
            write=10.0,
            pool=5.0,
        )

    async def _get_client(self):
        if self._client is None or getattr(self._client, "is_closed", False):
            self._client = httpx.AsyncClient(
                timeout=self._timeout(),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def aclose(self):
        if self._client is not None and not getattr(self._client, "is_closed", False):
            await self._client.aclose()
            self._client = None

    async def generate(self, user_text: str, max_tokens: int | None = None):
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": user_text,
            "system": self.system_prompt,
            "stream": True,
            "format": self.schema,
            "think": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "num_ctx": settings.OLLAMA_NUM_CTX,
                "num_predict": (
                    settings.OLLAMA_NUM_PREDICT if max_tokens is None else max_tokens
                ),
                "temperature": settings.OLLAMA_TEMPERATURE,
            },
        }

        try:
            client = await self._get_client()
            async with client.stream("POST", self.url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if data.get("error"):
                            raise LLMError(
                                "O Ollama deu um erro. Confere se o modelo está baixado?"
                            )
                        text = data.get("response", "")
                        done = bool(data.get("done", False))
                        yield text, done
                        if done:
                            break
        except httpx.ConnectError as exc:
            raise LLMError("Não consegui falar com o Ollama. Ele está aberto?") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("Meu cérebro demorou demais pra responder. Tenta de novo?") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                "O Ollama recusou o pedido. Confere se o modelo está baixado?"
            ) from exc
