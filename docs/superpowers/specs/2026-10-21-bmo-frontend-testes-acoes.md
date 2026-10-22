# BMO — Análise do processo, testes de frontend e preparação para ações

**Data:** 2026-10-21  
**Repositório:** `~/Documentos/Estudo/Feira-de-ciencias`  
**Alvo:** `bmollm/` (backend FastAPI + frontend Three.js)  
**Status:** análise concluída e contrato proposto para revisão; nenhuma mudança de código feita ainda.

> Observação de caminho: o BMO fica em `~/Documentos/Estudo/Feira-de-ciencias`.
> A pasta `~/Documentos/FeiraDeCiencias` contém outro projeto (`GestosGatos`).

---

## 1. Objetivo

1. Colocar o frontend do BMO sob teste automatizado, sem depender de GPU, Ollama,
   Whisper, Kokoro ou microfone real.
2. Corrigir o que impede o frontend de rodar hoje.
3. Preparar o contrato de **ações** que o modelo novo (a ser enviado) vai emitir,
   deixando um ponto de extensão claro para trocar o modelo sem reescrever o
   frontend.
4. Manter o funcionamento atual (voz, legenda, emoção, barge-in) intacto.

---

## 2. Arquitetura atual

```
Navegador
  index.html
    └─ src/main.js
         ├─ Bmo (Three.js procedural ou bmo.glb)
         ├─ AudioManager (MediaRecorder + Web Audio)
         ├─ UI (botão, estados, legendas)
         └─ WSClient (WebSocket /ws)
                │
                ▼
Backend FastAPI
  main.py
    ├─ /            → index.html
    ├─ /test.html   → página de teste sem 3D
    ├─ /health      → diagnóstico de engines + Ollama
    ├─ /ws          → recebe áudio binário, devolve JSON + PCM
    └─ pipeline.py
         ├─ STT (faster-whisper, CPU int8)
         ├─ LLM (Ollama qwen3:4b, streaming JSON)
         ├─ ResponseParser (emocao + resposta)
         ├─ SentenceSplitter (frases para TTS)
         └─ TTS (Kokoro, PCM 24 kHz)
```

### 2.1 Fluxo completo de uma pergunta

1. A página carrega `index.html`, que importa `/src/main.js`.
2. `main.js` monta a cena Three.js, o BMO, a UI, o áudio e o `WSClient`.
3. O usuário segura o botão (ou Espaço):
   - `AudioManager.startRecording()` pede o microfone e inicia o `MediaRecorder`
     em `audio/webm;codecs=opus`.
4. Ao soltar:
   - `AudioManager.stopRecording()` devolve um `ArrayBuffer`;
   - `WSClient.sendAudio()` manda os bytes binários para `/ws`.
5. `main.websocket_endpoint` cancela a resposta anterior (se houver), envia
   `{"type":"parar"}` e cria uma task para `BmoPipeline.process`.
6. `pipeline.process`:
   - salva o áudio num `.webm` temporário;
   - chama `STTEngine.transcribe` em thread;
   - envia `{"type":"transcricao","texto":...}`;
   - se vazio, fala “Não ouvi nada…” e encerra;
   - envia `{"type":"estado","estado":"pensando"}`;
   - chama `LLMEngine.generate` e faz streaming.
7. `ResponseParser` extrai `emocao` e decodifica `resposta` aos poucos.
   `SentenceSplitter` fecha frases completas.
8. Para cada frase, `pipeline._speak`:
   - limpa emojis/símbolos com `limpar_para_fala`;
   - sintetiza com Kokoro em thread;
   - envia uma única `audio_meta` (24000 Hz, mono, int16);
   - envia `{"type":"frase","texto":...}` e, em seguida, o chunk PCM binário.
9. No fim: flush da última frase, emoção `neutro` se nenhuma foi enviada,
   `audio_fim` e, no `finally`, `{"type":"estado","estado":"pronto"}`.
10. O frontend:
    - atualiza legenda, transcrição, emoção e estado;
    - converte PCM int16 para float32 e agenda no `AudioContext` a 24 kHz;
    - usa o RMS do analyser para abrir a boca do BMO;
    - aplica emoção/estado no corpo e no rosto desenhado em canvas.
11. Barge-in: novos bytes cancelam a task anterior no servidor; o servidor manda
    `parar`; o frontend para as fontes de áudio.

### 2.2 Inventário de funções

