# Kavach — start here (for judges)

**HYPNEXIS'26 · Track 01 · AI-01 Voice-Clone Detection for Phone Scams**

Kavach listens to 2–10 seconds of speech and says **REAL**, **NOT SURE** or **FAKE (AI clone)**, marks which half-seconds look synthetic, and can watch a live call with an update every 0.5 s.

---

## Run it in 3 steps (Windows 10/11)

1. **Install Python 3.12** from https://www.python.org/downloads/ — on the first installer screen tick **"Add python.exe to PATH"**.
2. **Unzip** this folder to a short path, for example `C:\kavach` (long paths with spaces can break some tools).
3. Double-click **`setup.bat`** once (needs internet, ~15–20 min: PyTorch ~3 GB, pretrained models ~1.3 GB, other packages, ffmpeg). It ends by running the test suite — you should see `55 passed`.
   Then double-click **`run.bat`**. The browser opens **http://localhost:8320**.

Wait until the badge in the top-right says **Model ready** (about 30 s the first time). Everything after setup works **offline**.

*macOS / Linux:* `bash setup.sh` then `bash run.sh` (install ffmpeg first: `brew install ffmpeg` or `sudo apt install ffmpeg`).
*No NVIDIA GPU?* It still works on CPU; a clip takes ~1–3 s instead of ~0.3 s.

## What to try (2 minutes)

| Do this | You should see |
|---|---|
| Demo clips → **1 Real voice** | Green **REAL** |
| Demo clips → **2 Internet deepfake** | Red **FAKE** |
| Demo clips → **3 Voice cloned RVC** (a team member's voice, cloned with consent) | Red **FAKE**, all seconds marked synthetic |
| Demo clips → **4 Modern AI voice unseen** (a neural TTS voice never used in training) | Red **FAKE** |
| Demo clips → **5 Partly faked call** (real call with ~2.5 s replaced by a fake) | **FAKE**, and the red 0.5 s cells sit on the faked stretch |
| **Live call mode** → "Simulate a call with…" → pick a clip | Score line updating every 0.5 s |
| **Record** and speak for 5–10 s | Your live voice, usually **REAL** |
| **Upload** any audio file (≤30 s) | Verdict + timeline |

## Where the evidence is

| File | What |
|---|---|
| `docs/Kavach_Pitch.pdf` | The pitch deck (16 slides) |
| `docs/Kavach_Project_Document.pdf` | Full write-up: problem, method, system design, security, testing, **all results** (section 15) |
| `docs/Kavach_Phase2_Plan.pdf` | Phase 2 requirements R1–R4 and results |
| `runs/*/results.json` | Raw numbers behind every table and chart (nothing typed by hand) |
| `README.md` | Folder layout and how to retrain |

## Headline results (from `runs/`)

- Unseen speakers (In-the-Wild): **~2% EER**.
- Unseen modern neural TTS voices: **0.5% EER**, ~98% flagged.
- Phase 2: codecs / 8 kHz / noise worst case **1.94×** clean EER (target ≤ 2.5×); partial-fake localisation **F1 80.5%** at 0.5 s; live updates every **500 ms** (~26 ms compute); Phase 1 EERs within **±0.3 pts**.
- Red-team: a voice cloned zero-shot (F5-TTS) from a **3.9 s WhatsApp note**, then hidden with noise/codecs — with the noise shield **16 of 18** versions flagged FAKE, 2 NOT SURE, 0 passed as real.
- Honest limits: audio played through a speaker into a mic is the hardest case; SNAC codec clones are often missed.

## Run the tests yourself

```
.venv\Scripts\python -m pytest -q tests        # 55 unit / API / streaming / security tests
```
With the app running: `.venv\Scripts\python tests\load_check.py` (latency + concurrency).

## Privacy

Uploaded audio is analysed in memory and never written to disk or logs. The app only listens on `localhost`.

## If something goes wrong

| Problem | Fix |
|---|---|
| `python` not found | Re-install Python 3.12 with "Add python.exe to PATH" ticked, open a new window |
| "ffmpeg not found" after setup | Close the window, open a new one, run `run.bat` again (PATH refresh) |
| Badge says "Model not loaded" | Close `run.bat` window and start it again from the Kavach folder |
| Microphone blocked | Click the lock icon in the address bar → Microphone → Allow |
