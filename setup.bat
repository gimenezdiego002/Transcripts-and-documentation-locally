@echo off
setlocal
cd /d "%~dp0"

echo.
echo  Local Knowledge Studio - setup
echo  --------------------------------

where python >nul 2>nul || (
  echo Python 3.11 or newer was not found. Install it from https://python.org and enable "Add Python to PATH".
  exit /b 1
)

where npm >nul 2>nul || (
  echo Node.js 20 or newer was not found. Install the LTS version from https://nodejs.org.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creating the local Python environment...
  python -m venv .venv || exit /b 1
) else (
  echo [1/4] Python environment already exists.
)

echo [2/4] Installing local Python packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || exit /b 1

echo [3/4] Installing dashboard packages...
pushd frontend
call npm install || (popd & exit /b 1)

echo [4/4] Building the local dashboard...
call npm run build || (popd & exit /b 1)
popd

echo.
echo Setup complete.
echo.
echo Whisper models download once when you first transcribe audio:
echo   Fast: tiny   Balanced: small   Accurate: large-v3
echo An internet connection is needed only for that initial model download.
echo.
echo Optional tools:
echo   - Ollama for grounded answer synthesis: https://ollama.com
echo   - LibreOffice or Antiword for legacy .doc files
echo   - Speaker labels: install requirements-optional-diarization.txt and select a local pyannote model in Settings
echo.
echo Run start.bat to open the application.
pause

