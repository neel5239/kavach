#!/usr/bin/env bash
# Kavach one-time setup (macOS / Linux). Needs Python 3.12, ffmpeg, internet once.
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip >/dev/null
if command -v nvidia-smi >/dev/null 2>&1; then
  pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
else
  pip install torch==2.11.0   # CPU build (Apple Silicon uses MPS-free CPU path)
fi
pip install -r requirements.txt
pip install --no-deps -r requirements-shield.txt
[ -f models/xlsr-300m/pytorch_model.bin ] || python -c "from huggingface_hub import snapshot_download as s; s('facebook/wav2vec2-xls-r-300m', revision='1a640f32ac3e39899438a2931f9924c02f080a54', local_dir='models/xlsr-300m', allow_patterns=['*.json','*.bin'])"
[ -d models/torch/hub/checkpoints ] || python -c "import os; os.environ['TORCH_HOME']=os.path.abspath('models/torch'); from demucs.pretrained import get_model; get_model('htdemucs')"
[ -f models/second_opinion/model.safetensors ] || python -c "from huggingface_hub import snapshot_download as s; s('mo-thecreator/Deepfake-audio-detection', local_dir='models/second_opinion', allow_patterns=['*.json','*.safetensors'])"
command -v ffmpeg >/dev/null || echo "Install ffmpeg: brew install ffmpeg  (mac)  or  sudo apt install ffmpeg  (Linux)"
python -m pytest -q tests
echo "Setup done. Start with ./run.sh"
