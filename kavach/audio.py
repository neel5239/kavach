"""Audio front end: decode, trim silence, normalise loudness, phone-line simulation, windowing."""
from __future__ import annotations

import shutil
import subprocess  # nosec B404 - only used to run ffmpeg with fixed arguments

import numpy as np
from scipy.signal import butter, fftconvolve, resample_poly, sosfilt

SR = 16000
TARGET_RMS_DB = -23.0


class AudioError(ValueError):
    """Input could not be turned into usable speech audio."""


def decode_bytes(data: bytes, timeout: float = 15.0, max_seconds: float = 30.0) -> np.ndarray:
    """Decode any ffmpeg-readable audio bytes to 16 kHz mono float32.

    ffmpeg runs as a separate process with fixed arguments (no shell) and a timeout.
    Output is capped at max_seconds + 1 so a hostile file cannot expand without bound.
    """
    if not data:
        raise AudioError("The file is empty.")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is not installed")
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
           "-t", str(max_seconds + 1), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1"]
    try:
        proc = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout, check=False)  # nosec B603 - fixed argv, no shell, data via stdin
    except subprocess.TimeoutExpired as e:
        raise AudioError("Decoding took too long. Try a shorter clip.") from e
    if proc.returncode != 0 or not proc.stdout:
        raise AudioError("This file could not be read as audio. Use WAV, MP3, M4A, OGG, FLAC or WEBM.")
    wav = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    if not np.all(np.isfinite(wav)):
        wav = np.nan_to_num(wav)
    return wav


