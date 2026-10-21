import json

import httpx

from .config import settings


class LLMError(RuntimeError):
    """Falha ao falar com o Ollama. A mensagem já está pronta para o usuário."""


class LLMEngine:
    """Cliente Ollama com saída JSON estruturada e streaming."""

    def __init__(self):
        self.url = f"{settings.OLLAMA_URL}/api/generate"
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
            + ". Não inclua raciocínio, tags de pensamento ou markdown."
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
                "temperature": 0.7,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout()) as client:
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
