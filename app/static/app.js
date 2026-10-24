"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const dial = $("dial"), arc = $("arc"), verdictEl = $("verdict"), scoreEl = $("score"), advice = $("advice");
  const statusEl = $("status"), fileIn = $("file"), recBtn = $("recBtn"), recLabel = $("recLabel");
  const meter = $("meter"), meterFill = $("meterFill"), recTime = $("recTime");
  const detail = $("detail"), wave = $("wave"), player = $("player");
  const history = $("history"), historyCard = $("historyCard");
  const MAX_BYTES = 10 * 1024 * 1024, MAX_REC_S = 10;
  const ADVICE = {
    REAL: ["real", "This sounds like a real person."],
    "NOT SURE": ["unsure", "Can't be sure. Verify another way before acting."],
    FAKE: ["fake", "Likely AI-cloned. Hang up and call back on a saved number."],
  };
  let busy = false, lastUrl = null;

  function setDial(state, title, sub, pct) {
    dial.dataset.state = state;
    verdictEl.textContent = title;
    scoreEl.textContent = sub;
    arc.style.strokeDasharray = `${Math.max(0, Math.min(100, pct))} 100`;
  }

  async function health() {
    try {
      const r = await fetch("/api/health");
      const j = await r.json();
      statusEl.textContent = j.model_loaded ? `Model ready · ${j.device || "cpu"}` : j.status === "loading" ? "Loading model…" : "Model not loaded";
      if (j.status === "loading") setTimeout(health, 3000);
      statusEl.className = "status " + (j.model_loaded ? "ok" : "bad");
    } catch {
      statusEl.textContent = "Server offline";
      statusEl.className = "status bad";
    }
  }

  async function analyze(blob, name) {
    if (busy) return;
    if (blob.size > MAX_BYTES) return showError("File is larger than 10 MB.");
    if (blob.size === 0) return showError("The file is empty.");
    busy = true;
    setDial("busy", "Listening", "Checking for clone fingerprints…", 0);
    advice.textContent = ""; advice.className = "advice";
    if (lastUrl) URL.revokeObjectURL(lastUrl);
    lastUrl = URL.createObjectURL(blob);
    player.src = lastUrl;
    const fd = new FormData();
    fd.append("file", blob, name);
    try {
      const r = await fetch("/api/analyze", { method: "POST", body: fd });
      const j = await r.json().catch(() => ({ error: "Unexpected server response." }));
      if (!r.ok) throw new Error(j.error || `Request failed (${r.status})`);
      render(j, name, blob);
    } catch (e) {
      showError(e.message);
    } finally {
      busy = false;
    }
  }

  function showError(msg) {
    setDial("idle", "Oops", msg, 0);
    advice.textContent = ""; advice.className = "advice";
  }

  function render(j, name, blob) {
    const [cls, text] = ADVICE[j.verdict] || ADVICE["NOT SURE"];
    const pct = j.score == null ? 0 : Math.round(j.score * 100);
    const sub = j.score == null ? (j.reason || "No speech found") : `Clone score ${pct} / 100`;
    setDial(cls, j.verdict === "FAKE" ? "FAKE" : j.verdict, sub, pct);
    advice.textContent = j.reason && j.verdict === "NOT SURE" ? j.reason : text;
    advice.className = "advice " + cls;
    $("fScore").textContent = j.score == null ? "–" : pct;
    $("fSpeech").textContent = `${j.speech_s.toFixed(1)} s`;
    $("fWin").textContent = j.windows.length;
    $("fLat").textContent = `${Math.round(j.latency_ms)} ms`;
    detail.hidden = false;
    drawWave(blob, j);
    drawSegments(j.segments);
    addHistory(name, j.verdict, pct);
  }

  async function drawWave(blob, j) {
    const ctx = wave.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const w = wave.clientWidth, h = wave.clientHeight;
    wave.width = w * dpr; wave.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const css = getComputedStyle(document.documentElement);
    const fake = css.getPropertyValue("--fake").trim(), real = css.getPropertyValue("--real").trim(), fg = css.getPropertyValue("--muted").trim();
    const span = Math.max(j.speech_s, 0.1);
    const lo = j.thresholds.real_below, hi = j.thresholds.fake_above;
    // shade windows by score (speech-time axis, after silence trim)
    for (const win of j.windows) {
      const x0 = (win.start / span) * w, x1 = (win.end / span) * w;
      const t = Math.max(0, Math.min(1, (win.score - lo) / Math.max(1e-6, hi - lo)));
      ctx.fillStyle = win.score > hi ? fake : win.score < lo ? real : fake;
      ctx.globalAlpha = win.score > hi ? 0.28 : win.score < lo ? 0.14 : 0.08 + 0.15 * t;
      ctx.fillRect(x0, 6, Math.max(2, x1 - x0), h - 12);
    }
    ctx.globalAlpha = 1;
    try {
      const ac = new (window.AudioContext || window.webkitAudioContext)();
      const buf = await ac.decodeAudioData(await blob.arrayBuffer());
      ac.close();
      const d = buf.getChannelData(0), step = Math.max(1, Math.floor(d.length / w));
      ctx.strokeStyle = fg; ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = 0; x < w; x++) {
        let mn = 1, mx = -1;
        for (let k = x * step; k < Math.min(d.length, (x + 1) * step); k++) { const v = d[k]; if (v < mn) mn = v; if (v > mx) mx = v; }
        ctx.moveTo(x + 0.5, h / 2 + mn * (h / 2 - 10));
        ctx.lineTo(x + 0.5, h / 2 + mx * (h / 2 - 10));
      }
      ctx.stroke();
    } catch { /* browser cannot decode this format: shading alone is still shown */ }
  }

  function drawSegments(seg) {
    const wrap = $("segWrap"), bar = $("segBar");
    if (!seg || !seg.cells || !seg.cells.length) { wrap.hidden = true; return; }
    bar.replaceChildren();
    for (const c of seg.cells) {
      const i = document.createElement("i");
      if (c.score > seg.threshold) i.className = "on";
      else if (c.score > seg.threshold * 0.7) i.className = "mid";
      i.title = `${c.start.toFixed(1)}–${c.end.toFixed(1)} s · ${Math.round(c.score * 100)}`;
      bar.append(i);
    }
    $("segInfo").textContent = seg.synthetic_seconds > 0 ? `${seg.synthetic_seconds.toFixed(1)} s look synthetic` : "no synthetic segment found";
    wrap.hidden = false;
  }

  // ---------- live call mode (streaming, 500 ms updates) ----------
  const liveMic = $("liveMic"), liveLabel = $("liveMicLabel"), simSel = $("simSel"), chart = $("liveChart"), liveInfo = $("liveInfo");
  let live = null;
  function liveDraw(points, th) {
    const ctx = chart.getContext("2d"), dpr = window.devicePixelRatio || 1, w = chart.clientWidth, h = chart.clientHeight;
    chart.width = w * dpr; chart.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
    const css = getComputedStyle(document.documentElement);
    const col = (n) => css.getPropertyValue(n).trim();
    const span = 20, tEnd = points.length ? points[points.length - 1].t : 0, t0 = Math.max(0, tEnd - span);
    const X = (t) => ((t - t0) / span) * (w - 12) + 6, Y = (v) => h - 8 - v * (h - 16);
    if (th) for (const [v, c] of [[th[1], "--fake"], [th[0], "--real"]]) {
      ctx.strokeStyle = col(c); ctx.globalAlpha = 0.5; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(6, Y(v)); ctx.lineTo(w - 6, Y(v)); ctx.stroke();
    }
    ctx.setLineDash([]); ctx.globalAlpha = 1; ctx.lineWidth = 2.5; ctx.strokeStyle = col("--fg"); ctx.beginPath();
    let first = true;
    for (const p of points) { if (p.smoothed == null || p.t < t0) continue; const x = X(p.t), y = Y(p.smoothed); first ? ctx.moveTo(x, y) : ctx.lineTo(x, y); first = false; }
    ctx.stroke();
    const last = [...points].reverse().find((p) => p.smoothed != null);
    if (last) { ctx.fillStyle = col(last.verdict === "FAKE" ? "--fake" : last.verdict === "REAL" ? "--real" : "--unsure"); ctx.beginPath(); ctx.arc(X(last.t), Y(last.smoothed), 5, 0, 7); ctx.fill(); }
  }
  function liveStop(msg) {
    if (!live) return;
    try { live.ws.close(); } catch {}
    try { live.ac.close(); } catch {}
    if (live.stream) live.stream.getTracks().forEach((t) => t.stop());
    if (live.timer) clearInterval(live.timer);
    if (live.player) live.player.pause();
    live = null;
    liveMic.setAttribute("aria-pressed", "false"); liveLabel.textContent = "Start live call";
    liveSys.setAttribute("aria-pressed", "false"); liveSysLabel.textContent = "Listen to this computer";
    liveMic.disabled = false; liveSys.disabled = false; simSel.disabled = false;
    if (msg) liveInfo.textContent = msg;
  }
  function liveStart(onReady) {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/stream`);
    ws.binaryType = "arraybuffer";
    const points = [];
    let fakeSince = null;
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.error) { liveStop(m.error); return; }
      points.push(m);
      if (points.length > 200) points.shift();
      liveDraw(points, m.thresholds);
      if (m.verdict === "LISTENING" && m.smoothed == null) {
        setDial("busy", "Listening", "Waiting for speech…", 0);
        advice.className = "advice"; advice.textContent = "";
      }
      if (m.smoothed != null && m.verdict !== "LISTENING") {
        const cls = m.verdict === "FAKE" ? "fake" : m.verdict === "REAL" ? "real" : "unsure";
        setDial(cls, m.verdict, `Live · ${Math.round(m.smoothed * 100)} / 100`, m.smoothed * 100);
        fakeSince = m.verdict === "FAKE" ? (fakeSince ?? m.t) : null;
        advice.className = "advice " + cls;
        advice.textContent = m.verdict === "FAKE" ? `Voice has looked AI-cloned for ${(m.t - fakeSince + 0.5).toFixed(1)} s. Hang up and call back on a saved number.` : (ADVICE[m.verdict] || ["", "Listening…"])[1];
      }
      liveInfo.textContent = m.verdict === "LISTENING" ? `${m.t.toFixed(1)} s · no speech, not judging` : `${m.t.toFixed(1)} s · update ${Math.round(m.ms)} ms${m.noisy ? " · noise shield on" : ""}`;
    };
    ws.onclose = () => live && liveStop("Call ended.");
    ws.onopen = () => onReady(ws);
    return ws;
  }
  const liveSys = $("liveSys"), liveSysLabel = $("liveSysLabel");
  async function liveFromStream(stream, btn, label, busyText) {
    const ac = new AudioContext({ sampleRate: 16000 });
    await ac.audioWorklet.addModule("/static/worklet.js");
    const src = ac.createMediaStreamSource(stream), node = new AudioWorkletNode(ac, "grab");
    src.connect(node);
    live = { ac, stream, btn, label };
    live.ws = liveStart((ws) => { node.port.onmessage = (e) => ws.readyState === 1 && ws.send(e.data.buffer); });
    stream.getAudioTracks().forEach((t) => (t.onended = () => liveStop("Audio sharing stopped.")));
    btn.setAttribute("aria-pressed", "true"); label.textContent = "End call";
    for (const b of [liveMic, liveSys]) if (b !== btn) b.disabled = true;
    simSel.disabled = true;
    setDial("busy", "Live", busyText, 0);
  }
  liveMic.addEventListener("click", async () => {
    if (live) return liveStop("Call ended.");
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } }); }
    catch { return showError("Microphone blocked. Allow mic access or use Simulate a call."); }
    liveFromStream(stream, liveMic, liveLabel, "Listening through the microphone…");
  });
  liveSys.addEventListener("click", async () => {
    if (live) return liveStop("Call ended.");
    if (!navigator.mediaDevices.getDisplayMedia) return showError("This browser cannot share computer audio. Use Chrome or Edge.");
    let shared;
    try {
      shared = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false }, systemAudio: "include" });
    } catch { return showError("Sharing was cancelled. Choose 'Entire screen' and tick 'Share system audio'."); }
    shared.getVideoTracks().forEach((t) => t.stop());  // only the sound is used, the picture is dropped
    const tracks = shared.getAudioTracks();
    if (!tracks.length) return showError("No audio was shared. Choose 'Entire screen' and tick 'Share system audio', then try again.");
    liveFromStream(new MediaStream(tracks), liveSys, liveSysLabel, "Listening to this computer's call audio…");
  });
  simSel.addEventListener("change", async () => {
    const f = simSel.value; simSel.value = "";
    if (!f || live) return;
    const blob = await (await fetch("/samples/" + encodeURIComponent(f))).blob();
    const ac = new AudioContext({ sampleRate: 16000 });
    const buf = await ac.decodeAudioData(await blob.arrayBuffer());
    const pcm = buf.getChannelData(0);
    const url = URL.createObjectURL(blob), pl = new Audio(url);
    live = { ac, player: pl };
    live.ws = liveStart((ws) => {
      let pos = 0;
      pl.play().catch(() => {});
      live.timer = setInterval(() => {
        if (!live) return;
        const end = Math.min(pcm.length, pos + 1600);  // 100 ms per tick = real time
        if (ws.readyState === 1) ws.send(pcm.slice(pos, end).buffer);
        pos = end;
        if (pos >= pcm.length) setTimeout(() => liveStop("Simulated call finished."), 600);
      }, 100);
    });
    liveMic.setAttribute("aria-pressed", "true"); liveLabel.textContent = "End call"; simSel.disabled = true;
    setDial("busy", "Live", "Streaming " + f.replace(/_/g, " ").replace(/\.wav$/, ""), 0);
  });

  function addHistory(name, verdict, pct) {
    const li = document.createElement("li");
    const nm = document.createElement("span"); nm.className = "nm"; nm.textContent = name;
    const tag = document.createElement("span");
    tag.className = "tag " + (ADVICE[verdict] || ADVICE["NOT SURE"])[0];
    tag.textContent = `${verdict} · ${pct}`;
    li.append(nm, tag);
    history.prepend(li);
    while (history.children.length > 8) history.lastChild.remove();
    historyCard.hidden = false;
  }

  // ---------- upload + drag/drop ----------
  fileIn.addEventListener("change", () => { const f = fileIn.files[0]; if (f) analyze(f, f.name); fileIn.value = ""; });
  $("uploadBtn").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileIn.click(); } });
  $("uploadBtn").tabIndex = 0;
  const drop = $("drop");
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) analyze(f, f.name); });

  // ---------- recording ----------
  let rec = null, chunks = [], stream = null, raf = 0, t0 = 0, stopTimer = 0;
  async function startRec() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    } catch {
      return showError("Microphone blocked. Allow mic access or upload a file.");
    }
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/mp4"].find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || "";
    rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunks = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      cancelAnimationFrame(raf); clearTimeout(stopTimer);
      meter.hidden = true; recBtn.setAttribute("aria-pressed", "false"); recLabel.textContent = "Record";
      const type = rec.mimeType || "audio/webm";
      const blob = new Blob(chunks, { type });
      const ext = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "m4a" : "webm";
      analyze(blob, `recording.${ext}`);
    };
    const ac = new AudioContext(), src = ac.createMediaStreamSource(stream), an = ac.createAnalyser();
    an.fftSize = 1024; src.connect(an);
    const buf = new Float32Array(an.fftSize);
    t0 = performance.now();
    const tick = () => {
      an.getFloatTimeDomainData(buf);
      let s = 0; for (const v of buf) s += v * v;
      const lvl = Math.min(100, Math.sqrt(s / buf.length) * 400);
      meterFill.style.setProperty("--lvl", lvl + "%");
      recTime.textContent = `${((performance.now() - t0) / 1000).toFixed(1)} s`;
      raf = requestAnimationFrame(tick);
    };
    rec.start();
    tick();
    stopTimer = setTimeout(() => rec && rec.state === "recording" && rec.stop(), MAX_REC_S * 1000);
    meter.hidden = false; recBtn.setAttribute("aria-pressed", "true"); recLabel.textContent = "Stop";
    setDial("busy", "Recording", `Speak for up to ${MAX_REC_S} s`, 0);
  }
  recBtn.addEventListener("click", () => {
    if (rec && rec.state === "recording") rec.stop();
    else if (!busy) startRec();
  });

  // ---------- demo samples ----------
  async function loadSamples() {
    try {
      const list = await (await fetch("/api/samples")).json();
      if (!list.length) return;
      const box = $("samples");
      for (const s of list) {
        const b = document.createElement("button");
        b.className = "chip"; b.type = "button"; b.textContent = s.name;
        b.addEventListener("click", async () => {
          const r = await fetch("/samples/" + encodeURIComponent(s.file));
          analyze(await r.blob(), s.file);
        });
        box.append(b);
        const o = document.createElement("option"); o.value = s.file; o.textContent = s.name; simSel.append(o);
      }
      $("samplesCard").hidden = false;
    } catch { /* no samples: card stays hidden */ }
  }

  health(); loadSamples();
  setInterval(health, 15000);
})();
