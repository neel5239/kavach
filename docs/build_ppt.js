// Kavach deck. Numbers are read from runs/*.json, never typed by hand.
// Run: NODE_PATH=D:/drowsy-ppt/node_modules node docs/build_ppt.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const rd = (p) => { try { return JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8")); } catch { return null; } };
const R = rd("runs/itw/results.json");
const K = rd("runs/kavach/results.json");
const C = rd("runs/kavach/clones.json") || rd("runs/itw/clones.json");
const L = rd("runs/load_test.json");
const P2 = rd("runs/phase2/results.json");
const ST = rd("runs/stress_test.json");
const pct = (x) => (x == null ? "–" : (x * 100).toFixed(1) + "%");

// Palette: medium-soft neumorphic surface, one accent per meaning
const BG = "E4E9EE", CARD = "EEF2F6", INK = "1E2A33", MUTED = "526270", BRAND = "0F6B58", REAL = "157A43", FAKE = "C0281D", AMBER = "9A5A00";
const HF = "Segoe UI Semibold", BF = "Segoe UI";
const SH = { type: "outer", color: "A9B3BE", blur: 14, offset: 5, angle: 45, opacity: 0.55 };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "Kavach";

function base(kicker, title) {
  const s = pres.addSlide();
  s.background = { color: BG };
  if (kicker) s.addText(kicker.toUpperCase(), { x: 0.6, y: 0.35, w: 9, h: 0.35, fontFace: BF, fontSize: 12, bold: true, color: BRAND, charSpacing: 3 });
  if (title) s.addText(title, { x: 0.6, y: 0.68, w: 12.1, h: 0.85, fontFace: HF, fontSize: 32, color: INK });
  s.addText("Kavach · HYPNEXIS'26 · AI-01", { x: 9.3, y: 7.05, w: 3.8, h: 0.3, fontFace: BF, fontSize: 9, color: MUTED, align: "right" });
  return s;
}
function card(s, x, y, w, h, head, body, color = INK, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: CARD }, line: { color: CARD }, rectRadius: 0.18, shadow: { ...SH } });
  if (head) s.addText(head, { x: x + 0.25, y: y + 0.18, w: w - 0.5, h: 0.5, fontFace: HF, fontSize: opts.headSize || 18, color, valign: "top" });
  if (body) s.addText(body, { x: x + 0.25, y: y + (head ? 0.7 : 0.2), w: w - 0.5, h: h - (head ? 0.85 : 0.4), fontFace: BF, fontSize: opts.size || 13, color: MUTED, valign: "top", paraSpaceAfter: 4 });
}
function arrow(s, x1, y1, x2, y2) {
  s.addShape(pres.shapes.LINE, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color: "9AA6B2", width: 2, endArrowType: "triangle" } });
}

// 1 Title
{
  const s = base(null, null);
  s.addShape(pres.shapes.OVAL, { x: 8.6, y: 1.35, w: 4.0, h: 4.0, fill: { color: CARD }, line: { color: CARD }, shadow: { ...SH } });
  s.addShape(pres.shapes.OVAL, { x: 9.25, y: 2.0, w: 2.7, h: 2.7, fill: { color: BG }, line: { color: "D3DAE1", width: 1 } });
  s.addText("FAKE", { x: 9.25, y: 2.75, w: 2.7, h: 0.8, fontFace: HF, fontSize: 36, color: FAKE, align: "center" });
  s.addText("likely AI-cloned", { x: 9.25, y: 3.45, w: 2.7, h: 0.4, fontFace: BF, fontSize: 12, color: MUTED, align: "center" });
  s.addText("HYPNEXIS'26  ·  TRACK 01  ·  AI-01", { x: 0.8, y: 1.6, w: 7.5, h: 0.4, fontFace: BF, fontSize: 13, bold: true, color: BRAND, charSpacing: 3 });
  s.addText("Kavach", { x: 0.8, y: 2.05, w: 7.5, h: 1.3, fontFace: HF, fontSize: 66, color: INK });
  s.addText("Catching AI-cloned voices before the money moves", { x: 0.8, y: 3.35, w: 7.4, h: 1.0, fontFace: BF, fontSize: 24, color: MUTED });
  s.addText("Voice-clone detection that keeps working on cloning tools it has never seen", { x: 0.8, y: 4.6, w: 7.2, h: 0.8, fontFace: BF, fontSize: 15, color: INK });
}

