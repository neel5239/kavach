"""Stress-test Kavach with 'laundered' versions of clips, the way a scammer would hide artifacts.

For every input clip (real and cloned) make: as-is, WhatsApp Opus, phone AMR-NB, street noise 15 dB,
speaker-to-mic replay, and Opus + noise. Score each through the running app and print a table.
Run: python scripts/attack_test.py OUTDIR real.wav clone1.wav clone2.wav ...
"""
import json
import sys
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kavach import audio  # noqa: E402

ATTACKS = {
    "as-is": lambda x, r: x,
    "WhatsApp Opus": lambda x, r: audio.codec(x, "opus"),
    "Phone AMR-NB": lambda x, r: audio.codec(x, "amr"),
    "Street noise 15 dB": lambda x, r: audio.add_noise(x, 15.0, r),
    "Speaker->mic replay": lambda x, r: audio.replay_sim(x, r),
    "Opus + noise": lambda x, r: audio.add_noise(audio.codec(x, "opus"), 15.0, r),
}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    c = httpx.Client(timeout=120)
    rows = []
    for src in sys.argv[2:]:
        x = audio.decode_bytes(Path(src).read_bytes())
        x = audio.normalise(x)
        for name, f in ATTACKS.items():
            y = f(x, np.random.default_rng(3))
            p = out / f"{Path(src).stem}__{name.replace(' ', '_').replace('>', '').replace('+', 'plus')}.wav"
            sf.write(p, y, audio.SR)
            j = c.post("http://127.0.0.1:8320/api/analyze", files={"file": (p.name, p.read_bytes(), "audio/wav")}).json()
            rows.append({"clip": Path(src).stem, "attack": name, "verdict": j.get("verdict"), "score": j.get("score")})
            print(f"{Path(src).stem:20s} {name:22s} {j.get('verdict'):9s} {round((j.get('score') or 0) * 100, 1):6}")
    (out / "results.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
