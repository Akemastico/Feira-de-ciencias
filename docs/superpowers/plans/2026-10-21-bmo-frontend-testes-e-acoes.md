# BMO — Testes de Frontend e Preparação para Ações — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Colocar o frontend do BMO sob testes automatizados (Vitest + Playwright), corrigir o carregamento quebrado do Three.js e preparar o protocolo de ações que o modelo novo vai emitir.

**Architecture:** O frontend continua em ES modules puros, sem bundler. O backend ganha um modo ensaio determinístico (`BMO_E2E=1`) que substitui as engines por um pipeline roteirizado, permitindo testar WebSocket, UI, áudio e ações sem GPU/modelo. As ações são validadas por allowlist no backend, enviadas como `{"type":"acao",...}` pelo WebSocket e executadas no frontend por um `ActionDispatcher` que nunca usa `eval`.

**Tech Stack:** Python 3.12, FastAPI 0.115, pytest, JavaScript ES2022, Three.js r160 vendorizado, Vitest + jsdom, Playwright/Chromium, Ollama (apenas produção).

**Spec:** `docs/superpowers/specs/2026-10-21-bmo-frontend-testes-acoes.md`

## Global Constraints

- Diretório de trabalho de todos os comandos: `~/Documentos/Estudo/Feira-de-ciencias/bmollm`.
- Python do projeto: `.venv/bin/python` no Linux; `.venv\Scripts\python.exe` no Windows.
- Não adicionar bundler, framework de UI ou dependência de runtime no frontend.
- Testes devem rodar **sem** GPU, Ollama, Whisper, Kokoro, microfone real e internet.
- O protocolo atual (`transcricao`, `estado`, `emocao`, `audio_meta`, `frase`, `audio_fim`, `parar`, `erro`) não pode mudar de forma incompatível.
- Ações são uma lista fechada; o frontend nunca executa código vindo do modelo.
- `BMO_ACOES=0` por padrão; o schema/prompt só pede ações quando o modelo novo estiver pronto.
- Textos visíveis ao público em português do Brasil.
- Cada task termina com testes passando e um commit próprio.

## Review Focus

1. **JSON do modelo com ações malformadas, fora de ordem ou desconhecidas** — a fala deve continuar e nenhuma ação inválida pode ser executada. Testes: Task 4 (parser/validação) e Task 5 (dispatcher).
2. **Ação desconhecida ou com args inválidos vinda de um modelo futuro** — o frontend registra aviso, ignora e segue animando. Testes: Task 5 (unit) e Task 6 (E2E).
3. **Barge-in durante fala/animação** — no `pointerdown`, áudio e animação param na hora e a UI volta a `pronto`; nenhuma transformação fica presa. Testes: Task 7.
4. **Microfone negado, microfone ausente ou WebSocket fechado** — mensagem clara, botão não fica em `gravando`, estado não fica em `pensando`. Testes: Task 3 e Task 7.
5. **`bmo.glb` ausente ou WebGL indisponível** — o BMO procedural continua aparecendo e as ações não quebram. Testes: Task 1 (load) e Task 6.
6. **Resposta longa com muitas frases** — o áudio não sobrepõe, as fontes são limpas e a tela volta a `pronto`. Testes: Task 3 e Task 7.

---

### Task 1: Harness de testes do frontend + correção P0 do vendor

**Files:**
- Create: `package.json`
- Create: `vitest.config.js`
- Create: `playwright.config.js`
- Create: `frontend/tests/ws.test.js`
- Create: `frontend/tests_e2e/load.spec.js`
- Create: `frontend/vendor/utils/BufferGeometryUtils.js`
- Modify: `.gitignore`
- Modify: `README.md` (seção de comandos de teste)

**Interfaces:**
- Consumes: nada.
- Produces: `npm run test:unit`, `npm run test:e2e`, `npm test`; módulo `WSClient` importável em Node/jsdom; página inicial carregando com Canvas e WebSocket.

- [ ] **Step 1: Escrever o teste unitário do `WSClient`**

Crie `frontend/tests/ws.test.js`:

```js
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WSClient } from '../src/ws.js';

class FakeWebSocket {
  static OPEN = 1;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.sent = [];
    FakeWebSocket.instances.push(this);
  }

  send(data) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(); }
  open() { this.readyState = 1; this.onopen?.(); }
  message(data) { this.onmessage?.({ data }); }
}

describe('WSClient', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('conecta em /ws e entrega JSON e binário', () => {
    const onJson = vi.fn();
    const onBinary = vi.fn();
    const client = new WSClient({ onJson, onBinary });
    client.connect();

    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toBe('ws://localhost:8000/ws');
    expect(socket.binaryType).toBe('arraybuffer');

    socket.message('{"type":"estado","estado":"pronto"}');
    expect(onJson).toHaveBeenCalledWith({ type: 'estado', estado: 'pronto' });

    const buffer = new ArrayBuffer(4);
    socket.message(buffer);
    expect(onBinary).toHaveBeenCalledWith(buffer);
  });

  it('só envia áudio quando o socket está aberto', () => {
    const client = new WSClient();
    client.connect();
    const socket = FakeWebSocket.instances[0];

    const buffer = new ArrayBuffer(2);
    client.sendAudio(buffer);
    expect(socket.sent).toEqual([]);

    socket.open();
    client.sendAudio(buffer);
    expect(socket.sent).toEqual([buffer]);
  });

  it('tenta reconectar 2 s depois de fechar', () => {
    vi.useFakeTimers();
    const client = new WSClient();
    client.connect();
    FakeWebSocket.instances[0].close();

    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(2000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha por falta de infraestrutura**

Run: `npm run test:unit`  
Expected: FAIL — `npm ERR! Missing script: "test:unit"` (ou `package.json` inexistente).

- [ ] **Step 3: Criar `package.json`, `vitest.config.js` e `playwright.config.js`**

`package.json` (sem versões fixas; elas entram no `npm install`):

```json
{
  "name": "bmollm-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "test:unit": "vitest run",
    "test:e2e": "playwright test",
    "test": "npm run test:unit && npm run test:e2e"
  }
}
```

`vitest.config.js`:

```js
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    environmentOptions: { jsdom: { url: 'http://localhost:8000/' } },
    include: ['frontend/tests/**/*.test.js'],
  },
});
```

`playwright.config.js`:

```js
import { defineConfig, devices } from '@playwright/test';

const python = process.platform === 'win32'
  ? '.venv\\Scripts\\python.exe'
  : '.venv/bin/python';

