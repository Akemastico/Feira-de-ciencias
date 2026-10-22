#!/usr/bin/env bash
# Roda o BMO-LLM localmente (Linux). Requer .venv criado.
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
    echo "Ambiente virtual nao encontrado. Crie com: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi
echo "Diagnostico: http://127.0.0.1:8000/health"
echo "Pagina do BMO: http://127.0.0.1:8000"
.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
EOF
chmod +x ~/Documentos/bmollm/run.sh
echo created