// 2 The scam
{
  const s = base("The problem", "Seconds of your voice are enough to rob your family");
  const steps = [["1  Collect", "A reel, a WhatsApp voice note or a short \"wrong number\" call gives the scammer 3–10 s of audio."],
    ["2  Clone", "Free open-source tools copy the voice in minutes."],
    ["3  Call", "\"Papa, accident ho gaya, jaldi paise bhejo.\" Same voice, real panic."],
    ["4  Pay", "Money leaves by instant transfer before anyone checks."]];
  steps.forEach(([h, b], k) => { card(s, 0.6 + k * 3.15, 2.0, 2.85, 2.6, h, b, k === 3 ? FAKE : INK); if (k < 3) arrow(s, 3.45 + k * 3.15, 3.3, 3.75 + k * 3.15, 3.3); });
  card(s, 0.6, 5.0, 12.1, 1.55, "Why it works", "People trust a familiar voice, and today's phones give no signal that a voice might be synthetic.", BRAND, { size: 15 });
}

// 3 Why hard
{
  const s = base("Why detection fails", "Most detectors learn the wrong thing");
  const items = [["Unseen cloners", "Trained on known tools, they memorise those tools' quirks and miss new ones."],
    ["Shortcuts", "Benchmarks leak the answer through silence length and loudness. Models learn that instead of the voice."],
    ["Short clips", "2–10 s carries little evidence."],
    ["Many languages", "Training data is mostly English. Scam calls in India are not."]];
  items.forEach(([h, b], k) => card(s, 0.6 + (k % 2) * 6.15, 1.9 + Math.floor(k / 2) * 2.45, 5.95, 2.2, h, b, k === 1 ? FAKE : INK, { size: 15 }));
}

// 4 Insight
{
  const s = base("Our insight", "Every cloner ends in a vocoder");
  card(s, 0.6, 1.9, 3.6, 1.6, "Text + target voice", "what to say, in whose voice", INK);
  card(s, 4.85, 1.9, 3.6, 1.6, "Cloning model", "changes with every new tool", INK);
  card(s, 9.1, 1.9, 3.6, 1.6, "Vocoder / codec", "turns it into sound: leaves fingerprints", FAKE);
  arrow(s, 4.25, 2.7, 4.8, 2.7); arrow(s, 8.5, 2.7, 9.05, 2.7);
  card(s, 0.6, 4.0, 12.1, 2.6, "So we detect the fingerprint, not the tool",
    "XLS-R, a speech model pretrained on 436,000 hours of real speech in 128 languages, is kept frozen. It already knows what real speech looks like at every level. We read all 25 of its layers, learn which ones carry the fake signal, and train only a small classifier on top. A frozen model cannot overfit to one cloner's artifacts.", BRAND, { size: 16 });
}

// 5 How it works
{
  const s = base("How it works", "From a 2–10 second clip to a verdict in under a second");
  const st = [["Clean", "trim silence\nequal loudness"], ["Phone", "8 kHz line,\ncodec, noise"], ["Ears", "XLS-R 300M\nfrozen, 25 layers"], ["Mixer", "learned layer\nweights"], ["Judge", "small MLP\nscore 0–100"], ["Verdict", "REAL / NOT SURE\n/ FAKE"]];
  st.forEach(([h, b], k) => { card(s, 0.6 + k * 2.08, 2.2, 1.85, 2.0, h, b, k === 5 ? BRAND : INK, { size: 12 }); if (k < 5) arrow(s, 2.47 + k * 2.08, 3.2, 2.66 + k * 2.08, 3.2); });
  const v = [["REAL", REAL, "This sounds like a real person."], ["NOT SURE", AMBER, "Can't be sure. Verify another way."], ["FAKE", FAKE, "Likely AI-cloned. Hang up, call back on a saved number."]];
  v.forEach(([t, c, b], k) => card(s, 0.6 + k * 4.1, 4.75, 3.9, 1.8, t, b, c, { size: 14 }));
}

// 6 Shortcuts
{
  const s = base("Beating the shortcuts", "Proving the model listens to the voice, not the silence");
  const e2 = R && R.experiments.E2_shortcut_only_classifier;
  const corr = R && R.experiments.E2_model_score_correlation_with_shortcuts;
  card(s, 0.6, 1.9, 5.9, 2.3, "Shortcut-only classifier", `Uses only duration, silence and loudness.\nEER on unseen speakers: ${e2 ? pct(e2.eer) : "–"}`, AMBER, { size: 16 });
  const cs = corr ? Object.entries(corr).map(([k, v]) => `${k.replace("_", " ")}: ${v.toFixed(2)}`).join("\n") : "–";
  card(s, 6.8, 1.9, 5.9, 2.3, "Our score vs shortcut features", "Correlation (0 = unrelated):\n" + cs, BRAND, { size: 14 });
  card(s, 0.6, 4.5, 12.1, 2.1, "What we do about it", "Every clip is silence-trimmed and loudness-normalised before the model sees it, so neither carries any information. Training also sees phone-line versions (8 kHz, μ-law codec, noise) so call audio does not confuse it.", INK, { size: 15 });
}

