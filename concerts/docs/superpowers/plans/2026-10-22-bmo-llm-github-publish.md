# BMO-LLM — Publicação no GitHub (repositório separado) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar o projeto BMO-LLM em um repositório GitHub próprio, com instruções claras para as melhorias já aplicadas e para as diferenças procedurais entre as duas máquinas (PC de desenvolvimento e PC da feira).

**Architecture:** Um único repositório `bmo-llm` contendo backend (FastAPI), frontend (Three.js/Vite-vendor), testes e documentação. A stack é idêntica nas duas máquinas (Python 3.12, Ollama, faster-whisper, Kokoro, espeak-ng, Node para testes). O que muda entre máquinas são apenas etapas procedurais: valores de `.env`, criação do `.venv`, disponibilidade de GPU (LLM roda em CPU aqui, em RTX 2050 na feira), e caminhos de execução (run.sh vs run.bat). O código-fonte é o mesmo; as diferenças vivem em configuração e ambiente, nunca em lógica.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, httpx, faster-whisper, Kokoro, soundfile, numpy, Ollama (qwen3:4b), Three.js (vendored), pytest, vitest/playwright (dev).

**Spec:** N/A — este plano implementa a publicação e a documentação das melhorias já feitas (STT base, keep_alive 24h, preload paralelo, warmup real, reuse de cliente HTTP).

## Global Constraints

- **Nunca commitar segredos:** `.env` fica fora do git; apenas `.env.example` é versionado.
- **Nunca commitar dependências geradas:** `.venv/`, `node_modules/`, caches, logs, `__pycache__`, `*.wav/webm/mp3/ogg`, `test-results/`.
- **Stack fixa:** Python 3.10–3.12; Ollama com modelo `qwen3:4b`; Whisper `base` por padrão (medium como fallback); Kokoro voz `pf_dora`, lang `p`.
- **Melhorias já aplicadas (devem estar documentadas):** `WHISPER_MODEL=base`, `OLLAMA_KEEP_ALIVE=24h`, `BMO_PRELOAD=1`, preload paralelo STT+TTS, warmup real de STT/TTS/LLM, reuse de cliente HTTP no LLM, run.sh para Linux.
- **Mesma stack, etapas procedurais diferentes:** código idêntico; `.env`, `.venv`, execução e cache de modelos variam por máquina.

## Review Focus

- Um `.env` real com segredos pode vazar se o `.gitignore` estiver incompleto.
- Symlinks `.venv`/`node_modules` (usados neste PC) não devem ser commitados como links quebrados na outra máquina.
- A documentação de "melhorias" pode ficar desatualizada se não for ligada a commits específicos.
- O README atual menciona Windows (`C:\Users\...`); precisa cobrir Linux também.
- A branch `main` do repo original está desatualizada em relação à worktree com as melhorias; a publicação deve partir da versão mais recente.

---

### Task 1: Matriz de diferenças entre máquinas

**Files:**
- Create: `docs/MAQUINAS.md`

**Interfaces:**
- Consumes: configurações atuais de `.env` e `.env.example`.
- Produces: tabela de referência usada pelas Tasks 2, 3 e 4.

- [ ] **Step 1: Criar `docs/MAQUINAS.md` com a matriz de diferenças**

Conteúdo obrigatório (tabela):

| Item | PC de desenvolvimento (este) | PC da feira |
|------|------------------------------|-------------|
| SO | CachyOS (Niri) / Linux | Windows |
| Python | 3.12 (via uv) | 3.12 (instalador oficial) |
| Execução | `./run.sh` | `run.bat` |
| `.venv` | symlink para o venv do projeto original | venv real criado com `python -m venv .venv` |
| `node_modules` | symlink (testes frontend) | `npm install` (se rodar testes) |
| GPU/LLM | CPU (~4 tokens/s) | RTX 2050 (~30 tokens/s) |
| Whisper | CPU int8, modelo `base` | CPU int8, modelo `base` |
| Kokoro | CPU, espeak-ng | CPU, espeak-ng (MSI) |
| Cache de modelos | `~/.cache/huggingface`, `~/.ollama` | `%USERPROFILE%\.cache\huggingface`, `%USERPROFILE%\.ollama` |
| `.env` | valores de dev (OLLAMA_URL localhost) | valores da feira (idem, localhost) |

Adicionar seção "O que é idêntico" (código, stack, testes) e "O que muda" (apenas procedimento).

