import asyncio
import logging
import tempfile
import threading
import unicodedata
from pathlib import Path

from .llm import LLMEngine, LLMError
from .parsing import ResponseParser
from .segmentation import SentenceSplitter
from .stt import STTEngine
from .tts import SAMPLE_RATE, TTSEngine

log = logging.getLogger(__name__)

_ENGINE_NAMES = ("stt", "llm", "tts")

# Frases faladas para o público quando algo dá errado no meio da apresentação.
_FALLBACK_FALA = "Hmm, me perdi aqui. Pode falar de novo?"

_ENGINE_MESSAGE = {
    "stt": "Não consegui carregar o reconhecimento de voz.",
    "llm": "Não consegui falar com o Ollama. Ele está aberto?",
    "tts": "Não consegui carregar a voz do BMO.",
}


class EngineUnavailable(RuntimeError):
    """Engine não carregou. A mensagem já está pronta para mostrar ao usuário."""


def limpar_para_fala(texto: str) -> str:
    """Remove emoji e símbolos que o TTS não sabe falar.

    O LLM às vezes devolve '😊' como frase separada — sem isso o Kokoro
    tentava sintetizar um emoji em vez de ficar quieto.
    """
    return "".join(c for c in texto if unicodedata.category(c)[:1] in "LNPZ")