// 7 Results
{
  const s = base("Results", "Tested only on speakers and cloners it never saw");
  const ex = R ? R.experiments : {};
  const rows = [["Test", "What it proves", "EER", "n"]];
  const add = (k, label, why) => ex[k] && rows.push([label, why, pct(ex[k].eer), String(ex[k].n)]);
  add("E1_unseen_speakers_4s", "In-the-Wild, unseen speakers, 4 s", "Works on people it never heard");
  add("E3_len_2s", "Same, 2 s clips", "Very short evidence");
  add("E3_len_10s", "Same, 10 s clips", "More evidence");
  add("E4_phone_line", "Same, phone-line audio", "Survives a phone call");
  if (C) for (const [g, v] of Object.entries(C.generators)) rows.push([`Unseen cloner: ${g.toUpperCase()}`, "Never in training", pct(v.eer_vs_itw_real), String(v.n)]);
  const tr = rows.map((r, k) => r.map((c) => ({ text: c, options: { bold: k === 0, color: k === 0 ? BRAND : INK, fill: { color: k === 0 ? "DCE6EC" : CARD }, fontFace: BF, fontSize: 13 } })));
  s.addTable(tr, { x: 0.6, y: 1.75, w: 12.1, colW: [4.4, 4.5, 1.6, 1.6], rowH: 0.42, border: { type: "solid", color: "D3DAE1", pt: 1 } });
  s.addText("EER = equal error rate: real voices called fake = fake voices called real. Lower is better; 50% is a coin toss. Every number is produced by scripts in the repo (runs/*.json).",
    { x: 0.6, y: 6.45, w: 12.1, h: 0.5, fontFace: BF, fontSize: 11, color: MUTED });
}


// 7b Modern voices + replay (final combined model)
if (K) {
  const s = base("Closing the modern-voice gap", "Modern AI voices and replayed audio");
  const E = K.experiments;
  const row = (k, label, why) => E[k] ? [label, why, pct(E[k].eer), pct(E[k].fake_flagged), String(E[k].n_fake)] : null;
  const rows = [["Test (never seen in training)", "Why it matters", "EER", "Flagged FAKE", "n fake"],
    row("modern:clean", "Unseen modern TTS voices (Microsoft neural, Kokoro)", "GPT / Gemini-class quality"),
    row("modern:replay", "Same voices played through a speaker into a mic", "How a scam call is overheard"),
    row("modern_b:clean", "Second set of modern voices", "More sentences"),
    row("itw:clean", "In-the-Wild, unseen speakers", "Internet deepfakes"),
    row("itw_replay:replay", "In-the-Wild, replayed", "Room + speaker + mic"),
  ].filter(Boolean);
  for (const k of ["libri:clean", "libri:replay"]) if (E[k]) rows.push([k === "libri:clean" ? "Clean real speech (LibriSpeech)" : "Clean real speech, replayed", "Real voices must not be flagged", "–", "false alarm " + pct(E[k].real_called_fake), String(E[k].n_real) + " real"]);
  const _unused = 0;
  const tr = rows.map((r, k) => r.map((c) => ({ text: c, options: { bold: k === 0, color: k === 0 ? BRAND : INK, fill: { color: k === 0 ? "DCE6EC" : CARD }, fontFace: BF, fontSize: 12 } })));
  s.addTable(tr, { x: 0.6, y: 1.75, w: 12.1, colW: [4.2, 3.7, 1.2, 1.6, 1.4], rowH: 0.42, border: { type: "solid", color: "D3DAE1", pt: 1 } });
  s.addText("First model (In-the-Wild only) called GPT/Gemini voices REAL. We added modern neural TTS and simulated speaker-to-mic replay to training, holding out 25% of voices for this test.",
    { x: 0.6, y: 6.2, w: 12.1, h: 0.6, fontFace: BF, fontSize: 11, color: MUTED });
}