export default defineConfig({
  testDir: './frontend/tests_e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:8010',
    trace: 'on-first-retry',
    permissions: ['microphone'],
    launchOptions: {
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        '--autoplay-policy=no-user-gesture-required',
      ],
    },
  },
  webServer: {
    command: `${python} -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010`,
    url: 'http://127.0.0.1:8010/',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: { BMO_PRELOAD: '0', LOG_TO_FILE: '0', BMO_E2E: '1' },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
```

- [ ] **Step 4: Instalar as dependências de teste**

Run:

```bash
npm install --save-dev vitest jsdom @playwright/test
npx playwright install chromium
```

Expected: `node_modules/`, `package-lock.json` e o Chromium do Playwright instalados.

- [ ] **Step 5: Rodar o teste unitário e confirmar que passa**

Run: `npm run test:unit`  
Expected: PASS — 3 testes do `WSClient`.

- [ ] **Step 6: Escrever o teste E2E de carregamento**

Crie `frontend/tests_e2e/load.spec.js`:

```js
import { expect, test } from '@playwright/test';

test('carrega o BMO, cria o canvas e conecta no WebSocket', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveTitle('BMO-LLM');
  await expect(page.locator('#scene canvas')).toBeVisible();
  await expect(page.locator('#estado')).toContainText('pronto', { timeout: 10_000 });
});
```

- [ ] **Step 7: Rodar e confirmar a falha P0**

Run: `npm run test:e2e -- --project=chromium`  
Expected: FAIL — `#scene canvas` não existe e `#estado` fica em `conectando…`; no console, 404 de `/vendor/utils/BufferGeometryUtils.js`.

- [ ] **Step 8: Vendorizar `BufferGeometryUtils.js` da versão r160**

Run:

```bash
mkdir -p frontend/vendor/utils
curl -fsSL https://unpkg.com/three@0.160.0/examples/jsm/utils/BufferGeometryUtils.js \
  -o frontend/vendor/utils/BufferGeometryUtils.js
```

O arquivo deve ter ~1375 linhas e conter `import { BufferAttribute, BufferGeometry, ... } from 'three';`. O import existente em `frontend/vendor/three/GLTFLoader.js:68` (`../utils/BufferGeometryUtils.js`) passa a resolver para `/vendor/utils/BufferGeometryUtils.js`.

- [ ] **Step 9: Rodar o E2E e confirmar que passa**

Run: `npm run test:e2e -- --project=chromium`  
Expected: PASS — título, canvas visível e status `pronto — segure para falar`.

- [ ] **Step 10: Atualizar `.gitignore` e README**

Adicione ao `.gitignore`:

```gitignore
# Frontend tests
test-results/
playwright-report/
coverage/
```

No `README.md`, adicione uma seção curta:

````markdown
## Testes de frontend

```bash
npm install
npx playwright install chromium
npm run test:unit
npm run test:e2e
npm test
```
````

- [ ] **Step 11: Commit**

```bash
git add package.json package-lock.json vitest.config.js playwright.config.js \
  frontend/tests frontend/tests_e2e frontend/vendor/utils .gitignore README.md
git commit -m "test(frontend): adiciona harness e corrige vendor do GLTFLoader"
```

---

### Task 2: Modo ensaio determinístico no backend (`BMO_E2E=1`)

**Files:**
- Create: `backend/app/scripted.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Create: `tests/test_scripted.py`

**Interfaces:**
- Consumes: `FakeWebSocket` de `tests/fakes.py`.
- Produces: `ScriptedPipeline.process(ws, audio_bytes)`, `ScriptedPipeline.status()`, `ScriptedPipeline.warmup()`; a flag `settings.E2E`.

- [ ] **Step 1: Escrever os testes do pipeline roteirizado**

Crie `tests/test_scripted.py`:

```python
import asyncio

from fakes import FakeWebSocket
from backend.app.scripted import ScriptedPipeline


def run(token: bytes) -> FakeWebSocket:
    ws = FakeWebSocket()
    asyncio.run(ScriptedPipeline().process(ws, token))
    return ws


def test_cenario_ok_segue_o_protocolo_atual():
    ws = run(b"ok")

    assert ws.tipos[0] == "transcricao"
    assert ws.jsons[0]["texto"] == "oi bmo"
    assert {"type": "estado", "estado": "pensando"} in ws.jsons
    assert ws.tipos.count("audio_meta") == 1
    assert ws.tipos.index("audio_meta") < ws.tipos.index("frase")
    assert ws.tipos[-1] == "estado"
    assert ws.jsons[-1]["estado"] == "pronto"
    assert ws.bytes


def test_cenario_erro_avisa_e_libera_a_tela():
    ws = run(b"erro")

    assert ws.tipos[0] == "erro"
    assert "teste de erro" in ws.texto_de("erro")[0]
    assert ws.jsons[-1]["estado"] == "pronto"


def test_cenario_longo_tem_varias_frases():
    ws = run(b"longo")

    assert len(ws.texto_de("frase")) >= 3
    assert ws.jsons[-1]["estado"] == "pronto"


def test_token_desconhecido_cai_no_cenario_padrao():
    ws = run(b"qualquer-coisa")

    assert ws.jsons[0]["texto"] == "oi bmo"
    assert ws.jsons[-1]["estado"] == "pronto"


def test_status_do_modo_ensaio_e_sempre_ok():
    status = ScriptedPipeline().status()

    assert set(status) == {"stt", "llm", "tts"}
    assert all(item["estado"] == "ok" for item in status.values())
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_scripted.py -q`  
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.scripted'`.

- [ ] **Step 3: Implementar `ScriptedPipeline`**

Crie `backend/app/scripted.py` com esta interface e comportamento:

```python
import asyncio

# Tokens que o cliente E2E manda como bytes UTF-8 no lugar do áudio.
CENARIOS = {
    b"ok": {
        "transcricao": "oi bmo",
        "emocao": "feliz",
        "frases": ["Oi! Eu sou o BMO."],
    },
    b"erro": {"erro": "teste de erro"},
    b"vazio": {"transcricao": "", "frases": ["Não ouvi nada. Segura o botão e fala pertinho?"]},
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
}
```

Implemente `process` assim:

1. Decodifique o token com `audio_bytes.decode("utf-8", errors="ignore").strip()` e use `CENARIOS.get(token.encode(), CENARIOS[b"ok"])`.
2. Se o cenário tem `"erro"`, envie `{"type":"erro","mensagem":...}` e `{"type":"estado","estado":"pronto"}`; retorne.
3. Envie `transcricao`, depois `estado pensando`.
4. Se houver `emocao`, envie `{"type":"emocao","emocao":...}`.
5. Envie `audio_meta` uma vez: `{"type":"audio_meta","rate":24000,"channels":1,"fmt":"int16"}`.
6. Para cada frase: `await asyncio.sleep(0.03)`, envie `{"type":"frase","texto":frase}`, depois `await ws.send_bytes(b"\x00\x00" * 2400)` (0,1 s de silêncio PCM).
7. Envie `{"type":"audio_fim"}` e, no `finally`, `{"type":"estado","estado":"pronto"}`.
8. `status()` devolve `{"stt":{"estado":"ok"},"llm":{"estado":"ok"},"tts":{"estado":"ok"}}`.
9. `async def warmup(self): return None`.

- [ ] **Step 4: Ligar a flag no `config.py` e no `main.py`**

Em `backend/app/config.py`, adicione:

