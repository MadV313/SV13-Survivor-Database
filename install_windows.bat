@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher "py" was not found.
    echo Install Python 3.11 or newer, then run this again.
    pause
    exit /b 1
)

if not exist ".venv" (
    py -3 -m venv .venv
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo Created .env from .env.example.
    echo Open .env and add DISCORD_TOKEN, DISCORD_GUILD_ID, and SV13_KNOWLEDGE_DIR.
)

echo.
echo SV13 Survivor Database bot dependencies installed.
pause
