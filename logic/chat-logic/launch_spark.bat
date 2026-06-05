@echo off
title Spark - AI Teaching Companinon (Launcher)
color 0B

echo ============================================================
echo        Spark - AI Teaching Companinon (Launcher)
echo ============================================================
echo.

:: ---------------------------------------------------------------
:: 1. Check if Ollama is installed
:: ---------------------------------------------------------------
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Ollama is NOT installed or not found in PATH.
    echo.
    echo  Please download and install Ollama from:
    echo  https://ollama.com/download
    echo.
    echo  After installing, restart this launcher.
    echo.
    pause
    exit /b 1
)
echo [OK] Ollama found.

:: ---------------------------------------------------------------
:: 2. Check if Python is installed
:: ---------------------------------------------------------------
where python >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is NOT installed or not found in PATH.
    echo.
    echo  Please download and install Python 3.10 or later from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT during installation:
    echo    - Select "Install for all users"
    echo    - CHECK the box "Add Python to PATH" /
    echo      "Add python.exe to environment variables"
    echo.
    echo  After installing, restart this launcher.
    echo.
    pause
    exit /b 1
)
echo [OK] Python found.

:: ---------------------------------------------------------------
:: 3. Set up virtual environment if it doesn't exist
:: ---------------------------------------------------------------
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo.
    echo [SETUP] Creating virtual environment...
    python -m venv "%~dp0venv"
    if %errorlevel% neq 0 (
        color 0C
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)

:: ---------------------------------------------------------------
:: 4. Install / update dependencies
:: ---------------------------------------------------------------
echo.
echo [SETUP] Installing dependencies (this may take a minute on first run)...
call "%~dp0venv\Scripts\activate.bat"
pip install -q -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies are up to date.

:: ---------------------------------------------------------------
:: 5. Pull the Gemma model (skips automatically if already pulled)
:: ---------------------------------------------------------------
echo.
echo [SETUP] Ensuring Gemma model is available (first run downloads ~2.5 GB)...
ollama pull gemma3:4b
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to pull gemma3:4b model. Check your internet connection.
    pause
    exit /b 1
)
echo [OK] Gemma model ready.

:: ---------------------------------------------------------------
:: 6. Start Ollama serve in a new window
:: ---------------------------------------------------------------
echo.
echo [START] Launching Ollama server...
start "Ollama Server" cmd /k "title Ollama Server & echo Starting Ollama server... & echo (Keep this window open) & echo. & ollama serve"

:: Give Ollama a few seconds to start up
echo Waiting for Ollama to start...
timeout /t 5 /nobreak >nul

:: ---------------------------------------------------------------
:: 7. Start bot_teaching_assistant.py in a new window
:: ---------------------------------------------------------------
echo.
echo [START] Launching Spark Teaching Assistant...
start "Spark Teaching Assistant" cmd /k "title Spark Teaching Assistant & cd /d "%~dp0" & call venv\Scripts\activate.bat & echo Starting Spark AI Teaching Assistant... & echo. & python bot_teaching_assistant.py"

:: ---------------------------------------------------------------
:: 8. Wait a moment then open the browser
:: ---------------------------------------------------------------
echo.
echo Waiting for the bot to start...
timeout /t 8 /nobreak >nul

echo.
echo [START] Opening browser...
start http://localhost:7860

:: ---------------------------------------------------------------
:: Done
:: ---------------------------------------------------------------
echo.
echo ============================================================
echo  Spark is running! Two new windows have been opened:
echo.
echo    1. Ollama Server   - keep this open
echo    2. Spark Assistant  - keep this open
echo.
echo  Your browser should open to http://localhost:7860
echo  Click "Start Session" and begin speaking!
echo.
echo  To stop Spark, close both windows or press Ctrl+C in each.
echo ============================================================
echo.
pause