```python
E2E = _flag("BMO_E2E", "0")
```

Em `backend/app/main.py`, importe e selecione o pipeline:

```python
from .scripted import ScriptedPipeline

pipeline = ScriptedPipeline() if settings.E2E else BmoPipeline()
```

- [ ] **Step 5: Rodar os testes do backend**

Run: `.venv/bin/python -m pytest tests/test_scripted.py -q`  
Expected: PASS — 5 testes.

Run: `.venv/bin/python -m pytest tests -q`  
Expected: PASS — 29 testes (24 antigos + 5 novos).

- [ ] **Step 6: Commit**

```bash
git add backend/app/scripted.py backend/app/config.py backend/app/main.py tests/test_scripted.py
git commit -m "test(backend): adiciona modo ensaio deterministico BMO_E2E"
```

---

### Task 3: Test hooks e E2E do fluxo atual

**Files:**
- Modify: `frontend/src/main.js`
- Create: `frontend/tests_e2e/flow.spec.js`

**Interfaces:**
- Consumes: `ScriptedPipeline` (Task 2), `WSClient`, `UI`, `AudioManager`, `Bmo`.
- Produces: `window.__bmoTest` somente quando a URL tem `?e2e=1`; métodos `send(token)`, `closeSocket()`, além de `bmo`, `ui`, `audio`, `ws`, `lastJson`, `actions`.

- [ ] **Step 1: Expor o hook de teste no `main.js`**

Depois da criação de `const ws = new WSClient({...})` e antes de `ws.connect()`, adicione:

```js
const e2e = new URLSearchParams(location.search).has('e2e');
if (e2e) {
  window.__bmoTest = {
    bmo,
    ui,
    audio,
    ws,
    lastJson: null,
    actions: [],
    send(token) { ws.sendAudio(new TextEncoder().encode(token)); },
    closeSocket() { ws.ws?.close(); },
  };
}
```

No início de `handleJson(msg)`, adicione:

```js
if (window.__bmoTest) window.__bmoTest.lastJson = msg;
```

- [ ] **Step 2: Escrever os E2E do fluxo**

Crie `frontend/tests_e2e/flow.spec.js`:

```js
import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
});

test('resposta ok atualiza transcrição, emoção, frase e volta a pronto', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('ok'));

  await expect(page.locator('#transcricao')).toHaveText('ouvi: oi bmo');
  await expect(page.locator('#emocao')).toHaveText('feliz');
  await expect(page.locator('#frase')).toHaveText('Oi! Eu sou o BMO.');
  await expect(page.locator('#estado')).toHaveText('pronto');
});

test('erro do servidor aparece e libera a tela', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('erro'));

  await expect(page.locator('#erro')).toContainText('teste de erro');
  await expect(page.locator('#estado')).toHaveText('pronto');
});

test('resposta longa não deixa a tela presa', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('longo'));

  await expect(page.locator('#frase')).toContainText('robô pequeno');
  await expect(page.locator('#estado')).toHaveText('pronto', { timeout: 15_000 });
});

test('botão com microfone falso envia áudio e recebe resposta', async ({ page }) => {
  const btn = page.locator('#btn');
  await btn.dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'mouse' });
  await expect(btn).toHaveClass(/recording/);
  await page.waitForTimeout(800);
  await btn.dispatchEvent('pointerup', { pointerId: 1, pointerType: 'mouse' });

  await expect(page.locator('#transcricao')).toContainText('ouvi: oi bmo', { timeout: 10_000 });
});

test('reconecta sozinho depois de fechar o socket', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.closeSocket());

  await expect(page.locator('#estado')).toHaveText('desconectado');
  await expect(page.locator('#estado')).toContainText('pronto', { timeout: 5_000 });
});

test('microfone negado mostra mensagem e não fica gravando', async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () => Promise.reject(
      Object.assign(new Error('denied'), { name: 'NotAllowedError' }),
    );
  });
  await page.goto('/?e2e=1');

  await page.locator('#btn').dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'mouse' });

  await expect(page.locator('#erro')).toContainText('Microfone bloqueado');
  await expect(page.locator('#btn')).not.toHaveClass(/recording/);
});
```

- [ ] **Step 3: Rodar os E2E e corrigir o que aparecer**

Run: `npm run test:e2e -- --project=chromium`  
Expected: PASS — 1 load + 6 flow. Se o cenário `vazio` ainda não for usado, ele fica coberto pelos testes de backend.

- [ ] **Step 4: Rodar tudo junto**

Run: `npm run test:unit`  
Expected: PASS — 3 testes.

Run: `.venv/bin/python -m pytest tests -q`  
Expected: PASS — 29 testes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/main.js frontend/tests_e2e/flow.spec.js
git commit -m "test(frontend): cobre fluxo de fala, erro e reconexao no navegador"
```

---

### Task 4: Contrato, parser e validação de ações no backend

**Files:**
- Create: `backend/app/actions.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/llm.py`
- Modify: `backend/app/pipeline.py`
- Create: `tests/test_actions.py`
- Create: `tests/fixtures/model_output_examples.json`

**Interfaces:**
- Consumes: `settings.EMOTIONS`, `settings.ACTIONS_ENABLED`.
- Produces:
  - `@dataclass(frozen=True) Acao(nome: str, args: dict)`
  - `normalizar_acoes(raw: object) -> list[Acao]`
  - `ActionStreamParser.feed(chunk: str) -> list[Acao]`
  - `acoes_schema() -> dict`
  - mensagens `{"type":"acao","nome":str,"args":dict}` no WebSocket.

- [ ] **Step 1: Escrever os testes de validação e parsing**

Crie `tests/test_actions.py`:

```python
import json
from pathlib import Path

from backend.app.actions import ActionStreamParser, normalizar_acoes


def parse(pedacos):
    parser = ActionStreamParser()
    saida = []
    for pedaco in pedacos:
        saida.extend(parser.feed(pedaco))
    return saida


def test_extrai_acao_antes_da_resposta():
    acoes = parse([
        '{"emocao":"feliz","acoes":[{"nome":"animacao",',
        '{"args":{"nome":"pular"}}],"resposta":"Oi!"}',
    ])

    assert [(a.nome, a.args) for a in acoes] == [("animacao", {"nome": "pular", "duracao": 1.5})]


def test_extrai_acao_depois_da_resposta():
    acoes = parse([
        '{"emocao":"neutro","resposta":"Oi!",',
        '"acoes":[{"nome":"som","args":{"tipo":"bip"}}]}',
    ])

    assert [a.nome for a in acoes] == ["som"]


def test_espera_array_fechar_antes_de_executar():
    parser = ActionStreamParser()
    assert parser.feed('{"acoes":[{"nome":"animacao",') == []
    assert parser.feed('"args":{"nome":"dancar"}}]') != []


