@echo off
pushd "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo Ambiente virtual nao encontrado. Rode: python -m venv .venv
    pause
    exit /b 1
)

:: Abre o navegador so depois que o servidor estiver de pe (evita pagina em branco)
start "abrir navegador" /min cmd /c "timeout /t 4 /nobreak >nul && start http://127.0.0.1:8000"

echo.
echo Diagnostico: http://127.0.0.1:8000/health
echo Pagina do BMO: http://127.0.0.1:8000
echo Feche esta janela para encerrar o servidor.
echo.

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
