"""Generate Kavach-Clones: fakes from generators the detector never saw.

Run with the TTS environment (has kokoro_onnx + snac):
  D:/tts-venv/Scripts/python scripts/make_clones.py snac kokoro
Generators:
  snac   - real In-the-Wild test clips re-synthesised through the SNAC 24 kHz neural codec
           (same speaker, same words: only the vocoder fingerprint differs)
  kokoro - Kokoro-82M TTS, English + Hindi voices
Writes data/clones/<gen>/*.wav and appends rows to data/index/clones.csv
"""
import csv
import random  # dataset shuffling only, not security-sensitive
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "clones"
IDX = ROOT / "data" / "index" / "clones.csv"
N_SNAC = 300

EN = [
    "Hi Mum, it's me. I lost my phone, this is my friend's number.",
    "Papa, I've had a small accident, please don't tell anyone, I need money now.",
    "This is the fraud department of your bank. We noticed a suspicious transaction.",
    "Can you send fifty thousand rupees to this account? I'll return it tomorrow.",
    "Your card will be blocked today unless you share the one time password.",
    "I'm at the police station and they won't let me go without a fine.",
    "Please transfer the amount quickly, the hospital is asking for a deposit.",
    "Hello sir, I'm calling from customer support about your recent order.",
    "I'll explain everything later, just send the money on this UPI ID.",
    "The meeting has moved to four o'clock, can you share the report before that?",
    "We are verifying your account details for the new KYC rules.",
    "Don't call back on this number, my battery is about to die.",
    "Grandma, it's your grandson, I'm stuck abroad and my wallet was stolen.",
    "The courier with your parcel was stopped at customs, there is a fee to pay.",
    "Good morning, the weather is lovely today and the market opens at nine.",
    "I'm calling to confirm your appointment for Saturday afternoon.",
]
HI = [
    "मम्मी, मैं बोल रहा हूँ, मेरा फ़ोन खो गया है, ये मेरे दोस्त का नंबर है।",
    "पापा, एक छोटा सा एक्सीडेंट हो गया है, किसी को मत बताना, जल्दी पैसे भेजो।",
    "मैं बैंक से बोल रहा हूँ, आपके खाते में एक संदिग्ध लेनदेन हुआ है।",
    "प्लीज़ अभी पचास हज़ार रुपये इस नंबर पर भेज दो, कल लौटा दूँगा।",
    "आपका कार्ड आज बंद हो जाएगा, बस ओ टी पी बता दीजिए।",
    "मैं पुलिस स्टेशन में हूँ, जुर्माना भरे बिना छोड़ नहीं रहे।",
    "अस्पताल वाले पैसे जमा करने को बोल रहे हैं, जल्दी कीजिए।",
    "नमस्ते, आज मौसम बहुत अच्छा है और बाज़ार नौ बजे खुलता है।",
]


def add_rows(rows):
    new = not IDX.exists()
    IDX.parent.mkdir(parents=True, exist_ok=True)
    with IDX.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["path", "speaker", "label", "split", "generator", "lang"])
        w.writerows(rows)


def snac_gen():
    import torch
    from scipy.signal import resample_poly
    from snac import SNAC
    m = SNAC.from_pretrained("D:/tts-models/snac_24khz").eval().cuda()
    reals = [r for r in csv.DictReader(open(ROOT / "data/index/itw.csv", encoding="utf-8")) if r["split"] == "test" and r["label"] == "0"]
    random.Random(3).shuffle(reals)
    d = OUT / "snac"
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for k, r in enumerate(reals[:N_SNAC]):
        x, sr = sf.read(ROOT / r["path"], dtype="float32")
        if x.ndim == 2:
            x = x.mean(1)
        x = resample_poly(x, 24000, sr).astype(np.float32)[: 24000 * 10]
        with torch.inference_mode():
            t = torch.from_numpy(x)[None, None].cuda()
            y = m.decode(m.encode(t))[0, 0].float().cpu().numpy()
        p = d / f"snac_{k:04d}.wav"
        sf.write(p, y[: len(x)], 24000)
        rows.append([str(p.relative_to(ROOT)), r["speaker"], 1, "test", "snac", "en"])
    add_rows(rows)
    print("snac", len(rows))


def kokoro_gen():
    from kokoro_onnx import Kokoro
    k = Kokoro("D:/tts-models/kokoro-v1.0.onnx", "D:/tts-models/voices-v1.0.bin")
    voices = k.get_voices()
    en_v = [v for v in voices if v[:2] in ("af", "am", "bf", "bm")]
    hi_v = [v for v in voices if v[:2] in ("hf", "hm")]
    d = OUT / "kokoro"
    d.mkdir(parents=True, exist_ok=True)
    rows, rng = [], random.Random(5)
    n = 0
    for text in EN:
        for v in rng.sample(en_v, min(6, len(en_v))):
            a, sr = k.create(text, voice=v, speed=rng.uniform(0.9, 1.1), lang="en-us" if v[0] == "a" else "en-gb")
            p = d / f"kokoro_{n:04d}.wav"; n += 1
            sf.write(p, a, sr)
            rows.append([str(p.relative_to(ROOT)), "kokoro_" + v, 1, "test", "kokoro", "en"])
    for text in HI:
        for v in hi_v:
            a, sr = k.create(text, voice=v, speed=rng.uniform(0.9, 1.05), lang="hi")
            p = d / f"kokoro_{n:04d}.wav"; n += 1
            sf.write(p, a, sr)
            rows.append([str(p.relative_to(ROOT)), "kokoro_" + v, 1, "test", "kokoro", "hi"])
    add_rows(rows)
    print("kokoro", len(rows))


if __name__ == "__main__":
    for g in sys.argv[1:]:
        {"snac": snac_gen, "kokoro": kokoro_gen}[g]()