def test_descarta_acao_desconhecida_e_args_invalidos():
    acoes = normalizar_acoes([
        {"nome": "hackear", "args": {}},
        {"nome": "animacao", "args": {"nome": "voar"}},
        {"nome": "led", "args": {"cor": "vermelho"}},
        {"nome": "som", "args": {"tipo": "bip"}},
    ])

    assert [a.nome for a in acoes] == ["som"]


def test_limita_a_oito_acoes():
    raw = [{"nome": "som", "args": {"tipo": "bip"}}] * 20

    assert len(normalizar_acoes(raw)) == 8


def test_json_quebrado_nao_derruba_a_fala():
    acoes = parse(['{"acoes":[{"nome":', '###}],"resposta":"Oi!"}'])

    assert acoes == []


def test_exemplos_de_modelo_viram_acoes():
    fixture = Path(__file__).parent / "fixtures" / "model_output_examples.json"
    exemplos = json.loads(fixture.read_text(encoding="utf-8"))

    for exemplo in exemplos:
        parser = ActionStreamParser()
        acoes = []
        for pedaco in exemplo["chunks"]:
            acoes.extend(parser.feed(pedaco))
        assert [a.nome for a in acoes] == exemplo["esperado"]
```

Crie `tests/fixtures/model_output_examples.json`:

```json
[
  {
    "nome": "sem_acoes",
    "chunks": ["{\"emocao\":\"neutro\",\"resposta\":\"Oi!\"}"],
    "esperado": []
  },
  {
    "nome": "acoes_antes",
    "chunks": ["{\"emocao\":\"feliz\",\"acoes\":[{\"nome\":\"animacao\",\"args\":{\"nome\":\"pular\"}}],\"resposta\":\"Oi!\"}"],
    "esperado": ["animacao"]
  },
  {
    "nome": "acoes_depois",
    "chunks": ["{\"emocao\":\"neutro\",\"resposta\":\"Oi!\",\"acoes\":[{\"nome\":\"som\",\"args\":{\"tipo\":\"bip\"}}]}"],
    "esperado": ["som"]
  }
]
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_actions.py -q`  
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.actions'`.

- [ ] **Step 3: Implementar `backend/app/actions.py`**

Constantes e validação:

```python
from dataclasses import dataclass
import json
import logging
import re
from typing import Any

from .config import settings

log = logging.getLogger(__name__)

ANIMACOES = {"pular", "dancar", "tremer", "acenar", "olhar_lado", "dormir"}
SONS = {"bip", "erro", "sucesso"}
MAX_ACOES = 8


@dataclass(frozen=True)
class Acao:
    nome: str
    args: dict[str, Any]
```

`normalizar_acoes(raw)` deve:
- retornar `[]` se `raw` não for lista;
- processar no máximo `MAX_ACOES`;
- para cada item, exigir `nome` string e `args` dict;
- `expressao`: `emocao` em `settings.EMOTIONS`;
- `animacao`: `nome` em `ANIMACOES`; `duracao` numérica entre 0.1 e 10 (padrão 1.5);
- `texto`: `texto` string não vazia até 200 chars; `duracao` entre 0.5 e 30 (padrão 4);
- `led`: `cor` casando `^#[0-9a-fA-F]{6}$`; `piscar` booleano (padrão `False`);
- `som`: `tipo` em `SONS`;
- descartar chaves extras de `args`;
- retornar apenas `Acao` válidas.

`ActionStreamParser` deve guardar o buffer, achar `"acoes"\s*:\s*\[` com regex e, quando o array fechar, decodificar com `json.loads` e chamar `normalizar_acoes`. Use este scanner para achar o fechamento (respeita strings e escapes):

```python
def _fim_do_array(texto: str, inicio: int) -> int | None:
    profundidade = 0
    dentro_de_string = False
    escapado = False
    for i in range(inicio, len(texto)):
        ch = texto[i]
        if dentro_de_string:
            if escapado:
                escapado = False
            elif ch == "\\":
                escapado = True
            elif ch == '"':
                dentro_de_string = False
            continue
        if ch == '"':
            dentro_de_string = True
        elif ch == "[":
            profundidade += 1
        elif ch == "]":
            profundidade -= 1
            if profundidade == 0:
                return i
    return None
```

Se o JSON estiver quebrado, logue `warning`, marque o parser como concluído e retorne `[]` (a fala continua).

`acoes_schema()` devolve o trecho de schema para o Ollama:

```python
def acoes_schema() -> dict:
    return {
        "type": "array",
        "maxItems": MAX_ACOES,
        "items": {
            "type": "object",
            "properties": {
                "nome": {"enum": ["expressao", "animacao", "texto", "led", "som"]},
                "args": {"type": "object"},
            },
            "required": ["nome", "args"],
        },
    }
```

- [ ] **Step 4: Adicionar a flag e o schema opcional**

Em `backend/app/config.py`:

```python
ACTIONS_ENABLED = _flag("BMO_ACOES", "0")
```

Em `backend/app/llm.py`, importe `acoes_schema` e use `settings.ACTIONS_ENABLED`. No `__init__`:

```python
if settings.ACTIONS_ENABLED:
    self.schema["properties"]["acoes"] = acoes_schema()
    self.system_prompt = (
        self.system_prompt
        + " Se fizer sentido, inclua 'acoes' antes de 'resposta': uma lista de "
          "objetos com 'nome' e 'args'. Ações permitidas: expressao, animacao, "
          "texto, led, som. Nunca invente nomes ou argumentos."
    )
```

Mantenha `"required": ["emocao", "resposta"]` para não quebrar modelos antigos.

- [ ] **Step 5: Enviar ações no pipeline**

Em `backend/app/pipeline.py`, importe `ActionStreamParser` e, em `_stream_answer`, crie `action_parser = ActionStreamParser()` junto de `parser`/`splitter`.

Depois de `parser.feed(chunk)` e antes de `parser.drain_text()`, adicione:

```python
for acao in action_parser.feed(chunk):
    await self._send_json(ws, {
        "type": "acao",
        "nome": acao.nome,
        "args": acao.args,
    })
```

- [ ] **Step 6: Rodar os testes**

Run: `.venv/bin/python -m pytest tests/test_actions.py -q`  
Expected: PASS — 7 testes.

Run: `.venv/bin/python -m pytest tests -q`  
Expected: PASS — 36 testes.

- [ ] **Step 7: Commit**

```bash
git add backend/app/actions.py backend/app/config.py backend/app/llm.py \
  backend/app/pipeline.py tests/test_actions.py tests/fixtures/model_output_examples.json
git commit -m "feat(backend): valida e encaminha acoes do modelo pelo WebSocket"
```

---

### Task 5: Dispatcher de ações no frontend

**Files:**
- Create: `frontend/src/actions.js`
- Modify: `frontend/src/main.js`
- Create: `frontend/tests/actions.test.js`

**Interfaces:**
- Consumes: `bmo.setEmotion(emocao)`, `bmo.playAnimation(nome, duracao)`, `bmo.setLed(cor, piscar)`, `ui.setEmocao(emocao)`, `ui.setFrase(texto)`, `audio.playBeep(tipo)`.
- Produces: `new ActionDispatcher({ bmo, ui, audio, log })`; `execute(acao) -> boolean`; `executeAll(acoes) -> number`.

