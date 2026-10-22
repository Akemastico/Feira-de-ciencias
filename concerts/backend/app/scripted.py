import asyncio
import logging

from .tts import SAMPLE_RATE

log = logging.getLogger(__name__)

# Tokens que o cliente E2E manda como bytes UTF-8 no lugar do áudio.
CENARIOS = {
    b"ok": {
        "transcricao": "oi bmo",
        "emocao": "feliz",
        "frases": ["Oi! Eu sou o BMO."],
    },
    b"erro": {"erro": "teste de erro"},
    b"vazio": {
        "transcricao": "",
        "frases": ["Não ouvi nada. Segura o botão e fala pertinho?"],
    },
    b"longo": {
        "transcricao": "me conta uma historia",
        "emocao": "curioso",
        "frases": [
            "Era uma vez um robô pequeno.",
            "Ele morava em uma casa de madeira.",
            "Um dia ele encontrou uma estrela.",
            "E os dois viraram amigos para sempre.",
        ],
    },
    # O modelo pediu as cinco ações: expressão, animação, texto, LED e som.
    b"acoes": {
        "transcricao": "faz uma gracinha",
        "emocao": "feliz",
        "acoes": [
            {"nome": "expressao", "args": {"emocao": "feliz"}},
            {"nome": "animacao", "args": {"nome": "pular", "duracao": 5.0}},
            {"nome": "texto", "args": {"texto": "Olha eu pulando!"}},
            {"nome": "led", "args": {"cor": "#ff0000", "piscar": False}},
            {"nome": "som", "args": {"tipo": "bip"}},
        ],
        "frases": ["Olha eu pulando!"],
    },
    # Ações que não valem: nome fora da allowlist, animação desconhecida e
    # cor fora do formato. O modo de ensaio manda tudo cru, sem filtrar, para
    # o frontend provar que sabe descartar o que não é ação válida.
    b"acao_invalida": {
        "transcricao": "testa acao invalida",
        "emocao": "neutro",
        "acoes": [
            {"nome": "hackear", "args": {}},
            {"nome": "animacao", "args": {"nome": "voar"}},
            {"nome": "led", "args": {"cor": "vermelho"}},
        ],
        "frases": ["Continuo aqui!"],
    },
}


class ScriptedPipeline:
    """Pipeline de ensaio: respostas prontas, sem Whisper, Ollama ou Kokoro.

    Usado só quando BMO_E2E=1 (testes Playwright). O cliente manda um token
    em texto UTF-8 no lugar do áudio e recebe as mesmas mensagens que o
    pipeline real mandaria, então o frontend é exercitado de verdade.
    """

    async def process(self, ws, audio_bytes: bytes):
        token = audio_bytes.decode("utf-8", errors="ignore").strip().encode()
        cenario = CENARIOS.get(token, CENARIOS[b"ok"])

        try:
            if "erro" in cenario:
                await self._send_json(ws, {"type": "erro", "mensagem": cenario["erro"]})
                return

            await self._send_json(ws, {"type": "transcricao", "texto": cenario["transcricao"]})
            await self._send_json(ws, {"type": "estado", "estado": "pensando"})

            if cenario.get("emocao"):
                await self._send_json(ws, {"type": "emocao", "emocao": cenario["emocao"]})

            # Ações do modelo: nome e args, sem código. Quem confere se a
            # ação vale é o frontend (allowlist do dispatcher).
            for acao in cenario.get("acoes", []):
                await self._send_json(ws, {
                    "type": "acao",
                    "nome": acao["nome"],
                    "args": acao["args"],
                })

            # Uma única vez, como o pipeline real faz antes do primeiro PCM.
            await self._send_json(ws, {
                "type": "audio_meta",
                "rate": SAMPLE_RATE,
                "channels": 1,
                "fmt": "int16",
            })

            for frase in cenario.get("frases", ()):
                # Pausa curta para o frontend conseguir desenhar o streaming.
                await asyncio.sleep(0.03)
                await self._send_json(ws, {"type": "frase", "texto": frase})
                # 0,1 s de silêncio PCM: o navegador toca como se fosse fala.
                await ws.send_bytes(b"\x00\x00" * 2400)

            await self._send_json(ws, {"type": "audio_fim"})
        finally:
            # Nunca deixa a interface presa em "pensando".
            await self._send_json(ws, {"type": "estado", "estado": "pronto"})

    def status(self) -> dict:
        return {
            "stt": {"estado": "ok"},
            "llm": {"estado": "ok"},
            "tts": {"estado": "ok"},
        }

    async def warmup(self):
        return None

    @staticmethod
    async def _send_json(ws, payload: dict):
        try:
            await ws.send_json(payload)
        except Exception:
            log.debug("Cliente E2E desconectado; mensagem descartada: %s", payload.get("type"))
