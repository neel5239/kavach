"""Index LibriSpeech dev-clean (real, clean read speech, CC BY 4.0) with a speaker-disjoint split.

Gives the model clean REAL speech, so studio-quality audio is not mistaken for "fake".
Output: data/index/libri.csv
"""
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "libri" / "LibriSpeech" / "dev-clean"


def main():
    spk = sorted(p.name for p in SRC.iterdir() if p.is_dir())
    random.Random(8).shuffle(spk)  # dataset shuffling only
    n = len(spk)
    split = {s: "test" for s in spk[: n // 4]}
    split.update({s: "cal" for s in spk[n // 4: n // 4 + 4]})
    split.update({s: "train" for s in spk[n // 4 + 4:]})
    rows = []
    for s in spk:
        files = sorted((SRC / s).rglob("*.flac"))
        for f in files[:45]:
            rows.append([str(f.relative_to(ROOT)), "libri_" + s, 0, split[s], "libri", "en"])
    out = ROOT / "data" / "index" / "libri.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "speaker", "label", "split", "generator", "lang"])
        w.writerows(rows)
    for k in ("train", "cal", "test"):
        print(k, sum(1 for r in rows if r[3] == k))


if __name__ == "__main__":
    main()
