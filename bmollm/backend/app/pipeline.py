import asyncio
import tempfile
from pathlib import Path

from .llm import LLMEngine
from .parsing import ResponseParser
from .segmentation import SentenceSplitter
from .stt import STTEngine
from .tts import SAMPLE_RATE, TTSEngine


class BmoPipeline:
    """Orquestra STT -> LLM -> TTS com streaming frase a frase."""

    def __init__(self):
        self.stt = STTEngine()
        self.llm = LLMEngine()
        self.tts = TTSEngine()

    async def process(self, ws, audio_bytes: bytes):
        audio_path = None
        try:
            audio_path = await self._save_audio(audio_bytes)

            texto = await asyncio.to_thread(self.stt.transcribe, audio_path)
            await ws.send_json({"type": "transcricao", "texto": texto})

            if not texto.strip():
                await ws.send_json({"type": "erro", "mensagem": "Não entendi o que você disse."})
                return

            await ws.send_json({"type": "estado", "estado": "pensando"})

            parser = ResponseParser()
            splitter = SentenceSplitter()
            emotion_sent = False
            meta_sent = False

            async for chunk, done in self.llm.generate(texto):
                parser.feed(chunk)

                if parser.emotion is not None and not emotion_sent:
                    emotion_sent = True
                    await ws.send_json({"type": "emocao", "emocao": parser.emotion})

                ready = parser.drain_text()
                if ready:
                    for sentence in splitter.feed(ready):
                        meta_sent = await self._speak(ws, sentence, meta_sent)

                if done:
                    break

            for sentence in splitter.flush():
                meta_sent = await self._speak(ws, sentence, meta_sent)

            if not emotion_sent:
                await ws.send_json({"type": "emocao", "emocao": "neutro"})

            if meta_sent:
                await ws.send_json({"type": "audio_fim"})
        except Exception as e:
            try:
                await ws.send_json({"type": "erro", "mensagem": str(e)})
            except Exception:
                pass
        finally:
            if audio_path is not None:
                try:
                    audio_path.unlink(missing_ok=True)
                except OSError:
                    pass

    async def _speak(self, ws, sentence: str, meta_sent: bool) -> bool:
        if not sentence.strip():
            return meta_sent
        if not meta_sent:
            await ws.send_json({
                "type": "audio_meta",
                "rate": SAMPLE_RATE,
                "channels": 1,
                "fmt": "int16",
            })
        pcm = await asyncio.to_thread(self.tts.synthesize_sentence, sentence)
        if pcm:
            await ws.send_json({"type": "frase", "texto": sentence})
            await ws.send_bytes(pcm)
            return True
        return meta_sent

    async def _save_audio(self, audio_bytes: bytes) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        tmp.write(audio_bytes)
        tmp.close()
        return Path(tmp.name)