- [ ] **Step 1: Escrever os testes do dispatcher**

Crie `frontend/tests/actions.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { ActionDispatcher } from '../src/actions.js';

function montar() {
  const bmo = {
    setEmotion: vi.fn(),
    playAnimation: vi.fn(),
    setLed: vi.fn(),
  };
  const ui = { setEmocao: vi.fn(), setFrase: vi.fn() };
  const audio = { playBeep: vi.fn() };
  const log = { warn: vi.fn() };
  return {
    bmo,
    ui,
    audio,
    log,
    dispatcher: new ActionDispatcher({ bmo, ui, audio, log }),
  };
}

describe('ActionDispatcher', () => {
  it('executa expressao, animacao, texto, led e som', () => {
    const { dispatcher, bmo, ui, audio } = montar();

    expect(dispatcher.execute({ nome: 'expressao', args: { emocao: 'feliz' } })).toBe(true);
    expect(bmo.setEmotion).toHaveBeenCalledWith('feliz');
    expect(ui.setEmocao).toHaveBeenCalledWith('feliz');

    expect(dispatcher.execute({ nome: 'animacao', args: { nome: 'pular', duracao: 1.2 } })).toBe(true);
    expect(bmo.playAnimation).toHaveBeenCalledWith('pular', 1.2);

    expect(dispatcher.execute({ nome: 'texto', args: { texto: 'Oi!' } })).toBe(true);
    expect(ui.setFrase).toHaveBeenCalledWith('Oi!');

    expect(dispatcher.execute({ nome: 'led', args: { cor: '#ff0000' } })).toBe(true);
    expect(bmo.setLed).toHaveBeenCalledWith('#ff0000', false);

    expect(dispatcher.execute({ nome: 'som', args: { tipo: 'bip' } })).toBe(true);
    expect(audio.playBeep).toHaveBeenCalledWith('bip');
  });

  it('ignora ação desconhecida e argumentos inválidos', () => {
    const { dispatcher, bmo, log } = montar();

    expect(dispatcher.execute({ nome: 'hackear', args: {} })).toBe(false);
    expect(dispatcher.execute({ nome: 'animacao', args: { nome: 'voar' } })).toBe(false);
    expect(bmo.playAnimation).not.toHaveBeenCalled();
    expect(log.warn).toHaveBeenCalled();
  });

  it('não para o lote quando um handler lança erro', () => {
    const { dispatcher, bmo, ui, log } = montar();
    bmo.playAnimation.mockImplementation(() => { throw new Error('boom'); });

    const executadas = dispatcher.executeAll([
      { nome: 'animacao', args: { nome: 'pular' } },
      { nome: 'texto', args: { texto: 'Oi!' } },
    ]);

    expect(executadas).toBe(1);
    expect(ui.setFrase).toHaveBeenCalledWith('Oi!');
    expect(log.warn).toHaveBeenCalled();
  });

  it('trata mensagem sem nome/args como inválida', () => {
    const { dispatcher } = montar();

    expect(dispatcher.execute({})).toBe(false);
    expect(dispatcher.execute({ nome: 'som' })).toBe(false);
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `npm run test:unit -- frontend/tests/actions.test.js`  
Expected: FAIL — `Failed to resolve import "../src/actions.js"`.

- [ ] **Step 3: Implementar `frontend/src/actions.js`**

Estrutura:

```js
const EMOTIONS = new Set(['neutro', 'feliz', 'triste', 'surpreso', 'curioso', 'bravo']);
const ANIMATIONS = new Set(['pular', 'dancar', 'tremer', 'acenar', 'olhar_lado', 'dormir']);
const SOUNDS = new Set(['bip', 'erro', 'sucesso']);
const HEX = /^#[0-9a-fA-F]{6}$/;

function numero(valor, padrao, min, max) {
  if (typeof valor !== 'number' || !Number.isFinite(valor)) return padrao;
  return Math.min(max, Math.max(min, valor));
}

export class ActionDispatcher {
  constructor({ bmo, ui, audio, log = console } = {}) {
    this.bmo = bmo;
    this.ui = ui;
    this.audio = audio;
    this.log = log;
    this.handlers = {
      expressao: (args) => {
        this.bmo.setEmotion(args.emocao);
        this.ui.setEmocao(args.emocao);
      },
      animacao: (args) => this.bmo.playAnimation(args.nome, args.duracao),
      texto: (args) => this.ui.setFrase(args.texto),
      led: (args) => this.bmo.setLed(args.cor, args.piscar),
      som: (args) => this.audio.playBeep(args.tipo),
    };
  }

  validar(acao) {
    if (!acao || typeof acao.nome !== 'string') return null;
    const args = acao.args && typeof acao.args === 'object' ? acao.args : null;
    if (!args) return null;
    switch (acao.nome) {
      case 'expressao':
        return EMOTIONS.has(args.emocao) ? { emocao: args.emocao } : null;
      case 'animacao':
        return ANIMATIONS.has(args.nome)
          ? { nome: args.nome, duracao: numero(args.duracao, 1.5, 0.1, 10) }
          : null;
      case 'texto': {
        if (typeof args.texto !== 'string') return null;
        const texto = args.texto.trim().slice(0, 200);
        return texto ? { texto } : null;
      }
      case 'led':
        return HEX.test(args.cor)
          ? { cor: args.cor, piscar: Boolean(args.piscar) }
          : null;
      case 'som':
        return SOUNDS.has(args.tipo) ? { tipo: args.tipo } : null;
      default:
        return null;
    }
  }

  execute(acao) {
    const args = this.validar(acao);
    if (!args) {
      this.log.warn('Ação ignorada:', acao);
      return false;
    }
    try {
      this.handlers[acao.nome](args);
      return true;
    } catch (err) {
      this.log.warn('Falha ao executar ação', acao.nome, err);
      return false;
    }
  }

  executeAll(acoes) {
    if (!Array.isArray(acoes)) return 0;
    return acoes.reduce((total, acao) => total + (this.execute(acao) ? 1 : 0), 0);
  }
}
```

- [ ] **Step 4: Ligar no `main.js`**

Importe:

```js
import { ActionDispatcher } from './actions.js';
```

Depois de criar `bmo`, `ui` e `audio`:

```js
const actions = new ActionDispatcher({ bmo, ui, audio });
```

No `switch` de `handleJson`:

```js
case 'acao':
  window.__bmoTest?.actions.push(msg);
  actions.execute(msg);
  break;
```

- [ ] **Step 5: Rodar os testes**

Run: `npm run test:unit`  
Expected: PASS — 3 testes de `WSClient` + 4 de `ActionDispatcher`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/actions.js frontend/src/main.js frontend/tests/actions.test.js
git commit -m "feat(frontend): adiciona dispatcher de acoes com allowlist"
```

---

