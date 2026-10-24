"""RVC voice-conversion fakes (Applio, user's own consented 'me' voice model).
Run from Applio dir: D:/tools/Applio/env/Scripts/python D:/kavach/scripts/rvc_clones.py
Converts real In-the-Wild test clips into the user's voice: content real, voice cloned.
"""
import csv
import os
import random  # dataset shuffling only, not security-sensitive
import sys
from pathlib import Path

ROOT = Path("D:/kavach")
APP = Path("D:/tools/Applio")
os.chdir(APP)
sys.path.insert(0, str(APP))
sys.path.insert(0, str(ROOT / "scripts"))
from core import run_infer_script  # noqa: E402
from make_clones import add_rows  # noqa: E402

N = 100
reals = [r for r in csv.DictReader(open(ROOT / "data/index/itw.csv", encoding="utf-8")) if r["split"] == "test" and r["label"] == "0"]
random.Random(9).shuffle(reals)
reals = reals[-N:]  # different clips from the SNAC set
d = ROOT / "data" / "clones" / "rvc"
d.mkdir(parents=True, exist_ok=True)
rows = []
for k, r in enumerate(reals):
    out = d / f"rvc_{k:04d}.wav"
    try:
        run_infer_script(pitch=0, index_rate=0.75, volume_envelope=1.0, protect=0.33, f0_method="rmvpe",
                         input_path=str(ROOT / r["path"]), output_path=str(out),
                         pth_path=str(APP / "logs/me/me_100e_1100s.pth"), index_path=str(APP / "logs/me/me.index"),
                         split_audio=False, f0_autotune=False, f0_autotune_strength=1.0, proposed_pitch=False,
                         proposed_pitch_threshold=155.0, clean_audio=False, clean_strength=0.5, export_format="WAV",
                         embedder_model="contentvec")
    except Exception as e:
        print("fail", k, e)
        continue
    if out.exists():
        rows.append([str(out.relative_to(ROOT)), "rvc_me", 1, "test", "rvc", "en"])
    print(k, flush=True)
add_rows(rows)
print("rvc", len(rows))