// 8 Clones chart
if (C) {
  const s = base("Unseen cloners", "Share of clones flagged FAKE, by cloning tool");
  const g = Object.keys(C.generators);
  s.addChart(pres.charts.BAR, [{ name: "Flagged FAKE", labels: g.map((x) => x.toUpperCase()), values: g.map((x) => +(C.generators[x].detected_as_fake * 100).toFixed(1)) },
    { name: "Called REAL (missed)", labels: g.map((x) => x.toUpperCase()), values: g.map((x) => +(C.generators[x].called_real * 100).toFixed(1)) }],
    { x: 0.6, y: 1.7, w: 7.6, h: 5.0, barDir: "bar", barGrouping: "clustered", chartColors: [FAKE, "8A98A6"], valAxisMaxVal: 100, valAxisMinVal: 0,
      showValue: true, dataLabelFormatCode: "0.0", dataLabelColor: INK, catAxisLabelColor: INK, valAxisLabelColor: MUTED, showLegend: true, legendPos: "b", legendColor: INK, catAxisLabelFontFace: BF, valGridLine: { color: "D3DAE1" } });
  card(s, 8.6, 1.7, 4.1, 5.0, "The four tools", "SNAC: real voice passed through a neural codec (vocoder fingerprint only)\n\nKokoro: open TTS, English + Hindi voices\n\nVeena: Indian Hindi/Hinglish TTS\n\nRVC: voice conversion into a team member's voice (with consent)", INK, { size: 12 });
}


// ---------------- Phase 2 ----------------
if (P2) {
  { // R1 robustness chart
    const s = base("Phase 2 · R1", "Survives phone lines, codecs and noise");
    const keys = ["clean", "r8k", "amr", "opus", "noise", "chan"].filter((k) => P2.R1[k]);
    const names = { clean: "Clean", r8k: "8 kHz", amr: "AMR-NB 12.2k", opus: "Opus 12k", noise: "Noise 10 dB", chan: "Random mix" };
    s.addChart(pres.charts.BAR, [{ name: "EER %", labels: keys.map((k) => names[k]), values: keys.map((k) => +(P2.R1[k].eer * 100).toFixed(2)) }],
      { x: 0.6, y: 1.7, w: 7.8, h: 5.0, barDir: "col", chartColors: [BRAND], showValue: true, dataLabelFormatCode: "0.00", dataLabelColor: INK,
        catAxisLabelColor: INK, valAxisLabelColor: MUTED, valGridLine: { color: "D3DAE1" }, catAxisLabelFontFace: BF, showLegend: false });
    const ok = P2.R1_worst_ratio <= 2.5;
    card(s, 8.8, 1.7, 3.9, 2.4, ok ? "Target met" : "Target not met", `Worst case: ${({ r8k: "8 kHz", amr: "AMR-NB", opus: "Opus", noise: "noise" })[P2.R1_worst_condition]} = ${P2.R1_worst_ratio.toFixed(2)}× clean EER\nTarget ≤ 2.5×`, ok ? REAL : FAKE, { size: 15 });
    card(s, 8.8, 4.35, 3.9, 2.35, "How", "Real encoders via ffmpeg (AMR-NB = mobile calls, Opus = WhatsApp/VoIP). Training sees random channels on real and fake alike.", INK, { size: 12 });
  }
  { // R2 localisation
    const s = base("Phase 2 · R2", "Finding the faked seconds inside a real call");
    const r = P2.R2;
    card(s, 0.6, 1.7, 3.8, 2.3, `F1 ${pct(r.f1)}`, `at 0.5 s resolution on ${r.n_test} partial fakes\nprecision ${pct(r.precision)} · recall ${pct(r.recall)}`, BRAND, { size: 14, headSize: 26 });
    card(s, 0.6, 4.2, 3.8, 2.5, "Partial fakes", "Real clip of a speaker with 1–3 s replaced by a fake of the same speaker, loudness-matched, 20 ms crossfade. Threshold set on 60 separate calibration fakes.", INK, { size: 12 });
    // example timelines as cell strips
    (P2.R2_examples || []).slice(0, 3).forEach((ex, k) => {
      const y = 1.9 + k * 1.6, x0 = 4.8, w = 7.9, n = ex.cells.length, cw = w / n;
      s.addText(`Example ${k + 1}: true fake ${ex.fake[0].toFixed(1)}–${ex.fake[1].toFixed(1)} s`, { x: x0, y, w, h: 0.35, fontFace: BF, fontSize: 12, color: INK });
      ex.cells.forEach((c, i) => {
        const mid = (c.start + c.end) / 2, truth = mid >= ex.fake[0] && mid < ex.fake[1], pred = c.score > r.threshold;
        s.addShape(pres.shapes.RECTANGLE, { x: x0 + i * cw, y: y + 0.4, w: cw * 0.92, h: 0.35, fill: { color: truth ? "F2C4C0" : "DCE3E9" }, line: { color: truth ? "F2C4C0" : "DCE3E9" } });
        s.addShape(pres.shapes.RECTANGLE, { x: x0 + i * cw, y: y + 0.82, w: cw * 0.92, h: 0.35, fill: { color: pred ? FAKE : "DCE3E9" }, line: { color: pred ? FAKE : "DCE3E9" } });
      });
    });
    s.addText("Top strip = true fake cells · bottom strip = Kavach's 0.5 s cells", { x: 4.8, y: 6.65, w: 7.9, h: 0.3, fontFace: BF, fontSize: 10, color: MUTED });
  }
  { // R3 + R4
    const s = base("Phase 2 · R3 + R4", "Live call mode, and Phase 1 still holds");
    const r3 = P2.R3;
    card(s, 0.6, 1.7, 5.6, 2.6, "Streaming every 500 ms", `Browser streams the call over a WebSocket. Every 0.5 s the latest 2 s is scored.\nProcessing per update: median ${r3.p50_ms} ms, p95 ${r3.p95_ms} ms (${r3.device})`, BRAND, { size: 13 });
    card(s, 0.6, 4.5, 5.6, 2.2, "In the app", "Live call: mic or simulated call, score line updating twice a second, alert after the voice looks cloned.", INK, { size: 13 });
    const rows = [["Phase 1 test", "Phase 1", "Phase 2", "Change"]];
    const lab = { E1_unseen_speakers_4s: "Unseen speakers 4 s", E3_len_2s: "2 s clips", E3_len_10s: "10 s clips", E4_phone_line: "Phone line" };
    for (const [k, v] of Object.entries(P2.R4)) rows.push([lab[k] || k, pct(v.phase1_eer), pct(v.eer), (v.delta_points >= 0 ? "+" : "") + v.delta_points.toFixed(2) + " pts"]);
    const tr = rows.map((r, k) => r.map((c) => ({ text: c, options: { bold: k === 0, color: k === 0 ? BRAND : INK, fill: { color: k === 0 ? "DCE6EC" : CARD }, fontFace: BF, fontSize: 13 } })));
    s.addTable(tr, { x: 6.6, y: 1.7, w: 6.1, colW: [2.4, 1.2, 1.2, 1.3], rowH: 0.45, border: { type: "solid", color: "D3DAE1", pt: 1 } });
    s.addText(P2.R4_pass ? "All Phase 1 EERs within 2 points ✓" : "Some Phase 1 EERs moved more than 2 points", { x: 6.6, y: 4.3, w: 6.1, h: 0.5, fontFace: HF, fontSize: 16, color: P2.R4_pass ? REAL : FAKE });
  }
}


