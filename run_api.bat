@echo off
REM Windows launcher for the SEC Filing RAG FastAPI server.
REM
REM Just double-click this file, or run from PowerShell:
REM     .\run_api.bat

cd /d "%~dp0"
set PYTHONPATH=%cd%

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo Starting SEC Filing RAG API...
echo Open http://localhost:8000/docs in your browser.
echo Press Ctrl+C to stop.
echo.

uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