def to_mono_16k(wav: np.ndarray, sr: int) -> np.ndarray:
    wav = np.asarray(wav, dtype=np.float32)
    if wav.ndim == 2:
        wav = wav.mean(axis=1)
    if sr != SR:
        g = np.gcd(int(sr), SR)
        wav = resample_poly(wav, SR // g, int(sr) // g).astype(np.float32)
    return wav


def trim_bounds(wav: np.ndarray, top_db: float = 35.0, frame_ms: int = 25) -> tuple[int, int]:
    """Sample range [start, end) that remains after trimming leading/trailing silence."""
    n = int(SR * frame_ms / 1000)
    if len(wav) < n:
        return 0, len(wav)
    frames = len(wav) // n
    rms = np.sqrt(np.mean(wav[: frames * n].reshape(frames, n) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-12)
    keep = np.where(db > db.max() - top_db)[0]
    if len(keep) == 0 or db.max() < -70:
        return 0, 0
    return int(keep[0] * n), int((keep[-1] + 1) * n)


def trim_silence(wav: np.ndarray, top_db: float = 35.0, frame_ms: int = 25) -> np.ndarray:
    """Remove leading and trailing frames quieter than (peak frame level - top_db).

    This removes the silence-length shortcut known from ASVspoof (Mueller et al. 2021).
    """
    s, e = trim_bounds(wav, top_db, frame_ms)
    return wav[s:e]


def normalise(wav: np.ndarray, target_db: float = TARGET_RMS_DB) -> np.ndarray:
    """Scale to a fixed RMS level so loudness carries no label information."""
    if len(wav) == 0:
        return wav.astype(np.float32)
    rms = float(np.sqrt(np.mean(wav ** 2) + 1e-12))
    if rms < 1e-6:
        return wav
    out = wav * (10 ** (target_db / 20) / rms)
    return np.clip(out, -1.0, 1.0).astype(np.float32)


def speech_seconds(wav: np.ndarray) -> float:
    return len(wav) / SR


def preprocess(wav: np.ndarray) -> np.ndarray:
    return normalise(trim_silence(wav))


_PHONE_SOS = butter(6, [300, 3400], btype="bandpass", fs=8000, output="sos")


def phone_sim(wav: np.ndarray, rng: np.random.Generator | None = None, snr_db: float | None = None) -> np.ndarray:
    """Simulate a narrowband phone call: 8 kHz, 300-3400 Hz band, G.711 mu-law, light noise, back to 16 kHz."""
    rng = rng or np.random.default_rng(0)
    x = resample_poly(wav, 1, 2)
    x = sosfilt(_PHONE_SOS, x)
    peak = np.max(np.abs(x)) + 1e-9
    x = x / peak * 0.9
    mu = 255.0
    y = np.sign(x) * np.log1p(mu * np.abs(x)) / np.log1p(mu)
    y = np.round(y * 127) / 127
    x = np.sign(y) * (np.expm1(np.abs(y) * np.log1p(mu)) / mu)
    snr = snr_db if snr_db is not None else float(rng.uniform(25, 40))
    p = np.mean(x ** 2) + 1e-12
    x = x + rng.normal(0, np.sqrt(p / 10 ** (snr / 10)), size=x.shape)
    x = resample_poly(x, 2, 1) * peak / 0.9
    return normalise(x.astype(np.float32))


def replay_sim(wav: np.ndarray, rng: np.random.Generator | None = None) -> np.ndarray:
    """Simulate playing audio from a small speaker into a room and recording it with a phone/laptop mic.

    Small-speaker band limits + resonance, a synthetic room impulse response (RT60 0.15-0.7 s),
    mic self-noise and room noise. Applied to real and fake clips alike, so "replayed" carries no label.
    """
    rng = rng or np.random.default_rng(0)
    lo, hi = rng.uniform(120, 350), rng.uniform(5500, 7800)
    x = sosfilt(butter(4, [lo, hi], btype="bandpass", fs=SR, output="sos"), wav)
    f0 = rng.uniform(800, 3000)  # speaker cone resonance
    x = x + 0.25 * sosfilt(butter(2, [f0 * 0.85, f0 * 1.15], btype="bandpass", fs=SR, output="sos"), x)
    rt60 = rng.uniform(0.15, 0.7)
    n = int(rt60 * SR)
    t = np.arange(n) / SR
    rir = rng.normal(0, 1, n) * np.exp(-6.9 * t / rt60)
    rir[: int(0.002 * SR)] = 0
    rir[0] = 1.0 / rng.uniform(0.15, 0.6)  # direct path dominates when mic is close
    rir = rir / np.max(np.abs(rir))
    y = fftconvolve(x, rir)[: len(x)]
    p = np.mean(y ** 2) + 1e-12
    snr = rng.uniform(15, 35)
    noise = rng.normal(0, 1, len(y))
    noise = sosfilt(butter(1, 1000, btype="lowpass", fs=SR, output="sos"), noise)  # room noise is low-heavy
    noise *= np.sqrt(p / 10 ** (snr / 10) / (np.mean(noise ** 2) + 1e-12))
    y = y + noise
    if rng.random() < 0.5:  # some phones/apps compress again
        y = np.tanh(2.0 * y / (np.max(np.abs(y)) + 1e-9)) * 0.7
    return normalise(y.astype(np.float32))


def windows(wav: np.ndarray, win_s: float = 4.0, hop_s: float = 1.0) -> list[tuple[float, float, np.ndarray]]:
    """Split into overlapping windows. A clip shorter than one window is returned whole."""
    w, h = int(win_s * SR), int(hop_s * SR)
    if len(wav) <= w:
        return [(0.0, len(wav) / SR, wav)]
    out = []
    start = 0
    while start + w <= len(wav):
        out.append((start / SR, (start + w) / SR, wav[start: start + w]))
        start += h
    if out[-1][1] * SR < len(wav):
        s = len(wav) - w
        out.append((s / SR, len(wav) / SR, wav[s:]))
    return out


def center_crop(wav: np.ndarray, seconds: float) -> np.ndarray:
    n = int(seconds * SR)
    if len(wav) <= n:
        return wav
    s = (len(wav) - n) // 2
    return wav[s: s + n]


# ---------------- Phase 2 channel conditions ----------------
CODECS = {
    # name: (ffmpeg encoder args, container, sample rate)
    "amr": (["-c:a", "libopencore_amrnb", "-b:a", "12.2k"], "amr", 8000),   # GSM / mobile network voice codec
    "opus": (["-c:a", "libopus", "-b:a", "12k", "-application", "voip"], "ogg", 16000),  # WhatsApp / VoIP calls
    "gsm": (["-c:a", "libgsm"], "gsm", 8000),
    "mp3": (["-c:a", "libmp3lame", "-b:a", "32k"], "mp3", 16000),
}


def resample_8k(wav: np.ndarray) -> np.ndarray:
    """Down to 8 kHz and back (narrowband telephone bandwidth), nothing else."""
    return resample_poly(resample_poly(wav, 1, 2), 2, 1).astype(np.float32)[: len(wav)]


def codec(wav: np.ndarray, name: str, timeout: float = 20.0) -> np.ndarray:
    """Encode and decode through a real codec with ffmpeg (fixed argv, no shell)."""
    enc, fmt, sr = CODECS[name]
    ffmpeg = shutil.which("ffmpeg")
    pcm = np.clip(wav, -1, 1).astype(np.float32).tobytes()
    a = subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0",
                        "-ar", str(sr), *enc, "-f", fmt, "pipe:1"], input=pcm, capture_output=True, timeout=timeout, check=True)  # nosec B603
    b = subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-f", fmt, "-i", "pipe:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1"],
                       input=a.stdout, capture_output=True, timeout=timeout, check=True)  # nosec B603
    y = np.frombuffer(b.stdout, dtype=np.float32).copy()
    if len(y) < len(wav):
        y = np.pad(y, (0, len(wav) - len(y)))
    return normalise(y[: len(wav)])


