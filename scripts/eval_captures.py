"""Score the user's own captures with every saved model head (and with/without noise removal).
Usage: python scripts/eval_captures.py "ai:file1,file2" "real:file3,file4"   (files in data/user_tests/captures)
Prints each clip's score per model so a threshold / model choice can be made on the actual device chain."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kavach import audio, denoise  # noqa: E402
from kavach.features import Extractor  # noqa: E402
from kavach.model import aggregate, load_head  # noqa: E402

CAP = ROOT / "data" / "user_tests" / "captures"
HEADS = [d for d in ["kavach", "kavach_v1", "itw", "itw_quick"] if (ROOT / "models" / d / "head.pt").exists()]


def main():
    ex = Extractor()
    heads = {h: load_head(ROOT / "models" / h)[0] for h in HEADS}
    groups = {}
    for arg in sys.argv[1:]:
        lab, _, files = arg.partition(":")
        groups[lab] = [CAP / f.strip() for f in files.split(",") if f.strip()]
    for lab, files in groups.items():
        for f in files:
            x, sr = sf.read(f, dtype="float32")
            x = audio.to_mono_16k(x, sr)
            for mode, y in (("raw", audio.preprocess(x)), ("denoised", audio.preprocess(denoise.denoise(x)))):
                feats = ex.batch([w for _, _, w in audio.windows(y)]).astype(np.float32)
                with torch.no_grad():
                    sc = {h: round(aggregate(torch.sigmoid(m(torch.from_numpy(feats))).numpy().tolist()), 3) for h, m in heads.items()}
                print(f"{lab:5s} {f.name[:40]:40s} {mode:8s} {sc}")


if __name__ == "__main__":
    main()
