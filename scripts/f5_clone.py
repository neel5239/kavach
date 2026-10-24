"""Zero-shot clone a voice from a few seconds of reference audio with F5-TTS (never used in Kavach training).

Run: D:/tools/f5/.venv/Scripts/python D:/kavach/scripts/f5_clone.py REF.wav "ref transcript" OUTDIR
Local testing only, with the speaker's consent. Outputs are not distributed.
"""
import sys
from pathlib import Path

import soundfile as sf
import torch
import torchaudio


def _load(path, *a, **k):  # torchaudio>=2.9 needs torchcodec + FFmpeg DLLs; soundfile is enough here
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return torch.from_numpy(x.T.copy()), sr


def _save(path, wav, sr, *a, **k):
    sf.write(str(path), wav.detach().cpu().numpy().T, sr)


torchaudio.load = _load
torchaudio.save = _save

from f5_tts.api import F5TTS  # noqa: E402

ref, ref_text, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
NFE = int(sys.argv[4]) if len(sys.argv) > 4 else 32
out.mkdir(parents=True, exist_ok=True)
lines = {
    "clone_scam_1": "Hello, it's me. I had a small accident and my phone is broken. Please send fifty thousand rupees to this number right now.",
    "clone_scam_2": "Don't tell anyone at home, okay? I'll explain everything tomorrow, just transfer the money quickly.",
    "clone_normal": "Hey, I'm on my way. I'll reach in ten minutes, wait for me near the gate.",
}
tts = F5TTS()
for name, text in lines.items():
    tts.infer(ref_file=ref, ref_text=ref_text, gen_text=text, file_wave=str(out / f"{name}.wav"), seed=7, remove_silence=True, nfe_step=NFE, cfg_strength=2.0)
    print("wrote", out / f"{name}.wav")