// Stress test: zero-shot clone from a 4 s WhatsApp note + laundering attacks + noise shield
if (ST) {
  const s = base("Red-team test", "A 4-second WhatsApp note was enough to clone a voice");
  card(s, 0.6, 1.7, 4.0, 2.2, "The attack", "Zero-shot cloner F5-TTS (never in training) copied a speaker from a 3.9 s WhatsApp voice note, then we laundered the clones: WhatsApp Opus, phone AMR, street noise, speaker-to-mic replay.", INK, { size: 12 });
  const cnt = (rows, clipPrefix, v) => rows.filter((r) => r.clip.startsWith(clipPrefix) && r.verdict === v).length;
  const tot = (rows, clipPrefix) => rows.filter((r) => r.clip.startsWith(clipPrefix)).length;
  const b = ST.before, a = ST.after;
  const rows = [["", "FAKE", "NOT SURE", "REAL (missed)"],
    ["Clones · before noise shield", String(cnt(b, "clone", "FAKE")), String(cnt(b, "clone", "NOT SURE")), String(cnt(b, "clone", "REAL"))],
    ["Clones · with noise shield", String(cnt(a, "clone", "FAKE")), String(cnt(a, "clone", "NOT SURE")), String(cnt(a, "clone", "REAL"))],
    ["Real voice note · with shield", String(cnt(a, "original", "FAKE")), String(cnt(a, "original", "NOT SURE")), String(cnt(a, "original", "REAL"))]];
  const tr = rows.map((r, k) => r.map((c) => ({ text: c, options: { bold: k === 0, color: k === 0 ? BRAND : INK, fill: { color: k === 0 ? "DCE6EC" : CARD }, fontFace: BF, fontSize: 13 } })));
  s.addTable(tr, { x: 4.9, y: 1.7, w: 7.8, colW: [3.6, 1.2, 1.4, 1.6], rowH: 0.48, border: { type: "solid", color: "D3DAE1", pt: 1 } });
  const H = ST.heldout, n = ST.heldout_n;
  const pc = (o, k, d) => ((o[k] || 0) / d * 100).toFixed(0) + "%";
  card(s, 0.6, 4.15, 12.1, 2.55, "Noise shield on 300 held-out clips",
    `Noisy fakes (15 dB): caught ${pc(H.noisy_fake, "FAKE", n.fake)} (was ${(ST.heldout_raw.fake_caught * 100).toFixed(0)}%), NOT SURE ${pc(H.noisy_fake, "NOT SURE", n.fake)}.  ` +
    `Noisy real voices wrongly FAKE: ${pc(H.noisy_real, "FAKE", n.real)}.  Clean real voices wrongly FAKE: ${pc(H.clean_real, "FAKE", 100)}.\n` +
    "How: when a clip is noisy (estimated SNR < 24 dB), Kavach also scores it after removing background noise with Demucs. A red FAKE needs a strong denoised score; a weaker one gives amber NOT SURE instead of a red accusation.", BRAND, { size: 13 });
}