| Arquivo | Função | Responsabilidade |
|---|---|---|
| `backend/app/config.py` | `Settings` | Lê `.env` e centraliza modelo, voz, timeouts, emoções e flags. |
| `backend/app/main.py` | `_setup_logging` | Configura log em terminal e arquivo. |
| | `root` / `pagina_de_teste` | Servem `index.html` e `test.html`. |
| | `_check_ollama` | Consulta `/api/tags` e confere se o modelo está baixado. |
| | `health` | Junta status das engines + Ollama; 200 ou 503. |
| | `websocket_endpoint` | Recebe áudio, cancela task anterior e dispara o pipeline. |
| `backend/app/pipeline.py` | `limpar_para_fala` | Remove emoji/símbolos que o TTS não fala. |
| | `BmoPipeline.get_engine` | Carrega engine sob demanda, com lock e erro amigável. |
| | `BmoPipeline.preload` / `warmup` | Pré-carrega engines e aquece o Ollama. |
| | `BmoPipeline.status` | Estado `ok` / `nao_carregado` / `erro` para `/health`. |
| | `BmoPipeline.process` | Orquestra STT → LLM → TTS e trata falhas. |
| | `BmoPipeline._stream_answer` | Consome o stream do LLM, emoção, frases e áudio. |
| | `BmoPipeline._speak` | Sintetiza uma frase e envia legenda + PCM. |
| | `BmoPipeline._send_fala` | Fala uma frase pronta (fallback/aviso). |
| `backend/app/llm.py` | `LLMEngine.generate` | Cliente Ollama com JSON schema, streaming e erros amigáveis. |
| `backend/app/parsing.py` | `ResponseParser.feed` / `drain_text` | Extrai emoção e texto de um JSON que chega em pedaços. |
| `backend/app/segmentation.py` | `SentenceSplitter.feed` / `flush` | Divide texto em frases, respeitando abreviações. |
| `backend/app/stt.py` | `STTEngine.transcribe` | Whisper em pt-BR com VAD. |
| `backend/app/tts.py` | `TTSEngine.synthesize_sentence` | Kokoro → PCM int16 24 kHz. |
| `frontend/src/main.js` | `handleJson` / `loop` | Liga eventos do WS à UI/BMO e anima a cena. |
| `frontend/src/ws.js` | `connect` / `sendAudio` | WebSocket com reconexão de 2 s. |
| `frontend/src/audio.js` | `startRecording` / `stopRecording` | MediaRecorder + permissões. |
| | `playChunk` / `stop` / `getLevel` | Agenda PCM, para tudo e mede volume para a boca. |
| `frontend/src/bmo.js` | `_buildProcedural` / `_tryLoadGlb` | Corpo procedural ou modelo GLB. |
| | `setEmotion` / `setState` / `update` | Estado e animação do corpo/rosto. |
| `frontend/src/ui.js` | `_bind` / setters | Botão, teclado e textos da HUD. |
| `frontend/test.html` | script inline | Página de teste que duplica áudio/WS sem 3D. |

### 2.3 Cobertura atual

- **Backend:** 24 testes em `bmollm/tests/` com dublês; passam em ~0,5 s.
  Cobrem pipeline, erros, `/health`, `/`, `/test.html`, WS e parser.
- **Frontend:** nenhum teste automatizado.
- **Scripts:** `e2e_ws.py` e `smoke_real.py` dependem de servidor/modelo/áudio real.

---

## 3. Achados da análise (com evidência)

### P0 — O frontend não carrega no estado atual

`frontend/vendor/three/GLTFLoader.js:68` importa:

```js
import { toTrianglesDrawMode } from '../utils/BufferGeometryUtils.js';
```

O arquivo `frontend/vendor/utils/BufferGeometryUtils.js` **não existe**. O
navegador tenta `/vendor/utils/BufferGeometryUtils.js`, recebe 404 e o módulo
`main.js` inteiro falha. Resultado verificado em Chromium:

- `#scene canvas` não é criado;
- status fica preso em `conectando…`;
- WebSocket nunca abre;
- nenhum erro visível na HUD (só no console).

Isso é bloqueante para qualquer teste de frontend e para a apresentação.

**Correção:** vendorizar `BufferGeometryUtils.js` da mesma versão do Three.js
(r160) em `frontend/vendor/utils/`, ou mudar o import para um caminho local.
Preferir vendorizar para manter o modo offline.

### P1 — Barge-in só acontece depois de soltar o botão

Hoje o áudio local continua tocando enquanto o usuário grava. O servidor só
cancela quando recebe os bytes (no `pointerup`). Para a feira, o BMO deve parar
de falar no `pointerdown`.

**Correção:** enviar `{"type":"interromper"}` ao começar a gravar e parar
`AudioManager`/animações localmente na hora.

### P1 — Transformações do BMO não são resetadas

`Bmo._applyBody` zera `rotation.z`, `rotation.x` e `scale`, mas não
`position.x`. Depois de `bravo`, o corpo pode ficar deslocado para sempre.
Além disso, `surpreso` usa `Math.exp(-t * 0.5)` com `t` global: o efeito só
funciona no começo da sessão.

**Correção:** resetar posição/rotação/escala a cada frame e medir animações por
tempo desde o gatilho.

### P2 — Fontes de áudio não são removidas

`AudioManager.playChunk` adiciona em `_sources`, mas nunca remove no `onended`.
Em uma apresentação longa, a lista cresce e `stop()` percorre fontes mortas.

### P2 — GLB substitui só o corpo

`_tryLoadGlb` remove `this.body`, mas mantém `screen`, `face` e botões
procedurais no grupo. Se `bmo.glb` existir, os dois modelos ficam sobrepostos.

