import numpy as np
import pytest

from conftest import tone, wav_bytes
from kavach import audio


def test_trim_removes_lead_and_tail_silence():
    x = tone(2.0, lead_silence=1.5, tail_silence=1.0)
    y = audio.trim_silence(x)
    assert abs(len(y) / audio.SR - 2.0) < 0.06


def test_trim_all_silence_returns_empty():
    assert len(audio.trim_silence(np.zeros(16000, np.float32))) == 0


def test_silence_length_does_not_survive_preprocessing():
    a = audio.preprocess(tone(2.0, lead_silence=0.1))
    b = audio.preprocess(tone(2.0, lead_silence=2.0, tail_silence=2.0))
    assert abs(len(a) - len(b)) <= 400 * 2


def test_normalise_equalises_loudness():
    q, l = audio.normalise(tone(amp=0.01)), audio.normalise(tone(amp=0.5))
    rq, rl = np.sqrt(np.mean(q ** 2)), np.sqrt(np.mean(l ** 2))
    assert abs(20 * np.log10(rq) - 20 * np.log10(rl)) < 0.5


def test_normalise_silence_is_safe():
    z = np.zeros(1000, np.float32)
    assert np.all(audio.normalise(z) == 0)


def test_phone_sim_keeps_length_and_removes_high_band():
    x = tone(2.0, freq=6000)  # far above the 3.4 kHz phone band
    y = audio.phone_sim(audio.normalise(tone(2.0, freq=300) + x))
    assert abs(len(y) - len(x)) <= 2
    spec = np.abs(np.fft.rfft(y))
    f = np.fft.rfftfreq(len(y), 1 / audio.SR)
    assert spec[(f > 5500) & (f < 6500)].mean() < 0.05 * spec[(f > 250) & (f < 350)].mean()


def test_windows_cover_clip():
    x = np.zeros(int(7.3 * audio.SR), np.float32)
    w = audio.windows(x, 4.0, 1.0)
    assert w[0][0] == 0.0 and abs(w[-1][1] - 7.3) < 1e-6
    assert all(abs((b - a) - 4.0) < 1e-6 for a, b, _ in w)


def test_windows_short_clip_single():
    w = audio.windows(np.zeros(16000, np.float32))
    assert len(w) == 1 and w[0][1] == 1.0


def test_decode_wav_and_resample():
    x = tone(1.0, sr=44100)
    y = audio.decode_bytes(wav_bytes(x, 44100))
    assert abs(len(y) - 16000) < 50 and y.dtype == np.float32


def test_decode_rejects_garbage():
    with pytest.raises(audio.AudioError):
        audio.decode_bytes(b"this is not audio at all" * 100)


def test_decode_rejects_empty():
    with pytest.raises(audio.AudioError):
        audio.decode_bytes(b"")


def test_decode_caps_duration():
    y = audio.decode_bytes(wav_bytes(tone(40.0)), max_seconds=30)
    assert len(y) / audio.SR <= 31.05


def test_center_crop():
    x = np.arange(10 * audio.SR, dtype=np.float32)
    c = audio.center_crop(x, 4.0)
    assert len(c) == 4 * audio.SR and c[0] == 3 * audio.SR


# ---------------- Phase 2 channel conditions ----------------
@pytest.mark.parametrize("name", ["amr", "opus", "gsm", "mp3"])
def test_codecs_roundtrip_keep_length(name):
    x = audio.normalise(tone(2.0))
    y = audio.codec(x, name)
    assert len(y) == len(x) and np.isfinite(y).all() and np.abs(y).max() > 0.01


def test_resample_8k_removes_above_4k():
    y = audio.resample_8k(audio.normalise(tone(2.0, freq=300) + tone(2.0, freq=6000)))
    f = np.fft.rfftfreq(len(y), 1 / audio.SR)
    sp = np.abs(np.fft.rfft(y))
    assert sp[(f > 5500) & (f < 6500)].mean() < 0.02 * sp[(f > 250) & (f < 350)].mean()


def test_add_noise_snr():
    x = audio.normalise(tone(2.0))
    y = audio.add_noise(x, 10.0, np.random.default_rng(0))
    assert y.shape == x.shape


def test_replay_sim_shape():
    x = audio.normalise(tone(2.0))
    assert audio.replay_sim(x, np.random.default_rng(0)).shape == x.shape


def test_noise_shield_snr_estimate_separates_noisy_from_clean():
    from kavach.denoise import estimate_snr_db
    rng = np.random.default_rng(0)
    speech = np.concatenate([tone(0.6), np.zeros(int(0.3 * audio.SR), np.float32)] * 5)
    noisy = audio.add_noise(audio.normalise(speech), 10.0, rng)
    assert estimate_snr_db(audio.normalise(speech)) > estimate_snr_db(noisy)
    assert estimate_snr_db(noisy) < 24.0