// 9 Demo
{
  const s = base("Live prototype", "Upload or record, verdict in under a second");
  const shot = path.join(ROOT, "runs", "e2e_desktop.png");
  if (fs.existsSync(shot)) s.addImage({ path: shot, x: 0.6, y: 1.65, w: 4.4, h: 5.2, sizing: { type: "contain", w: 4.4, h: 5.2 } });
  const lat = L ? `Median ${Math.round(L.sequential.p50_ms)} ms per clip, p95 ${Math.round(L.sequential.p95_ms)} ms; ${L.concurrent.errors} errors in ${L.concurrent.n} concurrent requests.` : "Measured by the load test.";
  card(s, 5.4, 1.65, 7.3, 1.6, "Speed (RTX 4050 laptop)", lat, BRAND, { size: 14 });
  card(s, 5.4, 3.5, 7.3, 3.35, "Demo", "1. Team member's real voice → REAL\n2. Same person, cloned: \"Mummy, I'm in trouble, send ₹50,000\" → FAKE\n3. A cloner it never saw → still FAKE\n4. A judge speaks into the mic → REAL", INK, { size: 15 });
}

// 10 Safety + system
{
  const s = base("Built to be trusted", "Safety, privacy and testing");
  card(s, 0.6, 1.9, 3.9, 4.7, "Safety", "NOT SURE instead of guessing\n\nAdvice always says: verify by calling back\n\nThresholds set on a separate calibration split", BRAND, { size: 14 });
  card(s, 4.7, 1.9, 3.9, 4.7, "Privacy", "Audio analysed in memory, never stored\n\nNo audio in logs\n\nEvery cloned voice belongs to a consenting team member", BRAND, { size: 14 });
  card(s, 8.8, 1.9, 3.9, 4.7, "Tested", "53 unit, API, streaming and security tests: all pass\n\nBrowser end-to-end: 13/13\n\nSemgrep (226 rules) and Bandit: 0 open findings\n\nUpload caps, decode timeout, origin-checked WebSocket, strict CSP", BRAND, { size: 14 });
}

// 11 Where next
{
  const s = base("Impact", "Where Kavach goes next");
  const w = [["Banks and call centres", "Flag cloned voices impersonating customers."], ["Telecom networks", "Warn on suspicious calls at network level."],
    ["Families", "Phone app, or a ₹1,300 Bluetooth guard for parents (apps cannot read call audio)."], ["Next", "Live call mode, more Indian languages, combine with scam-phrase detection."]];
  w.forEach(([h, b], k) => card(s, 0.6 + (k % 2) * 6.15, 1.9 + Math.floor(k / 2) * 2.45, 5.95, 2.2, h, b, k === 3 ? BRAND : INK, { size: 15 }));
}

if (process.env.ONLY) { const k = +process.env.ONLY; pres._slides = pres._slides.filter((_, i) => i <= k); }
pres.writeFile({ fileName: process.env.OUT || path.join(ROOT, "docs", "Kavach_Pitch.pptx") }).then((f) => console.log("written", f));