### P2 — `sendAudio` falha em silêncio

Se o WebSocket estiver fechado, `sendAudio` não faz nada e a UI não avisa.

### P3 — Duplicação em `test.html`

A página de teste reimplementa áudio/WS. Toda mudança de protocolo precisa ser
feita duas vezes. Não é bloqueante, mas é uma fonte de divergência.

### P3 — Sem verificação de `/health` na UI

O usuário só descobre que falta engine abrindo `/health` manualmente.

---

## 4. Decisões de teste

- **Vitest + jsdom** para módulos puros (`ws.js`, `audio.js`, `actions.js`).
- **Playwright** para o navegador real (Canvas/WebGL, MediaRecorder, UI, ações).
- **Modo ensaio determinístico** no backend (`BMO_E2E=1`) para os E2E não
  dependerem de Ollama/Whisper/Kokoro.
- **Nenhum bundler**: o frontend continua com ES modules + importmap.
- Testes rodam em Linux e no Windows alvo; o comando do Python no Playwright é
  escolhido por `process.platform`.

---

## 5. Contrato de ações (preparação para o modelo novo)

### 5.1 Formato que o modelo deve devolver

```json
{
  "emocao": "feliz",
  "acoes": [
    {"nome": "expressao", "args": {"emocao": "feliz"}},
    {"nome": "animacao", "args": {"nome": "pular", "duracao": 1.2}},
    {"nome": "texto", "args": {"texto": "Oi!", "duracao": 4}},
    {"nome": "led", "args": {"cor": "#7ee0a8", "piscar": false}},
    {"nome": "som", "args": {"tipo": "bip"}}
  ],
  "resposta": "Oi! Que bom te ver!"
}
```

`acoes` é **opcional** e vem antes de `resposta` para que as ações cheguem antes
da fala. O parser também aceita `acoes` depois de `resposta`, mas nesse caso a
fala pode começar antes das ações.

### 5.2 Catálogo inicial

| Ação | Args | Valores |
|---|---|---|
| `expressao` | `emocao` | `neutro`, `feliz`, `triste`, `surpreso`, `curioso`, `bravo` |
| `animacao` | `nome`, `duracao` | `pular`, `dancar`, `tremer`, `acenar`, `olhar_lado`, `dormir`; 0,1–10 s (padrão 1,5) |
| `texto` | `texto`, `duracao` | 1–200 caracteres; 0,5–30 s (padrão 4) |
| `led` | `cor`, `piscar` | `#rrggbb`; booleano (padrão `false`) |
| `som` | `tipo` | `bip`, `erro`, `sucesso` |

Regras:
- Lista fechada; ação desconhecida é descartada no backend **e** no frontend.
- Argumentos inválidos são descartados sem derrubar a fala.
- Máximo de 8 ações por resposta.
- O frontend nunca executa código vindo do modelo; só chama handlers do registry.
- `BMO_ACOES=0` por padrão: o schema/prompt só pede ações quando o modelo novo
  estiver pronto. O parser e o frontend já ficam prontos e testados.

### 5.3 Protocolo WebSocket (aditivo)

Servidor → cliente:

```json
{"type": "acao", "nome": "animacao", "args": {"nome": "pular", "duracao": 1.2}}
```

Cliente → servidor (texto JSON, além do áudio binário):

```json
{"type": "interromper"}
```

Tudo o que existe hoje (`transcricao`, `estado`, `emocao`, `audio_meta`, `frase`,
`audio_fim`, `parar`, `erro`) continua igual.

### 5.4 Ponto de extensão do modelo

Quando o modelo chegar, a mudança fica restrita a:

1. `backend/app/llm.py` — schema, prompt e transporte (se não for Ollama).
2. `backend/app/actions.py` — mapear o vocabulário do modelo para o catálogo.
3. `.env` — `OLLAMA_MODEL` / `BMO_ACOES=1`.
4. `tests/fixtures/model_output_examples.json` — exemplos reais para teste de
   contrato, sem chamar o modelo.

O frontend e o protocolo não precisam mudar.

---

## 6. Perguntas para quando o modelo chegar

- Ele é compatível com Ollama (`/api/generate` + `format`)?
- Emite JSON estruturado, tool calls ou texto livre?
- Já tem um vocabulário de ações próprio? Se sim, mapeamos para o catálogo.
- Qual o tempo até o primeiro token? Isso define se as ações podem vir antes da
  fala ou precisam ser enviadas depois.
- Ele substitui o `qwen3:4b` ou roda em paralelo?

Nenhuma dessas respostas muda o contrato acima; mudam apenas o adaptador.

---

## 7. Fora de escopo

- Trocar o modelo ou instalar um runtime novo agora.
- Implementar o `bmo.glb` (o procedural continua sendo o padrão).
- Refatorar `test.html` para compartilhar módulos (pode vir depois).
- Trocar Three.js, adicionar bundler ou framework de UI.
- Deploy, autenticação ou acesso remoto.