- [ ] **Step 2: Commit**

```bash
git add docs/MAQUINAS.md
git commit -m "docs: matriz de diferencas entre PC de dev e PC da feira"
```

---

### Task 2: Normalizar o projeto para publicação

**Files:**
- Modify: `.gitignore`
- Create: `.env.example` (já existe — verificar completude)
- Modify: `README.md`

**Interfaces:**
- Consumes: `.gitignore` atual, `.env.example` atual.
- Produces: repositório limpo e reproduzível em qualquer máquina.

- [ ] **Step 1: Revisar e completar `.gitignore`**

Garantir que contém (adicionar faltantes):

```
# Python
__pycache__/
*.py[cod]
*.so
.venv/
venv/
.env

# Model caches
models/
cache/
*.wav
*.webm
*.mp3
*.ogg

# Frontend build
node_modules/
dist/

# Logs
logs/
install.log
_tts_seg_*.wav

# Test artifacts
.pytest_cache/
test-results/
.coverage

# OS / editor
.DS_Store
.vscode/
.idea/
```

- [ ] **Step 2: Garantir que `.env.example` está completo e sem segredos**

Verificar que contém todas as chaves de `config.py` (OLLAMA_*, WHISPER_*, KOKORO_*, EMOTIONS, LOG_*, BMO_PRELOAD, BMO_E2E, BMO_ACOES) com valores padrão seguros. Confirmar que `.env` real não será commitado.

- [ ] **Step 3: Atualizar `README.md`**

Seções obrigatórias:
1. Descrição do BMO-LLM (assistente de voz offline).
2. Requisitos (Python 3.10–3.12, Ollama, espeak-ng, GPU opcional).
3. Setup no Linux (usar `run.sh`).
4. Setup no Windows (usar `run.bat`).
5. Configuração (copiar `.env.example` → `.env`).
6. Melhorias aplicadas (link para `docs/MELHORIAS.md`).
7. Diferenças entre máquinas (link para `docs/MAQUINAS.md`).
8. Testes (`pytest`, `npm test`).

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.example README.md
git commit -m "chore: normalizar projeto para publicacao (gitignore, env, readme)"
```

---

### Task 3: Documentar as melhorias aplicadas

**Files:**
- Create: `docs/MELHORIAS.md`

**Interfaces:**
- Consumes: mudanças feitas em `config.py`, `pipeline.py`, `llm.py`, `main.py`, `.env`.
- Produces: referência única das melhorias, usada no README e na feira.

- [ ] **Step 1: Criar `docs/MELHORIAS.md`**

Conteúdo obrigatório (uma seção por melhoria, com "o que mudou", "por quê", "onde"):

1. **STT mais rápido:** `WHISPER_MODEL` de `medium` → `base` (transcrição 6,33s → 0,65s, ~10×). Fallback `medium` para ambientes ruidosos.
2. **Ollama não descarrega:** `OLLAMA_KEEP_ALIVE=24h` (era 30m).
3. **Pré-carregamento:** `BMO_PRELOAD=1` (padrão) carrega Whisper/Kokoro ao subir.
4. **Preload paralelo:** STT e TTS carregam em paralelo (`ThreadPoolExecutor`).
5. **Warmup real:** STT transcreve 0,5s de silêncio; TTS sintetiza "oi"; LLM gera 1 token.
6. **Reuse de cliente HTTP:** `LLMEngine` mantém um `httpx.AsyncClient` persistente.
7. **Barge-in:** botão "interromper" corta a resposta em andamento.
8. **Ações do modelo:** flag `BMO_ACOES` (desligada por padrão).

Incluir tabela de benchmark (medium vs base) e nota sobre PC da feira (30 tokens/s).

- [ ] **Step 2: Commit**

```bash
git add docs/MELHORIAS.md
git commit -m "docs: registrar melhorias aplicadas (stt, keep-alive, preload, warmup)"
```

---

### Task 4: Checklist de setup por máquina

**Files:**
- Create: `docs/SETUP-DEV.md`
- Create: `docs/SETUP-FEIRA.md`

**Interfaces:**
- Consumes: `docs/MAQUINAS.md`, `README.md`.
- Produces: roteiro passo a passo para cada máquina.

- [ ] **Step 1: Criar `docs/SETUP-DEV.md` (Linux)**

Passos:
1. Clonar o repo.
2. `cp .env.example .env` e ajustar (manter `WHISPER_MODEL=base`).
3. Criar venv: `python -m venv .venv && .venv/bin/pip install -r requirements.txt`.
4. Baixar modelos: `ollama pull qwen3:4b`; rodar uma vez o STT/TTS para cachear.
5. Instalar espeak-ng (se necessário).
6. Rodar: `./run.sh`.
7. Verificar: `curl http://127.0.0.1:8000/health`.