def add_noise(wav: np.ndarray, snr_db: float, rng: np.random.Generator | None = None, kind: str = "mixed") -> np.ndarray:
    """Add noise at a fixed SNR. 'mixed' = half white, half low-pass (street/room-like)."""
    rng = rng or np.random.default_rng(0)
    n = rng.normal(0, 1, len(wav))
    if kind != "white":
        n = 0.5 * n + 0.5 * sosfilt(butter(2, 800, btype="lowpass", fs=SR, output="sos"), rng.normal(0, 3, len(wav)))
    p = np.mean(wav ** 2) + 1e-12
    n *= np.sqrt(p / 10 ** (snr_db / 10) / (np.mean(n ** 2) + 1e-12))
    return normalise((wav + n).astype(np.float32))


def channel_aug(wav: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Random training-time channel: optional 8 kHz, one random codec, optional noise, optional replay."""
    x = wav
    if rng.random() < 0.3:
        x = replay_sim(x, rng)
    if rng.random() < 0.5:
        x = resample_8k(x)
    x = codec(x, rng.choice(list(CODECS)))
    if rng.random() < 0.6:
        x = add_noise(x, float(rng.uniform(5, 25)), rng)
    return x


def speech_activity(wav: np.ndarray, frame_ms: int = 30) -> dict:
    """Is someone actually talking in this window? Energy above the window's own noise floor, plus
    low spectral flatness (voices are tonal; hiss, fans and silence are flat). Used by live mode so
    background noise is never judged as a voice."""
    n = int(SR * frame_ms / 1000)
    k = len(wav) // n
    if k < 5:
        return {"speech": False, "ratio": 0.0}
    fr = wav[: k * n].reshape(k, n)
    e = 10 * np.log10(np.mean(fr ** 2, axis=1) + 1e-12)
    floor = np.percentile(e, 10)
    loud = (e > floor + 9.0) & (e > -55.0)
    if not loud.any():
        return {"speech": False, "ratio": 0.0}
    spec = np.abs(np.fft.rfft(fr[loud] * np.hanning(n), axis=1)) + 1e-9
    band = spec[:, int(80 * n / SR): int(4000 * n / SR)]
    flat = np.exp(np.mean(np.log(band), axis=1)) / np.mean(band, axis=1)
    voiced = loud.copy()
    voiced[loud] = flat < 0.35
    ratio = float(voiced.mean())
    return {"speech": ratio >= 0.2, "ratio": round(ratio, 3)}
