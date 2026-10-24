"""Kavach API + web app.

Run:  .venv/Scripts/python -m uvicorn app.server:app --port 8320
Env:  KAVACH_MODEL=models/itw (model directory)
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path

import json
import time

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from kavach import audio
from kavach.model import aggregate
from kavach import vad
from kavach import second

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
SAMPLES = ROOT / "samples"
MAX_BYTES = 10 * 1024 * 1024
MAX_SECONDS = 30.0
ALLOWED_EXT = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".oga", ".webm", ".aac", ".opus", ".mp4"}

log = logging.getLogger("kavach")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Kavach", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)

def _model_dir() -> str:
    """Final Phase 2 model if trained, else the Phase 1 model."""
    if os.environ.get("KAVACH_MODEL"):
        return os.environ["KAVACH_MODEL"]
    return "models/kavach" if (ROOT / "models/kavach/head.pt").exists() else "models/itw"


_detector = None
_detector_error: str | None = None
_lock = threading.Lock()
_load_lock = threading.Lock()  # only one thread may load the 1.2 GB model


def get_detector():
    """Load the detector once. Concurrent callers wait for the single load. Tests use set_detector()."""
    global _detector, _detector_error
    if _detector is not None:
        return _detector
    with _load_lock:
        if _detector is None and _detector_error is not None and (ROOT / _model_dir() / "head.pt").exists():
            _detector_error = None  # model was trained after startup: try again
        if _detector is None and _detector_error is None:
            try:
                from kavach.model import Detector
                _detector = Detector(ROOT / _model_dir())
            except Exception as e:  # model missing or failed to load: report via /api/health
                _detector_error = f"{type(e).__name__}: {e}"
                log.error("model load failed: %s", _detector_error)
    return _detector


@app.on_event("startup")
def _preload():
    if os.environ.get("KAVACH_NO_PRELOAD") != "1":
        threading.Thread(target=get_detector, daemon=True).start()


def set_detector(det) -> None:
    global _detector, _detector_error
    _detector, _detector_error = det, None


@app.middleware("http")
async def security_headers(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BYTES + 64 * 1024:
        return JSONResponse({"error": "File is larger than 10 MB."}, status_code=413)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' ws://localhost:* ws://127.0.0.1:*; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
    resp.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    elif request.url.path == "/" or request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/api/health")
def health():
    if _detector is None and _load_lock.locked():
        return {"status": "loading", "model_loaded": False, "model": _model_dir(), "localisation": False, "device": None, "error": None}
    det = get_detector()
    return {"status": "ok" if det is not None else "degraded", "model_loaded": det is not None, "model": _model_dir(),
            "localisation": bool(getattr(det, "seg", None)),
            "device": getattr(getattr(det, "extractor", None), "device", None), "error": _detector_error}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), source: str = Form("upload")):
    name = (file.filename or "").lower()
    ext = os.path.splitext(name)[1]
    ctype = (file.content_type or "").lower()
    if ext not in ALLOWED_EXT and not ctype.startswith("audio/"):
        raise HTTPException(415, "Unsupported file type. Use WAV, MP3, M4A, OGG, FLAC or WEBM.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    if not data:
        raise HTTPException(422, "The file is empty.")
    det = get_detector()
    if det is None:
        raise HTTPException(503, "The detection model is not loaded yet.")

    def work():
        wav = audio.decode_bytes(data, max_seconds=MAX_SECONDS)
        dur = len(wav) / audio.SR
        if dur > MAX_SECONDS:
            raise audio.AudioError(f"Clip is {dur:.0f} s long. Use a clip of 30 seconds or less.")
        if dur < 0.3:
            raise audio.AudioError("Clip is too short. Use at least 1 second of speech.")
        sp = vad.speech_seconds(audio.normalise(wav))
        lvl = 20 * np.log10(float(np.sqrt(np.mean(wav ** 2))) + 1e-9)
        with _lock:  # one inference at a time per worker keeps GPU memory flat
            res = det.analyze(wav, orig_duration=dur)
        res["speech_detected_s"], res["input_level_db"] = round(sp, 2), round(lvl, 1)
        if source != "mic" and sp >= 1.0 and not (res.get("noise_shield") or {}).get("active"):
            p2 = second.p_fake(audio.normalise(wav))  # second opinion only on clean, direct audio
            res["second_opinion"] = None if p2 is None else round(p2, 4)
            if p2 is not None and p2 > 0.95 and res["verdict"] != "FAKE":
                res["verdict"], res["confidence"] = "FAKE", round(p2, 3)
                res["reason"] = "Flagged by the second detector (clean audio)."
        if sp < 1.0 and res["verdict"] != "FAKE":  # cannot hear a voice clearly: never claim REAL
            res["verdict"], res["confidence"] = "NOT SURE", 0.0
            res["reason"] = ("Too quiet or no clear speech. Move the phone closer or turn the volume up, "
                             "or use 'Listen to this computer' for calls on this laptop.")
        return res

    try:
        result = await asyncio.to_thread(work)
    except audio.AudioError as e:
        raise HTTPException(422, str(e)) from None
    log.info("analyze dur=%.2fs verdict=%s score=%s latency=%sms", result["duration_s"], result["verdict"], result["score"], result["latency_ms"])
    cap = ROOT / "data" / "user_tests" / "captures"
    if (cap / "CAPTURE_ON").exists() and not os.environ.get("KAVACH_NO_CAPTURE"):  # opt-in local debug capture, off by default
        import soundfile as sf
        sf.write(cap / f"{time.strftime('%H%M%S')}_{result['verdict'].replace(' ', '_')}_{result['score']}.wav",
                 audio.decode_bytes(data, max_seconds=MAX_SECONDS), audio.SR)
    return result


@app.exception_handler(HTTPException)
async def http_error(_req: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


STREAM_WINDOW_S = 4.0       # same window length as upload (more evidence than 2 s)
STREAM_MIN_S = 1.5          # first verdict after 1.5 s of audio
STREAM_MEMORY = 6           # call score = mean of the last 6 updates (3 s): steadier than single windows
STREAM_PERSIST = 3          # FAKE only after this many updates in a row above the live threshold (1.5 s)
LIVE_CALIB = ROOT / "runs" / "live_calib.json"
STREAM_MIN_SPEECH_S = 1.0   # judge a window only if it holds at least this much speech
STREAM_FORGET_S = 6.0       # this long without speech resets the call verdict
STREAM_STEP_S = 0.5
STREAM_MAX_S = 600.0          # one call is capped at 10 minutes
STREAM_MAX_FRAME = 64 * 1024  # bytes per message


@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    """Live call mode. Client sends raw float32 mono 16 kHz PCM chunks; every 500 ms of new audio
    the server scores the latest 2 s and replies with {t, score, smoothed, verdict}."""
    origin = ws.headers.get("origin")
    if origin and not origin.startswith(("http://localhost", "http://127.0.0.1")):
        await ws.close(code=1008)
        return
    await ws.accept()
    src = ws.query_params.get("src", "mic")  # mic | sys | sim ; the second opinion is only trusted off the mic
    det = get_detector()
    if det is None:
        await ws.send_text(json.dumps({"error": "The detection model is not loaded yet."}))
        await ws.close()
        return
    buf = np.zeros(0, dtype=np.float32)
    total, pending, smoothed = 0, 0, None
    # live thresholds: calibrated on real voices recorded through room/speaker/mic chains (unseen speakers)
    try:
        live_fake = max(det.th.fake_above, json.loads(LIVE_CALIB.read_text())["0.95"])
    except Exception:
        live_fake = max(det.th.fake_above, 0.7)
    live_real = det.th.real_below
    above = 0
    recent: list[float] = []
    last_speech_t = 0.0
    step = int(STREAM_STEP_S * audio.SR)
    win = int(STREAM_WINDOW_S * audio.SR)
    try:
        while True:
            data = await ws.receive_bytes()
            if len(data) > STREAM_MAX_FRAME or len(data) % 4:
                await ws.send_text(json.dumps({"error": "Bad audio chunk."}))
                break
            x = np.frombuffer(data, dtype=np.float32)
            if not np.all(np.isfinite(x)):
                x = np.nan_to_num(x)
            buf = np.concatenate([buf, np.clip(x, -1, 1)])[-win * 2:]
            total += len(x)
            pending += len(x)
            if total > STREAM_MAX_S * audio.SR:
                await ws.send_text(json.dumps({"error": "Call is longer than 10 minutes."}))
                break
            if pending < step or len(buf) < int(STREAM_MIN_S * audio.SR):
                continue
            pending = 0
            seg = buf[-win:]
            rms = float(np.sqrt(np.mean(seg ** 2)))
            t = round(total / audio.SR, 2)
            if rms > 1e-4:
                speech, sp = await asyncio.to_thread(vad.speech_only, audio.normalise(seg))
            else:
                speech, sp = seg[:0], 0.0
            if sp < min(STREAM_MIN_SPEECH_S, 0.4 * len(seg) / audio.SR):  # nobody talking: never judge noise
                if t - last_speech_t > STREAM_FORGET_S:
                    recent, smoothed, above = [], None, 0
                await ws.send_text(json.dumps({"t": t, "score": None, "smoothed": smoothed, "verdict": "LISTENING",
                                               "rms": round(rms, 4), "speech_s": round(sp, 2)}))
                continue
            last_speech_t = t
            t0 = time.perf_counter()

            def work(seg=speech):
                with _lock:
                    return det.score_live(seg)

            r = await asyncio.to_thread(work)
            s = r["score"]
            p2 = None
            if src != "mic" and not r["noisy"]:
                p2 = await asyncio.to_thread(second.p_fake, audio.normalise(speech))
                if p2 is not None and p2 > 0.95:
                    s = max(s, live_fake + 0.05)
            recent = (recent + [s])[-STREAM_MEMORY:]
            smoothed = float(np.mean(recent))
            above = above + 1 if smoothed > live_fake else 0
            if above >= STREAM_PERSIST:
                v = "FAKE"
            elif smoothed < live_real:
                v = "REAL"
            elif smoothed > live_fake or smoothed > det.th.fake_above:
                v = "NOT SURE"  # suspicious, but not yet sustained
            else:
                v = "REAL" if smoothed < (live_real + live_fake) / 2 else "NOT SURE"
            await ws.send_text(json.dumps({"t": t, "score": round(s, 4), "smoothed": round(smoothed, 4), "verdict": v, "rms": round(rms, 4), "noisy": r["noisy"], "speech_s": round(sp, 2), "second": None if p2 is None else round(p2, 3),
                                           "denoised": None if r["denoised"] is None else round(r["denoised"], 4),
                                           "ms": round((time.perf_counter() - t0) * 1000, 1), "thresholds": [live_real, live_fake]}))
    except WebSocketDisconnect:
        pass


@app.get("/api/samples")
def samples():
    if not SAMPLES.is_dir():
        return []
    out = []
    for p in sorted(SAMPLES.iterdir()):
        if p.suffix.lower() in ALLOWED_EXT and p.is_file():
            out.append({"name": p.stem.replace("_", " "), "file": p.name})
    return out


@app.get("/samples/{fname}")
def sample_file(fname: str):
    p = (SAMPLES / fname).resolve()
    if p.parent != SAMPLES.resolve() or not p.is_file() or p.suffix.lower() not in ALLOWED_EXT:
        raise HTTPException(404, "Not found")
    return FileResponse(p)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
