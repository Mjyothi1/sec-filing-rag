@echo off
REM Windows launcher for the SEC Filing RAG Streamlit UI.
REM Handles Python path issues that cause "ModuleNotFoundError: No module named 'app'"
REM
REM Just double-click this file, or run it from PowerShell:
REM     .\run_ui.bat

REM Move to the directory this script is in (the project root)
cd /d "%~dp0"

REM Set the Python path to the current directory so `app` is importable
set PYTHONPATH=%cd%

REM Activate the virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo Starting SEC Filing RAG UI...
echo Open http://localhost:8501 in your browser when ready.
echo Press Ctrl+C to stop.
echo.

REM Run Streamlit
streamlit run app/ui.py
