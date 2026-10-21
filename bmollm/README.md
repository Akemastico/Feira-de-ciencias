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

## Memória de conversa

O BMO lembra das **últimas 3 trocas** e usa esse histórico ao responder. Após
isso, as trocas antigas são descartadas para não estourar o `num_ctx` de 2048
tokens. O histórico é por instância do servidor — se duas pessoas usarem o bot
ao mesmo tempo, as conversas se misturam (bom pra feira, onde é uma pessoa por
vez).

Abra `http://127.0.0.1:8000/health` antes de apresentar. Ele diz o que já está
pronto e o que falta, sem precisar ler o terminal:

```json
{
  "servidor": "ok",
  "pronto": false,
  "engines": {
    "stt": {"estado": "erro", "detalhe": "No module named 'faster_whisper'"},
    "llm": {"estado": "ok"},
    "tts": {"estado": "erro", "detalhe": "No module named 'kokoro'"}
  },
  "ollama": {"estado": "ok", "modelo": "qwen3:4b", "modelo_baixado": false}
}
```

- `estado`: `ok`, `nao_carregado` (vai carregar na primeira pergunta) ou `erro` (com o motivo).
- HTTP **200** = tudo pronto. **503** = falta alguma coisa; o JSON explica o quê.
- O servidor **sobe mesmo sem** Whisper, Kokoro ou espeak-ng instalados. Nesse
  caso, em vez de morrer, ele responde no navegador: *"Não consegui carregar o
  reconhecimento de voz."* e libera a tela para tentar de novo.

Por padrão (`BMO_PRELOAD=1`) Whisper e Kokoro são carregados em segundo plano
enquanto o servidor já atende. Use `BMO_PRELOAD=0` para carregar só na primeira
pergunta (bom em máquina fraca).

## Testes (sem GPU, sem modelo, sem Ollama)

O fluxo inteiro é testado com dublês no lugar das engines: o "navegador" manda
bytes pelo WebSocket e a gente confere as mensagens que voltam.

```cmd
pip install -r requirements-dev.txt
python -m pytest tests -q
```

Cobrem: fluxo completo (transcrição → emoção → fala), áudio sem fala, erro no
STT, Ollama fora do ar, TTS quebrado, resposta vazia do LLM, engine que não
carrega, `/health`, `/` e o envio de áudio pelo WebSocket.

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

Diagnóstico completo (carrega tudo, gera fala, transcreve de volta e mede):

```cmd
python backend/scripts/smoke_real.py
```

Teste de ponta a ponta pelo WebSocket, sem navegador e sem microfone — manda um
áudio e salva a resposta falada do BMO em WAV:

```cmd
python backend/scripts/e2e_ws.py caminho\para\audio.webm --out resposta.wav
```

### Números medidos (CPU sem GPU, `qwen3:4b`, Whisper `medium` int8)

| Etapa | Tempo |
|---|---|
| Carregar Whisper + Kokoro | ~76s na primeira vez (inclui download); ~8s depois |
| STT de uma fala de 3s | ~10s |
| LLM: primeira frase (modelo já aquecido) | ~5s |
| TTS por frase | ~1,5–6s |
| **Primeiro áudio ao público** | **~20s** |
| Resposta completa (3 frases) | ~30s |

O Whisper em CPU é o gargalo. `WHISPER_MODEL=small` corta boa parte disso ao
custo de ouvir um pouco pior em ambiente barulhento.

## Estrutura

- `backend/app/` — FastAPI, STT, LLM, TTS e orquestração
- `backend/scripts/` — scripts de benchmark/teste (Fase 1)
- `tests/` — testes com mocks (rodam sem GPU/modelo/Ollama)
- `frontend/` — Three.js, áudio, WebSocket e UI
- `frontend/assets/` — modelo 3D do BMO (`bmo.glb`); sem o arquivo, o BMO
  procedural (feito de código) aparece no lugar
- `frontend/vendor/three/` — three.js offline (vendored na Fase 3)
- `logs/bmo.log` — log da execução (criado automaticamente)

## Variáveis de `.env`

| Variável | Padrão | Para que serve |
|---|---|---|
| `OLLAMA_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / `qwen3:4b` | onde está o LLM |
| `OLLAMA_NUM_PREDICT` | `256` | teto de tokens da resposta (resposta longa = fala longa) |
| `OLLAMA_TIMEOUT_CONNECT` / `OLLAMA_TIMEOUT_READ` | `5` / `120` | segundos; evita espera infinita se o Ollama travar |
| `WHISPER_MODEL` | `medium` | `small` é mais rápido, `medium` ouve melhor |
| `KOKORO_VOICE` | `pf_dora` | voz pt-BR do Kokoro |
| `LOG_TO_FILE` / `LOG_FILE` | `1` / `logs/bmo.log` | log em arquivo para conferir depois |
| `BMO_PRELOAD` | `1` | carrega Whisper/Kokoro no boot, em segundo plano |

