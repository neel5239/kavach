"""Veena (maya-research/Veena, Apache-2.0) Hindi/Hinglish TTS fakes for Kavach-Clones.
Run: D:/tts-venv/Scripts/python scripts/veena_clones.py
"""
import sys
from pathlib import Path

import soundfile as sf
import torch
from snac import SNAC
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_clones import EN, HI, add_rows  # noqa: E402

MODEL = "D:/tts-models/veena"
START_OF_SPEECH, END_OF_SPEECH, START_OF_HUMAN, END_OF_HUMAN, START_OF_AI, END_OF_AI, BASE = 128257, 128258, 128259, 128260, 128261, 128262, 128266
q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=q, device_map="auto", trust_remote_code=True)
tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
snac = SNAC.from_pretrained("D:/tts-models/snac_24khz").eval().cuda()


def decode(codes):
    codes = codes[: len(codes) // 7 * 7]
    lv = [[], [], []]
    off = [BASE + i * 4096 for i in range(7)]
    for i in range(0, len(codes), 7):
        lv[0].append(codes[i] - off[0])
        lv[1] += [codes[i + 1] - off[1], codes[i + 4] - off[4]]
        lv[2] += [codes[i + 2] - off[2], codes[i + 3] - off[3], codes[i + 5] - off[5], codes[i + 6] - off[6]]
    hc = [torch.tensor(l, dtype=torch.int32, device="cuda").unsqueeze(0).clamp(0, 4095) for l in lv]
    with torch.no_grad():
        return snac.decode(hc).squeeze().clamp(-1, 1).cpu().numpy()


def speak(spk, text):
    ids = tok.encode(f"<spk_{spk}> {text}", add_special_tokens=False)
    inp = torch.tensor([[START_OF_HUMAN, *ids, END_OF_HUMAN, START_OF_AI, START_OF_SPEECH]], device=model.device)
    with torch.no_grad():
        out = model.generate(inp, max_new_tokens=min(int(len(text) * 1.3) * 7 + 21, 1400), do_sample=True, temperature=0.45,
                             top_p=0.9, repetition_penalty=1.05, pad_token_id=tok.pad_token_id or END_OF_AI,
                             eos_token_id=[END_OF_SPEECH, END_OF_AI])
    gen = out[0][inp.shape[1]:].tolist()
    return decode([t for t in gen if BASE <= t < BASE + 7 * 4096])


d = ROOT / "data" / "clones" / "veena"
d.mkdir(parents=True, exist_ok=True)
rows, n = [], 0
lines = [(t, "hi") for t in HI] + [(t, "en") for t in EN[:6]]
for spk in ("kavya", "agastya", "maitri", "vinaya"):
    for text, lang in lines:
        torch.manual_seed(n)
        a = speak(spk, text)
        if len(a) < 24000:
            continue
        p = d / f"veena_{n:04d}.wav"
        sf.write(p, a, 24000)
        rows.append([str(p.relative_to(ROOT)), "veena_" + spk, 1, "test", "veena", lang])
        n += 1
        print(n, spk, round(len(a) / 24000, 1), flush=True)
add_rows(rows)
print("veena", len(rows))