### Task 6: Animações, LED e som no BMO + E2E de ações

**Files:**
- Modify: `frontend/src/bmo.js`
- Modify: `frontend/src/audio.js`
- Modify: `backend/app/scripted.py`
- Create: `frontend/tests_e2e/actions.spec.js`

**Interfaces:**
- Consumes: `ActionDispatcher` (Task 5), mensagens `{"type":"acao",...}`.
- Produces:
  - `bmo.playAnimation(nome: string, duracao = 1.5)`
  - `bmo.stopAnimation()`
  - `bmo.setLed(cor: string, piscar = false)`
  - `bmo.ledColor: string | null`
  - `audio.playBeep(tipo = 'bip')`
  - cenários roteirizados `acoes` e `acao_invalida`.

- [ ] **Step 1: Adicionar os cenários de ação ao modo ensaio**

Em `backend/app/scripted.py`, acrescente a `CENARIOS`:

```python
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
```

No `process`, depois de enviar a emoção, envie cada ação do cenário:

```python
for acao in cenario.get("acoes", []):
    await ws.send_json({"type": "acao", "nome": acao["nome"], "args": acao["args"]})
```

- [ ] **Step 2: Corrigir o ciclo de vida do BMO**

Em `frontend/src/bmo.js`:

1. No construtor, adicione `this._animation = null; this.ledColor = null; this._procedural = null; this._emotionSince = 0;`.
2. Em `_buildProcedural`, guarde os botões em `this.leds = [b1, b2, b3]` e crie um grupo `this._procedural` contendo corpo, tela, rosto e botões; adicione esse grupo ao `this.group`.
3. Em `_tryLoadGlb`, ao carregar, remova `this._procedural` inteiro (não só `this.body`) e zere `this.face`, `this.ctx`, `this.leds`.
4. Em `update`, só chame `_drawFace` se `this.face` existir (depois de um GLB carregado não há rosto procedural).
5. Implemente:

```js
playAnimation(nome, duracao = 1.5) {
  if (!['pular', 'dancar', 'tremer', 'acenar', 'olhar_lado', 'dormir'].includes(nome)) return false;
  this._animation = { nome, inicio: this._t, duracao: Math.max(0.1, duracao) };
  return true;
}

stopAnimation() {
  this._animation = null;
}

setLed(cor, piscar = false) {
  this.ledColor = cor;
  this._ledPiscar = piscar;
  if (!this.leds) return;
  for (const led of this.leds) {
    led.material.color.set(cor);
    led.material.emissive?.set(cor);
    led.material.emissiveIntensity = 0.6;
  }
}
```

6. Em `_applyBody(t)`, **sempre** comece com:

```js
const g = this.group;
g.position.set(0, 0, 0);
g.rotation.set(0, 0, 0);
g.scale.setScalar(1);
g.position.y = Math.sin(t * 2) * 0.04;
```

7. Remova o decaimento global de `surpreso`; use `const dtEmocao = t - this._emotionSince;` e `Math.exp(-dtEmocao * 0.5)`. Em `setEmotion`, atualize `this._emotionSince = this._t`.
8. Depois da lógica de estado/emoção, aplique a animação ativa por cima:

```js
if (this._animation) {
  const k = (t - this._animation.inicio) / this._animation.duracao;
  if (k >= 1) {
    this._animation = null;
  } else {
    this._aplicarAnimacao(this._animation.nome, t, k);
  }
}
```

`_aplicarAnimacao` deve implementar:

| Nome | Efeito |
|---|---|
| `pular` | `position.y += Math.abs(Math.sin(k * Math.PI * 3)) * 0.35` |
| `dancar` | `rotation.z = Math.sin(t * 8) * 0.12; position.y += Math.abs(Math.sin(t * 6)) * 0.1` |
| `tremer` | `position.x = Math.sin(t * 30) * 0.05; rotation.z = Math.sin(t * 30) * 0.03` |
| `acenar` | `rotation.z = Math.sin(t * 10) * 0.18` |
| `olhar_lado` | `rotation.y = Math.sin(t * 4) * 0.4` |
| `dormir` | `rotation.z = -0.08; position.y -= 0.05` |

9. LED piscando: em `_applyBody`, se `this._ledPiscar && this.leds`, alterne `emissiveIntensity` entre `0.2` e `1.0` com `Math.sin(t * 10)`.

- [ ] **Step 3: Adicionar som ao `AudioManager`**

Em `frontend/src/audio.js`, implemente:

```js
playBeep(tipo = 'bip') {
  try {
    const ctx = this._ensureCtx();
    const freq = { bip: 880, erro: 220, sucesso: 1320 }[tipo] || 880;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.value = freq;
    gain.gain.value = 0.05;
    osc.connect(gain);
    gain.connect(ctx.destination);
    const now = ctx.currentTime;
    osc.start(now);
    osc.stop(now + 0.12);
  } catch (err) {
    console.warn('Não consegui tocar o som:', err);
  }
}
```

- [ ] **Step 4: Escrever o E2E de ações**

Crie `frontend/tests_e2e/actions.spec.js`:

```js
import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
});

test('executa as cinco ações e mantém a fala', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('acoes'));

  await expect(page.locator('#frase')).toHaveText('Olha eu pulando!');
  await expect(page.locator('#emocao')).toHaveText('feliz');

  const estado = await page.evaluate(() => ({
    led: window.__bmoTest.bmo.ledColor,
    animation: window.__bmoTest.bmo._animation?.nome ?? null,
    acoes: window.__bmoTest.actions.map((a) => a.nome),
  }));

  expect(estado.led).toBe('#ff0000');
  expect(estado.animation).toBe('pular');
  expect(estado.acoes).toEqual(['expressao', 'animacao', 'texto', 'led', 'som']);
});

test('ação desconhecida não quebra a resposta', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('acao_invalida'));

  await expect(page.locator('#frase')).toHaveText('Continuo aqui!');
  await expect(page.locator('#erro')).toHaveText('');
  const animation = await page.evaluate(() => window.__bmoTest.bmo._animation);
  expect(animation).toBeNull();
});

test('bravo não deixa o corpo deslocado depois de voltar ao neutro', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.bmo.setEmotion('bravo'));
  await page.waitForTimeout(300);
  await page.evaluate(() => window.__bmoTest.bmo.setEmotion('neutro'));
  await page.waitForTimeout(200);

  const x = await page.evaluate(() => window.__bmoTest.bmo.group.position.x);
  expect(Math.abs(x)).toBeLessThan(0.001);
});

test('animação termina e limpa o estado', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.bmo.playAnimation('pular', 1.0));
  await page.waitForTimeout(150);
  const y = await page.evaluate(() => window.__bmoTest.bmo.group.position.y);
  expect(y).toBeGreaterThan(0.05);

  await page.waitForTimeout(1100);
  const animation = await page.evaluate(() => window.__bmoTest.bmo._animation);
  expect(animation).toBeNull();
});
```

- [ ] **Step 5: Rodar os testes**

