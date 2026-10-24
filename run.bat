@echo off
REM Start Kavach at http://localhost:8320 (works offline after setup)
cd /d "%~dp0"
set HF_HUB_OFFLINE=1
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & pause & exit /b 1)
start "" /min cmd /c "timeout /t 10 >nul & start http://localhost:8320"
echo Kavach is starting. The browser opens in about 10 seconds. Keep this window open.
.venv\Scripts\python -m uvicorn app.server:app --host 127.0.0.1 --port 8320
pause
