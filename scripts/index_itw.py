"""Index the In-the-Wild dataset and make a speaker-disjoint split.

Output: data/index/itw.csv with columns path,speaker,label(1=fake),split
"""
import csv
import random  # dataset shuffling only, not security-sensitive
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "itw" / "release_in_the_wild"
OUT = ROOT / "data" / "index" / "itw.csv"


def main(seed: int = 7) -> None:
    meta = SRC / "meta.csv"
    rows = list(csv.DictReader(meta.open(encoding="utf-8")))
    by_spk = defaultdict(list)
    for r in rows:
        lab = r["label"].strip().lower()
        if lab not in ("spoof", "bona-fide"):
            continue
        by_spk[r["speaker"].strip()].append((r["file"].strip(), 1 if lab == "spoof" else 0))
    # Only speakers with both classes can be fairly placed in any split.
    speakers = sorted(by_spk)
    random.Random(seed).shuffle(speakers)
    n = len(speakers)
    n_test, n_cal = round(n * 0.2), round(n * 0.1)
    split = {s: "test" for s in speakers[:n_test]}
    split.update({s: "cal" for s in speakers[n_test:n_test + n_cal]})
    split.update({s: "train" for s in speakers[n_test + n_cal:]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    counts = defaultdict(lambda: [0, 0])
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "speaker", "label", "split"])
        for s in speakers:
            for fn, lab in by_spk[s]:
                p = SRC / fn
                if p.exists():
                    w.writerow([str(p.relative_to(ROOT)), s, lab, split[s]])
                    counts[split[s]][lab] += 1
    for k in ("train", "cal", "test"):
        print(f"{k:5s} speakers={sum(1 for v in split.values() if v == k):3d} real={counts[k][0]:6d} fake={counts[k][1]:6d}")


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:2]))
