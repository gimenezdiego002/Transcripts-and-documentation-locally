@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo The app has not been set up. Run setup.bat first.
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo The dashboard build is missing. Run setup.bat first.
  pause
  exit /b 1
)

echo Starting Local Knowledge Studio at http://127.0.0.1:8000
start "" /B powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000'"
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

