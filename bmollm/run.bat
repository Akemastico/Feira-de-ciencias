@echo off
pushd "%~dp0"

:: Abre o navegador
start "" http://127.0.0.1:8000

:: Ativa ambiente virtual e sobe servidor
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo Ambiente virtual nao encontrado. Rode: python -m venv .venv
    pause
    exit /b 1
)

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