Run: `npm run test:unit`  
Expected: PASS — 7 testes.

Run: `npm run test:e2e -- --project=chromium`  
Expected: PASS — 1 load + 6 flow + 4 actions.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/bmo.js frontend/src/audio.js backend/app/scripted.py \
  frontend/tests_e2e/actions.spec.js
git commit -m "feat(frontend): executa animacoes, LED e som das acoes"
```

---

### Task 7: Barge-in imediato e robustez de áudio/WebSocket

**Files:**
- Modify: `backend/app/main.py`
- Modify: `frontend/src/ws.js`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/audio.js`
- Modify: `tests/test_ws.py`
- Modify: `frontend/tests/ws.test.js`
- Create: `frontend/tests/audio.test.js`
- Modify: `frontend/tests_e2e/flow.spec.js`

**Interfaces:**
- Consumes: `{"type":"interromper"}`; `AudioManager.stop()`; `Bmo.stopAnimation()`.
- Produces: `WSClient.interrupt()`, `WSClient.isOpen()`, `WSClient.sendAudio()` retornando `boolean`; cancelamento imediato no backend.

- [ ] **Step 1: Escrever o teste do backend para `interromper`**

Adicione `import asyncio` e `import time` no topo de `tests/test_ws.py` e, no fim do arquivo, este teste:

```python
def test_interromper_cancela_resposta_em_andamento(monkeypatch):
    class PipelineLongo:
        def __init__(self):
            self.cancelado = False

        async def process(self, ws, audio_bytes):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                self.cancelado = True
                raise

    fake = PipelineLongo()
    monkeypatch.setattr(main, "pipeline", fake)

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"audio")
            time.sleep(0.1)
            ws.send_json({"type": "interromper"})
            assert ws.receive_json() == {"type": "parar"}

    assert fake.cancelado is True
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_ws.py::test_interromper_cancela_resposta_em_andamento -q`  
Expected: FAIL — o servidor ignora texto e o teste trava/estoura timeout.

- [ ] **Step 3: Implementar o cancelamento no backend**

Em `backend/app/main.py`, extraia:

```python
async def _cancelar(task, ws):
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Falha ao encerrar a resposta anterior")
        try:
            await ws.send_json({"type": "parar"})
        except Exception:
            pass
```

No loop do WebSocket:

```python
if message.get("bytes"):
    await _cancelar(task, ws)
    task = asyncio.create_task(pipeline.process(ws, message["bytes"]))
elif message.get("text"):
    try:
        payload = json.loads(message["text"])
    except json.JSONDecodeError:
        continue
    if payload.get("type") == "interromper":
        await _cancelar(task, ws)
        task = None
```

Importe `json` no topo.

- [ ] **Step 4: Implementar no `WSClient`**

Em `frontend/src/ws.js`:

```js
isOpen() {
  return Boolean(this.ws && this.ws.readyState === WebSocket.OPEN);
}

sendAudio(buf) {
  if (!this.isOpen()) return false;
  this.ws.send(buf);
  return true;
}

interrupt() {
  if (!this.isOpen()) return false;
  this.ws.send(JSON.stringify({ type: 'interromper' }));
  return true;
}
```

- [ ] **Step 5: Parar áudio/animação no `pointerdown`**

Em `frontend/src/main.js`:

```js
ui.onTalkStart = () => {
  audio.stop();
  bmo.stopAnimation();
  ws.interrupt();
  audio.startRecording();
};
```

No `ui.onTalkEnd`, trate o retorno de `sendAudio`:

```js
const enviado = buf ? ws.sendAudio(buf) : false;
if (!enviado) {
  ui.setErro('Sem conexão com o servidor. Tentando reconectar…');
  ui.setEstado('desconectado');
}
```

- [ ] **Step 6: Limpar fontes de áudio**

Em `frontend/src/audio.js`, dentro de `playChunk`, depois de `this._sources.push(src)`:

```js
src.onended = () => {
  this._sources = this._sources.filter((s) => s !== src);
};
```

- [ ] **Step 7: Testes unitários de áudio e WS**

Crie `frontend/tests/audio.test.js` com um `AudioContext` falso (`createAnalyser`, `createBuffer`, `createBufferSource`, `createOscillator`, `createGain`, `destination`, `currentTime`) e cubra:

- `playChunk` agenda o primeiro chunk em `0` e o segundo em `duração do primeiro`;
- `stop()` para todas as fontes, limpa `_sources` e zera `_nextTime`;
- `onended` remove a fonte da lista;
- `playBeep('bip')` cria e inicia um oscillator.

Adicione em `frontend/tests/ws.test.js`:

```js
it('interrupt envia JSON e sendAudio devolve boolean', () => {
  const client = new WSClient();
  client.connect();
  const socket = FakeWebSocket.instances[0];

  expect(client.sendAudio(new ArrayBuffer(2))).toBe(false);
  expect(client.interrupt()).toBe(false);

  socket.open();
  expect(client.sendAudio(new ArrayBuffer(2))).toBe(true);
  expect(client.interrupt()).toBe(true);
  expect(socket.sent.at(-1)).toBe('{"type":"interromper"}');
});
```

- [ ] **Step 8: E2E de barge-in**

Adicione em `frontend/tests_e2e/flow.spec.js`:

```js
test('pointerdown durante a fala para áudio e animação na hora', async ({ page }) => {
  await page.evaluate(() => {
    window.__bmoTest.bmo.playAnimation('dancar', 10);
    window.__bmoTest.audio.playChunk(new Int16Array(24000).buffer);
  });

  await page.locator('#btn').dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'mouse' });

  const depois = await page.evaluate(() => ({
    fontes: window.__bmoTest.audio._sources.length,
    animacao: window.__bmoTest.bmo._animation,
  }));
  expect(depois.fontes).toBe(0);
  expect(depois.animacao).toBeNull();
});
```

- [ ] **Step 9: Rodar tudo**

Run: `.venv/bin/python -m pytest tests -q`  
Expected: PASS — 37 testes.

Run: `npm run test:unit`  
Expected: PASS — 7+ testes.

Run: `npm run test:e2e -- --project=chromium`  
Expected: PASS — 12+ testes.

- [ ] **Step 10: Commit**

```bash
git add backend/app/main.py frontend/src/ws.js frontend/src/main.js frontend/src/audio.js \
  tests/test_ws.py frontend/tests/ws.test.js frontend/tests/audio.test.js \
  frontend/tests_e2e/flow.spec.js
git commit -m "fix: interrompe audio e animacao no pointerdown"
```

---

### Task 8: Painel de ensaio manual e documentação do ponto de extensão

**Files:**
- Create: `frontend/src/debug.js`
- Modify: `frontend/src/main.js`
- Create: `frontend/tests_e2e/debug.spec.js`
- Modify: `README.md`
- Modify: `../.env.example` (raiz do repositório)

