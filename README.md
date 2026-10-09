# BMO-LLM

Assistente de voz 100% offline para feira de ciências: BMO (Adventure Time) responde em português com STT (Whisper), LLM (Qwen3 via Ollama) e TTS (Kokoro), tudo rodando localmente.

## Arquitetura

```
Frontend (Three.js)  <--WebSocket-->  Backend (FastAPI)
                                         │
            STT (faster-whisper, CPU int8) │ LLM (Ollama qwen3:4b, GPU) │ TTS (Kokoro, CPU)
```

## Requisitos

- Windows
- Python **3.10–3.12** (recomendado 3.12)
- [Ollama](https://ollama.com)
- [espeak-ng](https://github.com/espeak-ng/espeak-ng/releases) (MSI do Windows, necessário para Kokoro em pt-BR)
- PC alvo: GPU NVIDIA RTX 2050 4GB + 32GB RAM

## Setup

1. Instale o Ollama e baixe o modelo:
   ```cmd
   ollama pull qwen3:4b
   ```

2. Instale o espeak-ng via MSI do release oficial.

3. Crie o ambiente virtual e instale as dependências:
   ```cmd
   cd C:\Users\AKemistico\Documents\bmollm
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. Configure:
   ```cmd
   copy .env.example .env
   ```
   Edite `.env` se quiser ajustar modelo, voz, etc.

## Execução

```cmd
.\run.bat
```

Ou manualmente:
```cmd
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Página de teste do pipeline (sem 3D): `http://127.0.0.1:8000/test.html`

## Protocolo WebSocket (`/ws`)

Cliente → servidor: mensagem binária com áudio (webm/opus do MediaRecorder).

Servidor → cliente (JSON tipado + binário):

| Tipo | Conteúdo |
|---|---|
| `transcricao` | `{texto}` — o que o Whisper ouviu |
| `estado` | `{estado}` — ex: `pensando` |
| `emocao` | `{emocao}` — ex: `feliz` |
| `audio_meta` | `{rate, channels, fmt}` — 24000 Hz, 1 ch, int16 |
| `frase` | `{texto}` — legenda, seguida de 1 chunk PCM binário |
| `audio_fim` | fim da resposta |
| `parar` | barge-in (nova gravação interrompeu a anterior) |
| `erro` | `{mensagem}` |

## Benchmarks (Fase 1)

```cmd
python backend/scripts/test_tts.py
python backend/scripts/test_stt.py <arquivo.wav>
python backend/scripts/test_llm.py
```

## Estrutura

- `backend/app/` — FastAPI, STT, LLM, TTS e orquestração
- `backend/scripts/` — scripts de benchmark/teste (Fase 1)
- `frontend/` — Three.js, áudio, WebSocket e UI
- `frontend/assets/` — modelo 3D do BMO (`bmo.glb`)
- `frontend/vendor/three/` — three.js offline (vendored na Fase 3)
