"""API integration + security tests. Uses a stub detector so tests run without GPU or model."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from conftest import tone, wav_bytes
from app import server
from kavach import audio
from kavach.model import Thresholds, aggregate, verdict_for
from kavach import vad as _vad

_REAL_SPEECH_SECONDS = _vad.speech_seconds  # captured before any test patches it
_REAL_SPEECH_ONLY = _vad.speech_only


class StubDetector:
    """Scores by pitch so tests are deterministic: high tone -> fake."""
    th = Thresholds(0.3, 0.7, 0.5)

    def score_live(self, seg):
        s = self.score_window(seg)
        return {"raw": s, "denoised": None, "noisy": False, "score": s}

    def score_window(self, wav):
        f = np.abs(np.fft.rfft(wav))
        return 0.9 if np.fft.rfftfreq(len(wav), 1 / audio.SR)[f.argmax()] > 1000 else 0.1

    def analyze(self, wav, orig_duration=None):
        clean = audio.preprocess(wav)
        sp = len(clean) / audio.SR
        if sp < 0.3:
            return {"verdict": "NOT SURE", "score": None, "confidence": 0.0, "duration_s": orig_duration, "speech_s": sp,
                    "windows": [], "reason": "No speech found in the clip.", "thresholds": self.th.__dict__, "latency_ms": 1.0}
        f = np.abs(np.fft.rfft(clean))
        peak = np.fft.rfftfreq(len(clean), 1 / audio.SR)[f.argmax()]
        s = 0.9 if peak > 1000 else 0.1
        wins = audio.windows(clean)
        return {"verdict": verdict_for(aggregate([s] * len(wins)), self.th, sp), "score": s, "confidence": 0.9,
                "duration_s": orig_duration, "speech_s": sp,
                "windows": [{"start": a, "end": b, "score": s} for a, b, _ in wins], "reason": None,
                "thresholds": self.th.__dict__, "latency_ms": 1.0}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("KAVACH_NO_PRELOAD", "1")
    # test tones are not human speech: treat any non-silent window as speech here (real VAD is tested separately)
    monkeypatch.setattr(server.vad, "speech_seconds", lambda w: len(w) / audio.SR if np.sqrt(np.mean(w ** 2)) > 1e-3 else 0.0)
    monkeypatch.setattr(server.vad, "speech_only", lambda w: (w, len(w) / audio.SR) if np.sqrt(np.mean(w ** 2)) > 1e-3 else (w[:0], 0.0))
    server.set_detector(StubDetector())
    return TestClient(server.app)


def post(client, data, name="clip.wav", ctype="audio/wav"):
    return client.post("/api/analyze", files={"file": (name, data, ctype)})


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["model_loaded"] is True


def test_index_served_with_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200 and "Kavach" in r.text
    h = r.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "default-src 'self'" in h["content-security-policy"]
    assert "frame-ancestors 'none'" in h["content-security-policy"]


def test_analyze_real_and_fake(client):
    r1 = post(client, wav_bytes(tone(3.0, freq=200)))
    r2 = post(client, wav_bytes(tone(3.0, freq=3000)))
    assert r1.status_code == 200 and r1.json()["verdict"] == "REAL"
    assert r2.json()["verdict"] == "FAKE"
    j = r2.json()
    assert set(j) >= {"verdict", "score", "confidence", "duration_s", "speech_s", "windows", "thresholds", "latency_ms"}
    assert r2.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("fmt,name", [("FLAC", "a.flac"), ("OGG", "a.ogg")])
def test_other_formats(client, fmt, name):
    r = post(client, wav_bytes(tone(2.0), fmt=fmt), name, "audio/" + name.split(".")[1])
    assert r.status_code == 200, r.text


def test_silence_only_is_not_sure(client):
    r = post(client, wav_bytes(np.zeros(3 * 16000, np.float32)))
    assert r.status_code == 200 and r.json()["verdict"] == "NOT SURE"


# ---------------- security / robustness ----------------
def test_rejects_oversized(client):
    r = post(client, b"\0" * (10 * 1024 * 1024 + 10))
    assert r.status_code == 413


def test_rejects_wrong_type(client):
    r = post(client, b"MZ\x90\x00" * 100, "evil.exe", "application/x-msdownload")
    assert r.status_code == 415


def test_rejects_corrupt_audio(client):
    r = post(client, b"RIFF\x00\x00\x00\x00WAVEgarbage" * 50)
    assert r.status_code == 422 and "could not be read" in r.json()["error"]


def test_rejects_empty(client):
    assert post(client, b"").status_code == 422


def test_rejects_too_long(client):
    r = post(client, wav_bytes(tone(45.0)))
    assert r.status_code == 422 and "30 seconds" in r.json()["error"]


def test_rejects_too_short(client):
    r = post(client, wav_bytes(tone(0.1)))
    assert r.status_code == 422


def test_path_like_filename_is_harmless(client):
    r = post(client, wav_bytes(tone(2.0)), "../../../../windows/win.ini.wav")
    assert r.status_code == 200


def test_text_disguised_as_audio(client):
    r = post(client, b"<script>alert(1)</script>" * 20, "x.wav", "audio/wav")
    assert r.status_code == 422


def test_sample_path_traversal_blocked(client):
    for p in ["/samples/..%2F..%2Fapp%2Fserver.py", "/samples/../app/server.py", "/samples/%2e%2e%5cserver.py"]:
        assert client.get(p).status_code == 404


def test_no_api_docs_exposed(client):
    for p in ("/docs", "/openapi.json", "/redoc"):
        assert client.get(p).status_code == 404


def test_model_missing_returns_503(monkeypatch):
    monkeypatch.setenv("KAVACH_MODEL", "models/does_not_exist")
    server.set_detector(None)
    server._detector_error = "missing"
    c = TestClient(server.app)
    assert c.get("/api/health").json()["model_loaded"] is False
    assert post(c, wav_bytes(tone(2.0))).status_code == 503
    server._detector_error = None


# ---------------- streaming (Phase 2 R3) ----------------
def _stream(client, x, chunk=8000):
    msgs = []
    with client.websocket_connect("/ws/stream", headers={"origin": "http://localhost:8320"}) as ws:
        for k in range(0, len(x), chunk):
            ws.send_bytes(x[k:k + chunk].astype(np.float32).tobytes())
            if k + chunk >= int(server.STREAM_MIN_S * audio.SR):
                msgs.append(ws.receive_json())
    return msgs


def test_stream_updates_every_500ms(client):
    msgs = _stream(client, tone(5.0, freq=3000))
    assert len(msgs) >= 8
    ts = [m["t"] for m in msgs]
    assert all(abs((b - a) - 0.5) < 1e-6 for a, b in zip(ts, ts[1:]))
    assert msgs[-1]["verdict"] == "FAKE"


def test_stream_real_voice(client):
    assert _stream(client, tone(4.0, freq=200))[-1]["verdict"] == "REAL"


def test_stream_silence_is_listening(client):
    msgs = _stream(client, np.zeros(3 * audio.SR, np.float32))
    assert all(m["verdict"] == "LISTENING" for m in msgs)


def test_stream_rejects_bad_chunk(client):
    with client.websocket_connect("/ws/stream", headers={"origin": "http://localhost:8320"}) as ws:
        ws.send_bytes(bytes(7))  # not a whole float32
        assert "error" in ws.receive_json()


def test_stream_rejects_foreign_origin(client):
    import starlette.websockets
    with pytest.raises(starlette.websockets.WebSocketDisconnect):
        with client.websocket_connect("/ws/stream", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()


def test_model_loads_once_under_concurrent_first_requests(monkeypatch):
    """Regression: on a fresh start, simultaneous requests each loaded the 1.2 GB model and crashed the server."""
    import threading
    import time

    import kavach.model as km
    calls = []

    class SlowDetector:
        def __init__(self, *a, **k):
            calls.append(1)
            time.sleep(0.5)

    monkeypatch.setattr(km, "Detector", SlowDetector)
    monkeypatch.setattr(server, "_detector", None)
    monkeypatch.setattr(server, "_detector_error", None)
    ts = [threading.Thread(target=server.get_detector) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(calls) == 1
    server.set_detector(None)


def test_real_vad_ignores_silence_and_noise():
    rng = np.random.default_rng(0)
    for x in (np.zeros(4 * audio.SR, np.float32), rng.normal(0, 0.01, 4 * audio.SR).astype(np.float32),
              rng.normal(0, 0.1, 4 * audio.SR).astype(np.float32)):
        assert _REAL_SPEECH_SECONDS(x) < 0.3


def test_stream_noise_only_never_judged(client, monkeypatch):
    monkeypatch.setattr(server.vad, "speech_seconds", _REAL_SPEECH_SECONDS)  # real detector
    monkeypatch.setattr(server.vad, "speech_only", _REAL_SPEECH_ONLY)
    noise = np.random.default_rng(1).normal(0, 0.05, 5 * audio.SR).astype(np.float32)
    msgs = _stream(client, noise)
    assert msgs and all(m["verdict"] == "LISTENING" for m in msgs)


def test_quiet_or_no_speech_upload_is_not_called_real(client, monkeypatch):
    monkeypatch.setattr(server.vad, "speech_seconds", lambda w: 0.0)  # e.g. phone too far from the mic
    r = post(client, wav_bytes(tone(3.0, freq=200)))
    j = r.json()
    assert r.status_code == 200 and j["verdict"] == "NOT SURE" and "Too quiet" in j["reason"]
