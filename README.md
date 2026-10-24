# Kavach: AI voice-clone detector

HYPNEXIS'26 · Track 01 · AI-01. Listens to 2–10 s of speech and says **REAL**, **NOT SURE** or **FAKE (AI clone)**, with a timeline of which seconds looked synthetic.

## Run it on your laptop (Windows)

1. Install **Python 3.12** from python.org. During install, tick "Add python.exe to PATH".
2. Unzip this folder somewhere with a short path, e.g. `D:\kavach`.
3. Double-click **`setup.bat`**. It needs internet once (about 3 GB for PyTorch). It also installs ffmpeg if missing and runs the tests.
4. Double-click **`run.bat`**. The browser opens `http://localhost:8320`.
5. Wait for the badge at the top right to say **Model ready**. Then upload a clip, click a demo clip or press **Record**.
6. **Live call mode:** press *Start live call* (mic) or pick a clip under *Simulate a call*. The score updates every 0.5 s.

After setup everything runs **offline**. The speech model (`models/xlsr-300m`) and the trained detectors (`models/kavach`, `models/kavach_seg`) are inside this folder.

macOS / Linux: `bash setup.sh`, then `bash run.sh`. You need ffmpeg (`brew install ffmpeg` or `sudo apt install ffmpeg`).

A GPU is optional. With an NVIDIA GPU one clip takes well under a second; on CPU it takes about 1–3 seconds.

## What's in the folder

| Path | What it is |
|---|---|
| `app/` | FastAPI server (`server.py`) and the web UI (`static/`) |
| `kavach/` | Detector: audio cleaning, phone simulation, XLS-R features, classifier, metrics |
| `models/xlsr-300m/` | Frozen XLS-R 300M speech model (pinned commit 1a640f3) |
| `models/kavach/` | Final (Phase 2) detector head + calibrated thresholds, used by the app |
| `models/kavach_seg/` | Segment head: marks synthetic 0.5 s cells inside a call |
| `models/itw/` | Phase 1 detector (In-the-Wild only), kept for comparison |
| `samples/` | Demo clips shown as buttons in the app |
| `scripts/` | Data indexing, feature extraction, training, clone generation, evaluation |
| `tests/` | Unit, API and security tests (`pytest`), browser end-to-end check and load check |
| `runs/` | Every result number used in the deck (`results.json`, `clones.json`, `load_test.json`) |
| `data/index/` | Speaker-disjoint split and clone lists |
| `data/clones/` | Our own fakes from SNAC, Kokoro and RVC (test only, never used in training) |
| `data/modern/` | Modern neural TTS voices (Microsoft edge-tts, Kokoro); ~25% of voices held out for testing |
| `data/partial/` | 160 partial fakes (real call with 1–3 s faked) + exact fake intervals in `labels.json` |
| `docs/` | Project document, pitch deck, your-steps checklist, build sheet |

The In-the-Wild dataset (8 GB) is **not** included because it isn't needed to run the app. To retrain, download it from https://huggingface.co/datasets/mueller91/In-The-Wild into `data/itw/`, then run:

```
python scripts/index_itw.py
python scripts/extract.py data/index/itw.csv itw
python scripts/train.py itw
python scripts/eval_clones.py itw
# Phase 2 (needs the extra feature sets; see scripts/phase2.py)
python scripts/phase2.py
python scripts/eval_clones.py kavach itw
```

## Tests

```
.venv\Scripts\python -m pytest -q tests                     # 53 unit, API, streaming and security tests
.venv\Scripts\python tests\load_check.py                    # needs the app running
python tests\e2e_check.py http://127.0.0.1:8320 samples\<clip>.wav   # needs Playwright
```

## Privacy

Audio is analysed in memory and never written to disk or logs. Every cloned voice in `data/clones` was made from public In-the-Wild clips or from a team member's own voice with consent.
