"""Index the team's own real recordings (consented) for testing and the demo.

Put phone recordings in data/team/ named  <person>_<lang>_<n>.<ext>  e.g. neel_hi_01.m4a
Run: python scripts/ingest_team.py   -> data/index/team.csv (all label 0 = real)
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "team"
EXT = {".wav", ".m4a", ".mp3", ".ogg", ".flac", ".webm", ".aac", ".opus"}


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in sorted(SRC.iterdir()):
        if p.suffix.lower() not in EXT:
            continue
        parts = p.stem.split("_")
        person = parts[0]
        lang = parts[1] if len(parts) > 1 else "xx"
        wav = p.with_suffix(".wav")
        if p.suffix.lower() != ".wav" and not wav.exists():
            import subprocess  # nosec B404 - fixed ffmpeg argv
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(p), "-ac", "1", "-ar", "16000", str(wav)], check=True)  # nosec B603 B607
        rows.append([str(wav.relative_to(ROOT)), person, 0, "test", "real_team", lang])
    out = ROOT / "data" / "index" / "team.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "speaker", "label", "split", "generator", "lang"])
        w.writerows(sorted(set(map(tuple, rows))))
    print(len(rows), "team clips ->", out)


if __name__ == "__main__":
    main()
