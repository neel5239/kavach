"""Modern neural TTS fakes for TRAINING and held-out TESTING (closer to GPT / Gemini voice quality).

Generators: edge-tts (Microsoft neural voices, needs internet) and Kokoro (local).
Voices are split: ~75% train, ~25% test (unseen voices), so the test stays honest.
Run: D:/tts-venv/Scripts/python scripts/gen_modern.py
Writes data/modern/<gen>/*.wav and data/index/modern.csv
"""
import asyncio
import csv
import io
import random
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_clones import EN, HI  # noqa: E402

OUT = ROOT / "data" / "modern"
IDX = ROOT / "data" / "index" / ("modern_b.csv" if "--append" in sys.argv else "modern.csv")

EXTRA_EN = [
    "Sure, I can help with that. Let me check your booking details first.",
    "The train leaves at seven fifteen from platform three, please be on time.",
    "Honestly, I think the second option is better for your budget.",
    "Your package will arrive between two and five in the afternoon.",
    "Let's go over the plan once more before the meeting starts.",
    "I'm really sorry to hear that, is there anything I can do?",
    "Press one to speak to an agent, or stay on the line.",
    "That's a great question. The short answer is yes, but it depends.",
    "We have updated our policy, and the changes take effect next month.",
    "Can you hear me clearly? The network here is not very good.",
    "Okay, I've noted that down. Anything else you need today?",
    "The doctor will see you now, please come to room number four.",
    "It looks like it might rain later, so carry an umbrella.",
    "Your verification code is four eight two nine, do not share it.",
    "Hi, this is Priya from the bank, I'm calling about your loan application.",
    "Beta, phone mat kaatna, mujhe tumse ek zaroori baat karni hai.",
    "Sir, aapka account temporarily block ho gaya hai, abhi verify kariye.",
    "I'll send you the link on WhatsApp, just click it and enter the code.",
]
EXTRA_HI = [
    "हाँ जी, मैं आपकी मदद कर सकता हूँ, बस एक मिनट रुकिए।",
    "आपका पार्सल कल शाम तक पहुँच जाएगा।",
    "बेटा, मैं तुम्हारा चाचा बोल रहा हूँ, नया नंबर है ये।",
    "कृपया लाइन पर बने रहें, आपकी कॉल हमारे लिए महत्वपूर्ण है।",
    "मीटिंग चार बजे है, समय पर आ जाना।",
    "आज बहुत गर्मी है, पानी पीते रहना।",
]
EN_ALL = EN + EXTRA_EN
HI_ALL = HI + EXTRA_HI


def write_rows(rows):
    new = not IDX.exists()
    with IDX.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["path", "speaker", "label", "split", "generator", "lang"])
        w.writerows(rows)


async def edge_gen():
    import edge_tts
    voices = await edge_tts.list_voices()
    pick = [v["ShortName"] for v in voices if v["Locale"] in ("en-IN", "hi-IN", "en-US", "en-GB", "gu-IN", "en-AU")]
    random.Random(21).shuffle(pick)  # voice split is fixed across runs
    rnd = random.Random(99 if APPEND else 21)
    n_test = max(3, len(pick) // 4)
    test_v = set(pick[:n_test])
    d = OUT / "edge"
    d.mkdir(parents=True, exist_ok=True)
    rows, k = [], 0
    for v in pick:
        lang = "hi" if v.startswith(("hi-", "gu-")) else "en"
        texts = rnd.sample(HI_ALL, min(10, len(HI_ALL))) if lang == "hi" else rnd.sample(EN_ALL, 14)
        for txt in texts:
            rate = f"{rnd.randint(-12, 12):+d}%"
            pitch = f"{rnd.randint(-8, 8):+d}Hz"
            try:
                com = edge_tts.Communicate(txt, v, rate=rate, pitch=pitch)
                buf = b""
                async for ch in com.stream():
                    if ch["type"] == "audio":
                        buf += ch["data"]
                x, sr = sf.read(io.BytesIO(buf), dtype="float32")
            except Exception as e:
                print("edge fail", v, e)
                continue
            p = d / f"edge{'b' if APPEND else ''}_{k:05d}.wav"
            k += 1
            sf.write(p, x, sr)
            rows.append([str(p.relative_to(ROOT)), "edge_" + v, 1, "test" if v in test_v else "train", "edge", lang])
        print("edge voice", v, "test" if v in test_v else "train", flush=True)
    write_rows(rows)
    print("edge", len(rows), "test voices", sorted(test_v))


def kokoro_gen():
    from kokoro_onnx import Kokoro
    k = Kokoro("D:/tts-models/kokoro-v1.0.onnx", "D:/tts-models/voices-v1.0.bin")
    voices = [v for v in k.get_voices() if v[:2] in ("af", "am", "bf", "bm", "hf", "hm")]
    rnd = random.Random(22)
    rnd.shuffle(voices)
    # split voices: ~30% are test-only; the Kokoro clone-test rows are later filtered to these voices
    n_test = max(3, int(len(voices) * 0.3))
    test_v = set(voices[:n_test])
    d = OUT / "kokoro"
    d.mkdir(parents=True, exist_ok=True)
    rows, n = [], 0
    for v in voices:
        hi = v[0] == "h"
        texts = rnd.sample(HI_ALL, min(10, len(HI_ALL))) if hi else rnd.sample(EN_ALL, 12)
        for txt in texts:
            a, sr = k.create(txt, voice=v, speed=rnd.uniform(0.85, 1.15), lang="hi" if hi else ("en-us" if v[0] == "a" else "en-gb"))
            p = d / f"kok_{n:05d}.wav"
            n += 1
            sf.write(p, a, sr)
            rows.append([str(p.relative_to(ROOT)), "kokoro_" + v, 1, "test" if v in test_v else "train", "kokoro", "hi" if hi else "en"])
    write_rows(rows)
    print("kokoro", len(rows), "test voices", sorted(test_v))


APPEND = "--append" in sys.argv

if __name__ == "__main__":
    if IDX.exists() and not APPEND:
        IDX.unlink()
    what = [a for a in sys.argv[1:] if not a.startswith("--")] or ["kokoro", "edge"]
    if "kokoro" in what:
        kokoro_gen()
    if "edge" in what:
        asyncio.run(edge_gen())