- [ ] **Step 2: Criar `docs/SETUP-FEIRA.md` (Windows)**

Passos:
1. Clonar o repo.
2. `copy .env.example .env`.
3. `python -m venv .venv` e `.venv\Scripts\activate && pip install -r requirements.txt`.
4. Instalar Ollama (Windows) e `ollama pull qwen3:4b`.
5. Instalar espeak-ng via MSI.
6. Rodar: `run.bat`.
7. Verificar: `http://127.0.0.1:8000/health`.
8. Nota: LLM roda na RTX 2050 (~30 tokens/s); se Ollama não usar GPU, verificar variáveis de ambiente.

- [ ] **Step 3: Commit**

```bash
git add docs/SETUP-DEV.md docs/SETUP-FEIRA.md
git commit -m "docs: checklists de setup para PC de dev e PC da feira"
```

---

### Task 5: Inicializar repositório Git e primeiro commit

**Files:**
- Create: `.git/` (repo local)

**Interfaces:**
- Consumes: todos os arquivos do projeto (sem .env, .venv, node_modules).
- Produces: repositório local com histórico inicial.

- [ ] **Step 1: Inicializar o repositório**

```bash
cd ~/Documentos/bmollm
git init
git branch -M main
```

- [ ] **Step 2: Verificar o que será commitado**

```bash
git status
git add -A
git status  # revisar: nenhum .env, .venv, node_modules, logs
```

- [ ] **Step 3: Commit inicial**

```bash
git commit -m "feat: BMO-LLM inicial (stt base, keep-alive 24h, preload, warmup, run.sh)"
```

- [ ] **Step 4: Criar repositório no GitHub**

Opção A (CLI): `gh repo create bmo-llm --public --source=. --remote=origin --push`
Opção B (web): criar repo vazio no GitHub e depois:
```bash
git remote add origin https://github.com/<usuario>/bmo-llm.git
git push -u origin main
```

- [ ] **Step 5: Verificar push**

Confirmar no GitHub que os arquivos estão lá e que `.env`/`.venv`/`node_modules` **não** aparecem.

---

### Task 6: Verificação de clone na outra máquina (procedural)

**Files:**
- Nenhum (verificação manual).

**Interfaces:**
- Consumes: repo no GitHub, `docs/SETUP-FEIRA.md`.

- [ ] **Step 1: Na máquina da feira, clonar e seguir `docs/SETUP-FEIRA.md`**

- [ ] **Step 2: Confirmar health check**

```bash
curl http://127.0.0.1:8000/health
# esperado: pronto: true, engines ok, ollama modelo_baixado: true
```

- [ ] **Step 3: Confirmar que as melhorias estão ativas**

- `.env` com `WHISPER_MODEL=base`, `OLLAMA_KEEP_ALIVE=24h`, `BMO_PRELOAD=1`.
- Primeiro turno não paga carga de modelos (preload).
- LLM roda na GPU (verificar logs do Ollama).

- [ ] **Step 4: Registrar divergências (se houver)**

Se algum arquivo precisar ser diferente na feira (ex.: `.env` com caminho de espeak-ng), documentar em `docs/MAQUINAS.md` na seção "Divergências conhecidas" — nunca alterar o código-fonte para isso.

---

## Riscos e mitigações

- **Vazamento de segredos:** `.gitignore` revisado na Task 2; verificar com `git status` antes do push.
- **Symlinks quebrados:** `.venv`/`node_modules` não são commitados; a outra máquina cria os seus.
- **README desatualizado:** Task 2 garante seções para ambos os SOs.
- **Branch antiga:** a publicação parte de `~/Documentos/bmollm` (versão mais recente com melhorias), não do `main` antigo do repo `Feira-de-ciencias`.
- **Cache de modelos:** cada máquina precisa baixar os modelos uma vez; documentado nos checklists.

## Próximos passos (fora deste plano)

- Streaming real de TTS (reduzir atraso de ~2s para ~0,3–0,5s).
- Instrumentação ponta a ponta (timestamps por etapa).
- CI no GitHub (pytest) para garantir que as melhorias não regredam.