class BmoPipeline:
    """Orquestra STT -> LLM -> TTS com streaming frase a frase.

    As engines são carregadas sob demanda. Importar este módulo (ou subir o
    servidor) não baixa nem carrega modelo nenhum: se algo faltar na máquina,
    o servidor continua de pé e o problema aparece em /health.
    """

    def __init__(self, stt=None, llm=None, tts=None):
        self._overrides = {"stt": stt, "llm": llm, "tts": tts}
        self._engines = {}
        self._errors = {}
        self._locks = {name: threading.Lock() for name in _ENGINE_NAMES}

    def _build(self, name):
        return {"stt": STTEngine, "llm": LLMEngine, "tts": TTSEngine}[name]()

    def get_engine(self, name: str):
        engine = self._engines.get(name)
        if engine is not None:
            return engine

        override = self._overrides.get(name)
        if override is not None:
            self._engines[name] = override
            return override

        with self._locks[name]:
            engine = self._engines.get(name)
            if engine is not None:
                return engine
            try:
                engine = self._build(name)
            except Exception as exc:
                self._errors[name] = str(exc) or exc.__class__.__name__
                log.exception("Falha ao carregar engine %r", name)
                raise EngineUnavailable(_ENGINE_MESSAGE[name]) from exc
            self._engines[name] = engine
            self._errors.pop(name, None)
            log.info("Engine %r carregada", name)
            return engine

    def preload(self):
        """Carrega todas as engines (bloqueante — chamar fora do event loop)."""
        for name in _ENGINE_NAMES:
            try:
                self.get_engine(name)
            except EngineUnavailable:
                pass  # já logado; /health mostra o motivo

    async def warmup(self):
        """Deixa tudo quente antes do público chegar.

        Carrega as engines e faz uma pergunta mínima ao Ollama: sem isso, a
        primeira pergunta da apresentação paga o carregamento do modelo.
        """
        try:
            await asyncio.to_thread(self.preload)
        except Exception:
            log.exception("Falha no pré-carregamento")

        try:
            llm = self.get_engine("llm")
            async for _chunk, done in llm.generate("oi", max_tokens=1):
                if done:
                    break
            log.info("Ollama aquecido")
        except Exception as exc:
            log.warning("Não consegui aquecer o Ollama: %s", exc)

    def status(self) -> dict:
        out = {}
        for name in _ENGINE_NAMES:
            if name in self._engines:
                out[name] = {"estado": "ok"}
            elif name in self._errors:
                out[name] = {"estado": "erro", "detalhe": self._errors[name]}
            else:
                out[name] = {"estado": "nao_carregado"}
        return out

    async def process(self, ws, audio_bytes: bytes):
        audio_path = None
        try:
            audio_path = await self._save_audio(audio_bytes)

            try:
                stt = self.get_engine("stt")
            except EngineUnavailable as exc:
                await self._send_json(ws, {"type": "erro", "mensagem": str(exc)})
                return

            try:
                texto = await asyncio.to_thread(stt.transcribe, audio_path)
            except Exception:
                log.exception("Falha na transcrição")
                await self._send_json(ws, {
                    "type": "erro",
                    "mensagem": "Não consegui entender o áudio. Tenta de novo?",
                })
                return

            await self._send_json(ws, {"type": "transcricao", "texto": texto})

            if not texto.strip():
                await self._send_fala(ws, "Não ouvi nada. Segura o botão e fala pertinho?")
                return

            await self._send_json(ws, {"type": "estado", "estado": "pensando"})

            try:
                llm = self.get_engine("llm")
            except EngineUnavailable as exc:
                await self._send_json(ws, {"type": "erro", "mensagem": str(exc)})
                return

            falou = await self._stream_answer(ws, llm, texto)

            if not falou:
                log.warning("Resposta vazia do LLM; usando fallback falado")
                await self._send_fala(ws, _FALLBACK_FALA)
        except Exception:
            log.exception("Falha inesperada no pipeline")
            await self._send_json(ws, {
                "type": "erro",
                "mensagem": "Deu um probleminha aqui. Pode falar de novo?",
            })
        finally:
            if audio_path is not None:
                try:
                    audio_path.unlink(missing_ok=True)
                except OSError:
                    pass
            # Nunca deixa a interface presa em "pensando".
            await self._send_json(ws, {"type": "estado", "estado": "pronto"})

    async def _stream_answer(self, ws, llm, texto: str) -> bool:
        parser = ResponseParser()
        splitter = SentenceSplitter()
        emotion_sent = False
        meta_sent = False
        falou = False

        try:
            async for chunk, done in llm.generate(texto):
                parser.feed(chunk)

                if parser.emotion is not None and not emotion_sent:
                    emotion_sent = True
                    await self._send_json(ws, {"type": "emocao", "emocao": parser.emotion})

                ready = parser.drain_text()
                if ready:
                    for sentence in splitter.feed(ready):
                        meta_sent, tratou = await self._speak(ws, sentence, meta_sent)
                        falou = falou or tratou

                if done:
                    break
        except LLMError as exc:
            log.warning("LLM indisponível: %s", exc)
            await self._send_json(ws, {"type": "erro", "mensagem": str(exc)})
            return True
        except Exception:
            log.exception("Falha no streaming do LLM")
            await self._send_json(ws, {
                "type": "erro",
                "mensagem": "Meu cérebro deu um nó. Pode repetir?",
            })
            return True

        for sentence in splitter.flush():
            meta_sent, tratou = await self._speak(ws, sentence, meta_sent)
            falou = falou or tratou

        if not emotion_sent:
            await self._send_json(ws, {"type": "emocao", "emocao": "neutro"})

        if meta_sent:
            await self._send_json(ws, {"type": "audio_fim"})

        return falou

    async def _speak(self, ws, sentence: str, meta_sent: bool) -> tuple[bool, bool]:
        """Devolve (audio_meta_já_enviado, tratou_a_frase)."""
        sentence = limpar_para_fala(sentence).strip()
        if not sentence or not any(c.isalnum() for c in sentence):
            return meta_sent, False

        try:
            tts = self.get_engine("tts")
        except EngineUnavailable as exc:
            # Sem voz o BMO ainda pode responder por legenda.
            await self._send_json(ws, {"type": "erro", "mensagem": str(exc)})
            await self._send_json(ws, {"type": "frase", "texto": sentence})
            return meta_sent, True

        try:
            pcm = await asyncio.to_thread(tts.synthesize_sentence, sentence)
        except Exception:
            log.exception("Falha ao sintetizar fala")
            await self._send_json(ws, {"type": "frase", "texto": sentence})
            return meta_sent, True

        if not pcm:
            return meta_sent, False

        if not meta_sent:
            meta_sent = True
            await self._send_json(ws, {
                "type": "audio_meta",
                "rate": SAMPLE_RATE,
                "channels": 1,
                "fmt": "int16",
            })

        await self._send_json(ws, {"type": "frase", "texto": sentence})
        await ws.send_bytes(pcm)
        return True, True

    async def _send_fala(self, ws, frase: str):
        """Fala uma frase pronta (fallback / aviso), sem passar pelo LLM."""
        await self._send_json(ws, {"type": "estado", "estado": "pensando"})
        meta_sent, _tratou = await self._speak(ws, frase, False)
        await self._send_json(ws, {"type": "emocao", "emocao": "neutro"})
        if meta_sent:
            await self._send_json(ws, {"type": "audio_fim"})

    @staticmethod
    async def _send_json(ws, payload: dict):
        try:
            await ws.send_json(payload)
        except Exception:
            log.debug("Cliente desconectado; mensagem descartada: %s", payload.get("type"))

    async def _save_audio(self, audio_bytes: bytes) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        tmp.write(audio_bytes)
        tmp.close()
        return Path(tmp.name)
