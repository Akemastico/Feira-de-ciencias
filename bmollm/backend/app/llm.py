import json
import httpx
from .config import settings


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

    async def generate(self, user_text: str):
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
                "temperature": 0.7,
            },
        }
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", self.url, json=payload, timeout=None) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("error"):
                        raise RuntimeError(data["error"])
                    text = data.get("response", "")
                    done = bool(data.get("done", False))
                    yield text, done
                    if done:
                        break
