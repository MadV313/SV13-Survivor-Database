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

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
    echo Python 3.11 or newer is required.
    py -3 --version
    pause
    exit /b 1
)

if not exist ".venv" (
    py -3 -m venv .venv
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
    if not exist ".env.example" (
        echo ERROR: .env.example is missing from the repository.
        pause
        exit /b 1
    )
    copy ".env.example" ".env" >nul
    if errorlevel 1 exit /b 1
    echo.
    echo Created .env from .env.example.
    echo Add DISCORD_TOKEN, DISCORD_GUILD_ID, and your knowledge source.
)

echo.
echo Running repository preflight...
python tools\repo_audit.py
if errorlevel 1 (
    echo Repository preflight failed.
    pause
    exit /b 1
)

echo.
echo SV13 Survivor Database bot dependencies installed.
pause
