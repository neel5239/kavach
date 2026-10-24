@echo off
REM Kavach one-time setup (Windows). Needs Python 3.12 and internet once.
cd /d "%~dp0"
py -3.12 -c "1" >nul 2>nul && (set PY=py -3.12) || (set PY=python)
echo [1/4] Creating virtual environment...
%PY% -m venv .venv || goto :err
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
echo [2/4] Installing PyTorch...
nvidia-smi >nul 2>nul
if %errorlevel%==0 (
  echo NVIDIA GPU found: installing CUDA build
  pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128 || goto :err
) else (
  echo No NVIDIA GPU: installing CPU build ^(slower, about 1-3 s per clip^)
  pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu || goto :err
)
echo [3/4] Installing other packages (about 5 minutes)...
pip install -r requirements.txt || goto :err
pip install --no-deps -r requirements-shield.txt || goto :err
echo [3b/4] Downloading pretrained models (about 1.3 GB, once)...
if not exist models\xlsr-300m\pytorch_model.bin (python -c "from huggingface_hub import snapshot_download as s; s('facebook/wav2vec2-xls-r-300m', revision='1a640f32ac3e39899438a2931f9924c02f080a54', local_dir='models/xlsr-300m', allow_patterns=['*.json','*.bin'])" || goto :err)
if not exist models\torch\hub\checkpoints (python -c "import os; os.environ['TORCH_HOME']=os.path.abspath('models/torch'); from demucs.pretrained import get_model; get_model('htdemucs')" || goto :err)
if not exist models\second_opinion\model.safetensors (python -c "from huggingface_hub import snapshot_download as s; s('mo-thecreator/Deepfake-audio-detection', local_dir='models/second_opinion', allow_patterns=['*.json','*.safetensors'])" || goto :err)
echo [4/4] Checking ffmpeg...
where ffmpeg >nul 2>nul || (
  echo ffmpeg not found. Installing with winget...
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
)
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where ffmpeg >nul 2>nul || echo WARNING: ffmpeg still not found. Install it from https://www.gyan.dev/ffmpeg/builds/ and re-run setup.bat
python -m pytest -q tests
echo.
echo Setup done. Start the app with run.bat
pause
exit /b 0
:err
echo Setup failed. Read the error above.
pause
exit /b 1
