"""Build dist/Kavach_project.zip: everything a teammate needs to run Kavach offline.

Excludes the venv, raw datasets, cached features and personal team recordings.
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / (sys.argv[1] if len(sys.argv) > 1 else "Kavach_project.zip")
EXCLUDE_DIRS = {".venv", "dist", "__pycache__", ".pytest_cache"}
EXCLUDE_PREFIX = ["data/raw", "data/itw", "data/features", "data/team", "data/libri", "data/user_tests", "models/itw_quick", "models/kavach_v1", "models/kavach_seg_v1", "runs/bad.wav", "runs/denoise_val", "docs/hyp", "docs/build_manual.js", "docs/Kavach_Your_Steps.docx", "docs/Kavach_Your_Steps.pdf", "docs/phase-sheet.html"]
EXCLUDE_SUFFIX = {".pyc"}


def wanted(rel: str) -> bool:
    parts = rel.split("/")
    if any(p in EXCLUDE_DIRS or (p.startswith(".") and p not in (".gitignore", ".gitattributes")) for p in parts):
        return False
    if any(rel == x or rel.startswith(x + "/") for x in EXCLUDE_PREFIX):
        return False
    return Path(rel).suffix not in EXCLUDE_SUFFIX


def main():
    OUT.parent.mkdir(exist_ok=True)
    n, size = 0, 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(ROOT.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if not wanted(rel):
                continue
            ctype = zipfile.ZIP_STORED if p.suffix in {".bin", ".pt", ".wav", ".pptx", ".docx", ".pdf", ".png", ".npy"} else zipfile.ZIP_DEFLATED
            z.write(p, "kavach/" + rel, compress_type=ctype)
            n += 1
            size += p.stat().st_size
    print(f"{OUT}  files={n}  content={size / 2**20:.0f} MB  zip={OUT.stat().st_size / 2**20:.0f} MB")


if __name__ == "__main__":
    main()