**Interfaces:**
- Consumes: `ActionDispatcher.execute`, `Bmo`, `UI`, `AudioManager`, `WSClient`.
- Produces: painel visível em `/?debug=1`; botões para cada ação; log das últimas mensagens; documentação de `BMO_ACOES` e do adaptador do modelo.

- [ ] **Step 1: Criar o painel de depuração**

Crie `frontend/src/debug.js`:

```js
export function montarDebug({ actions, bmo, ui, audio, ws }) {
  const painel = document.createElement('div');
  painel.id = 'debug';
  painel.innerHTML = `
    <strong>Ensaio de ações</strong>
    <div id="debug-botoes"></div>
    <pre id="debug-log"></pre>
  `;
  Object.assign(painel.style, {
    position: 'fixed', right: '12px', bottom: '12px', width: '260px',
    maxHeight: '45vh', overflow: 'auto', padding: '10px',
    background: 'rgba(8,16,28,.92)', border: '1px solid #7ee0a8',
    borderRadius: '10px', color: '#cfe', font: '12px/1.4 system-ui',
    pointerEvents: 'auto', zIndex: '10',
  });

  const botoes = [
    ['Pular', { nome: 'animacao', args: { nome: 'pular', duracao: 1.2 } }],
    ['Dançar', { nome: 'animacao', args: { nome: 'dancar', duracao: 2 } }],
    ['Tremer', { nome: 'animacao', args: { nome: 'tremer', duracao: 0.8 } }],
    ['Acenar', { nome: 'animacao', args: { nome: 'acenar', duracao: 1 } }],
    ['Olhar lado', { nome: 'animacao', args: { nome: 'olhar_lado', duracao: 1.5 } }],
    ['Dormir', { nome: 'animacao', args: { nome: 'dormir', duracao: 2 } }],
    ['LED verde', { nome: 'led', args: { cor: '#7ee0a8', piscar: false } }],
    ['LED piscando', { nome: 'led', args: { cor: '#ff0000', piscar: true } }],
    ['Bip', { nome: 'som', args: { tipo: 'bip' } }],
    ['Texto', { nome: 'texto', args: { texto: 'Teste de ação!' } }],
    ['Erro', { nome: 'expressao', args: { emocao: 'bravo' } }],
  ];

  const container = painel.querySelector('#debug-botoes');
  for (const [rotulo, acao] of botoes) {
    const btn = document.createElement('button');
    btn.textContent = rotulo;
    btn.style.cssText = 'margin:2px;padding:4px 8px;cursor:pointer';
    btn.addEventListener('click', () => {
      const ok = actions.execute(acao);
      log(`${rotulo}: ${ok ? 'ok' : 'ignorada'}`);
    });
    container.appendChild(btn);
  }

  function log(texto) {
    const pre = painel.querySelector('#debug-log');
    pre.textContent = `${new Date().toLocaleTimeString()} ${texto}\n${pre.textContent}`;
  }

  const original = ws.onJson;
  ws.onJson = (msg) => {
    log(msg.type);
    original(msg);
  };

  document.body.appendChild(painel);
  return { log };
}
```

- [ ] **Step 2: Montar o painel só com `?debug=1`**

Em `frontend/src/main.js`, importe:

```js
import { montarDebug } from './debug.js';
```

Depois do hook E2E e antes de `ws.connect()`:

```js
if (new URLSearchParams(location.search).has('debug')) {
  montarDebug({ actions, bmo, ui, audio, ws });
}
```

- [ ] **Step 3: E2E do painel**

Crie `frontend/tests_e2e/debug.spec.js`:

```js
import { expect, test } from '@playwright/test';

test('painel de ensaio dispara ações sem modelo', async ({ page }) => {
  await page.goto('/?debug=1&e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');

  await page.getByRole('button', { name: 'Pular' }).click();

  const animacao = await page.evaluate(() => window.__bmoTest.bmo._animation?.nome);
  expect(animacao).toBe('pular');
  await expect(page.locator('#debug-log')).toContainText('Pular: ok');
});
```

- [ ] **Step 4: Documentar no README**

Adicione:

````markdown
## Testes de frontend

```bash
npm install
npx playwright install chromium
npm run test:unit
npm run test:e2e
npm test
```

O modo ensaio usa um pipeline roteirizado, sem Whisper/Kokoro/Ollama:

```bash
BMO_E2E=1 .venv/bin/python -m uvicorn backend.app.main:app --port 8010
```

Abra `http://127.0.0.1:8010/?e2e=1` para os testes automatizados ou
`http://127.0.0.1:8010/?debug=1` para disparar ações manualmente.

## Ações do modelo

O modelo pode devolver `acoes` (opcional) antes de `resposta`:

```json
{"emocao":"feliz","acoes":[{"nome":"animacao","args":{"nome":"pular"}}],"resposta":"Oi!"}
```

Ações permitidas: `expressao`, `animacao`, `texto`, `led`, `som`.
O backend valida e envia `{"type":"acao","nome":...,"args":...}`; o frontend
executa por allowlist e ignora qualquer nome/args desconhecido.

`BMO_ACOES=0` mantém o comportamento atual. Quando o modelo novo chegar, mude
para `BMO_ACOES=1` e ajuste apenas `backend/app/llm.py` (schema/prompt/transporte)
e `backend/app/actions.py` (mapeamento do vocabulário do modelo).
````

- [ ] **Step 5: Atualizar o `.env.example` da raiz**

Adicione:

```dotenv
# 0 = não pede ações ao modelo (comportamento atual)
# 1 = inclui 'acoes' no schema/prompt quando o modelo novo estiver pronto
BMO_ACOES=0
```

- [ ] **Step 6: Rodar a verificação final**

Run:

```bash
.venv/bin/python -m pytest tests -q
npm run test:unit
npm run test:e2e -- --project=chromium
```

Expected:
- pytest: PASS — 37 testes;
- Vitest: PASS — 7+ testes;
- Playwright: PASS — 13+ testes.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/debug.js frontend/src/main.js frontend/tests_e2e/debug.spec.js \
  README.md ../.env.example
git commit -m "docs: painel de ensaio e ponto de extensao do modelo"
```

---

## Verificação manual antes da feira

- [ ] Abrir `/?debug=1` e disparar cada botão; conferir rosto, corpo, LED e som.
- [ ] Segurar o botão e falar; conferir transcrição, emoção, legenda e voz.
- [ ] Começar a falar enquanto o BMO fala; conferir que ele para na hora.
- [ ] Abrir `/health` e confirmar `pronto: true`.
- [ ] Fechar o servidor e reabrir; conferir reconexão automática em 2 s.
- [ ] Testar sem `bmo.glb`; o BMO procedural deve aparecer.
- [ ] Testar em janela de 1280×720 e em viewport mobile (390×844).

## Fora deste plano

- Implementar o adaptador do modelo novo antes de receber a especificação dele.
- Ativar `BMO_ACOES=1` em produção sem o modelo validado.
- Refatorar `test.html` para compartilhar os módulos do frontend.
- Substituir Three.js ou adicionar bundler.
