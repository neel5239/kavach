// Builds D:\kavach\docs\Kavach_Project_Document.docx
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, LevelFormat, PageBreak, TableOfContents, Footer, PageNumber,
} = require("docx");

const ACC = "0F6B58", MUTED = "5A6B66", LINE = "D5DFDB", HEAD = "E1F0EB";
const FONT = "Calibri";
const W = 9026; // A4 text width in DXA at 1" margins

const p = (text, opts = {}) => new Paragraph({
  spacing: { after: 120, line: 300 }, ...opts.para,
  children: (Array.isArray(text) ? text : [text]).map(t => typeof t === "string" ? new TextRun({ text: t, ...opts.run }) : t),
});
const b = (t) => new TextRun({ text: t, bold: true });
const i = (t) => new TextRun({ text: t, italics: true });
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, spacing: { after: 160 }, children: [new TextRun(t)] });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun(t)] });
const bullet = (parts, level = 0) => new Paragraph({ numbering: { reference: "bul", level }, spacing: { after: 60, line: 280 },
  children: (Array.isArray(parts) ? parts : [parts]).map(t => typeof t === "string" ? new TextRun(t) : t) });
const num = (parts, ref = "num") => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 280 },
  children: (Array.isArray(parts) ? parts : [parts]).map(t => typeof t === "string" ? new TextRun(t) : t) });
const mono = (lines) => lines.map(l => new Paragraph({ spacing: { after: 0, line: 260 }, shading: { type: ShadingType.CLEAR, fill: "F3F6F5", color: "auto" },
  children: [new TextRun({ text: l || " ", font: "Consolas", size: 18 })] }));

function table(headers, rows, widths) {
  const border = { style: BorderStyle.SINGLE, size: 4, color: LINE };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (txt, w, head) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: head ? { type: ShadingType.CLEAR, fill: HEAD, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ spacing: { after: 0, line: 260 }, children: [new TextRun({ text: txt, bold: head, size: 20, color: head ? ACC : undefined })] })],
  });
  return new Table({
    width: { size: widths.reduce((a, c) => a + c, 0), type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, k) => cell(h, widths[k], true)) }),
      ...rows.map(r => new TableRow({ children: r.map((c, k) => cell(c, widths[k], false)) }))],
  });
}
const gap = () => new Paragraph({ spacing: { after: 120 }, children: [] });

const path = require("path");
const ROOTD = path.resolve(__dirname, "..");
const rdj = (p) => { try { return JSON.parse(fs.readFileSync(path.join(ROOTD, p), "utf8")); } catch { return null; } };
const ST = rdj("runs/stress_test.json");
const RB = rdj("runs/itw/results.json"), RK = rdj("runs/kavach/results.json"), RP = rdj("runs/phase2/results.json"), RC = rdj("runs/kavach/clones.json"), RL = rdj("runs/load_test.json");
const P = (x) => (x == null ? "–" : (x * 100).toFixed(2) + "%");
const children = [];
// ---------- Cover ----------
children.push(
  new Paragraph({ spacing: { before: 2400, after: 120 }, children: [new TextRun({ text: "HYPNEXIS'26  ·  TRACK 01  ·  AI-01", color: ACC, bold: true, size: 20 })] }),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Kavach", bold: true, size: 72 })] }),
  new Paragraph({ spacing: { after: 360 }, children: [new TextRun({ text: "Catching AI-cloned voices before the money moves", size: 32, color: MUTED })] }),
  p("Project document: problem, solution, system design, data, evaluation, prototype, testing and demo plan."),
  p([b("Problem statement: "), "AI-01 Voice-Clone Detection for Phone Scams"]),
  p([b("Event: "), "HYPNEXIS'26, 24–25 October 2026"]),
  p([b("Round 1 submission: "), "PPT, prototype and presentation by 3:00 AM, 25 October"]),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: "Contents", bold: true, size: 34, color: ACC })] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
);

// ---------- 1 Summary ----------
children.push(h1("1. Executive summary"),
  p("Scammers can now copy anyone's voice from a few seconds of audio taken from a reel, a WhatsApp voice note or a short call. They then phone a parent or a bank customer in that voice and ask for money. People trust a familiar voice, so the scam works."),
  p([b("Kavach"), " is a detector that listens to a 2–10 second speech clip and returns one of three verdicts: ", b("REAL"), ", ", b("NOT SURE"), " or ", b("FAKE (AI clone)"), ", together with a confidence score and a timeline showing which seconds looked synthetic."]),
  p([b("The central challenge"), " is generalisation. A detector trained on known cloning tools tends to learn their specific quirks and fails on new ones. Detectors trained on public benchmarks also learn shortcuts such as silence length or loudness, which do not exist in real calls."]),
  p([b("Our approach"), " rests on one idea: every cloning tool, old or new, must finish by turning its internal representation into a waveform through a vocoder or neural codec. That step leaves fine fingerprints. We detect those fingerprints with XLS-R, a speech model pretrained on 436,000 hours of real speech in 128 languages, kept frozen, with a small classifier on top. We remove shortcuts by design (silence trimming, loudness normalisation, phone-line simulation) and prove generalisation by testing on speakers and cloning tools the model never saw in training."]),
  p([b("The prototype"), " is a minimal, neumorphic web app: upload a clip or record from the microphone, and see the verdict, score and suspicious-seconds timeline. A FastAPI backend serves the model. The whole system is covered by unit, integration, end-to-end, security and load tests."]),
);

// ---------- 2 Problem ----------
children.push(h1("2. The problem"),
  h2("2.1 Problem statement (as given)"),
  p(i("Scammers can clone the voice of a relative or bank officer from just a few seconds of audio. Build a detector that decides whether a 2–10 second speech clip is genuine or synthetic, and keeps working on voice-cloning tools never seen during training.")),
  p("Pretrained self-supervised speech models are allowed. The ASVspoof 2019 evaluation set and the In-the-Wild dataset are suggested for testing generalisation."),
  h2("2.2 Why it matters"),
  bullet("Voice cloning has become cheap, fast and open-source. A convincing clone needs only seconds of reference audio."),
  bullet("The victims are often elderly parents, who are least able to verify a caller by other means."),
  bullet("The money usually moves through instant payments, so there is little time to reverse it."),
  bullet("Phones and messaging apps today give no signal that a voice might be synthetic."),
  h2("2.3 Key challenges and our answer to each"),
  table(["Challenge (from the PS)", "Why it is hard", "Kavach's answer"], [
    ["Generalising to unseen voice generators", "Models memorise the artifacts of the tools in their training set", "Frozen speech model that knows real speech deeply; tested on 4 generators never used in training"],
    ["Short clips with limited evidence", "2 seconds carries little information", "Sliding-window scoring with aggregation; an explicit NOT SURE zone instead of guessing"],
    ["Different languages and speakers", "Training data is mostly English", "XLS-R base pretrained on 128 languages; our own Hindi / Gujarati / English test set; train and test speakers never overlap"],
    ["Misleading shortcuts (silence, loudness)", "Benchmarks leak labels through silence length and level", "Silence trimming and loudness normalisation on every clip; a shortcut test that proves the model does not use them"],
  ], [2400, 3000, 3626]),
);

// ---------- 3 Solution ----------
children.push(h1("3. Our solution"),
  h2("3.1 The core insight"),
  p([b("Every cloner ends in a vocoder. "), "A cloning system first decides what to say and in whose voice, then a vocoder or neural codec renders that into sound. Vocoders are good enough to fool ears but leave consistent traces: unnatural fine structure in high frequencies, overly smooth micro-variation, phase patterns that real vocal tracts do not produce, and missing natural micro-noise. New cloners change the front end often, but the rendering step is shared by all of them."]),
  h2("3.2 Why a frozen pretrained model"),
  p("XLS-R has heard a vast amount of real human speech. Its internal layers already encode what real speech looks like, at many levels from raw acoustics to phonetics. We read all 24 of its transformer layers, learn which layers carry the strongest fake-detection signal, and train only a small classifier on top."),
  bullet([b("Generalisation: "), "a frozen model cannot overfit its representation to one cloner's artifacts."]),
  bullet([b("Feasibility: "), "fits a 6 GB laptop GPU; features are computed once and cached, so each retraining takes minutes."]),
  bullet([b("Multilingual: "), "pretraining covered 128 languages, including Hindi and Gujarati."]),
  h2("3.3 Removing shortcuts by design"),
  num([b("Silence trimming: "), "leading and trailing silence removed with an energy threshold, so silence length carries no information."]),
  num([b("Loudness normalisation: "), "every clip scaled to the same RMS level, so loudness carries no information."]),
  num([b("Phone-line simulation: "), "random down-sampling to 8 kHz and back, band-pass to the telephone band, light noise, so the model is robust to call audio."]),
  num([b("Shortcut test: "), "a classifier trained only on silence duration and loudness is measured on the same data. If it performs well, the data leaks; we report it and show that our model's score does not depend on these features."]),
  h2("3.4 Three-way verdict"),
  table(["Verdict", "Meaning", "What the user sees"], [
    ["REAL", "Score below the lower threshold", "Green. \"This sounds like a real person.\""],
    ["NOT SURE", "Score between the thresholds, or clip too short after trimming", "Amber. \"Can't be sure. Verify another way.\""],
    ["FAKE", "Score above the upper threshold", "Red. \"Likely AI-cloned. Hang up and call back on a saved number.\""],
  ], [1600, 3400, 4026]),
  p("Thresholds are set on a held-out calibration split, not on test data."),
);

// ---------- 4 Architecture ----------
children.push(h1("4. System architecture"),
  h2("4.1 Components"),
  table(["Component", "Technology", "Responsibility"], [
    ["Web app", "Plain HTML/CSS/JS, minimal neumorphic UI", "Upload or record audio, show verdict, score, timeline, history of this session"],
    ["API server", "Python, FastAPI, Uvicorn", "Validate input, decode audio, run the detector, return JSON"],
    ["Audio front end", "ffmpeg, NumPy", "Decode any common format to 16 kHz mono, trim silence, normalise loudness"],
    ["Feature extractor", "XLS-R 300M (frozen), PyTorch, CUDA when available", "Hidden states of all layers, pooled per window"],
    ["Classifier", "Learned layer weights + logistic regression / small MLP", "Score each window; aggregate to a clip score"],
    ["Calibration", "Thresholds from a calibration split", "Map score to REAL / NOT SURE / FAKE"],
    ["Training pipeline", "Python scripts", "Index data, extract and cache features, train, evaluate, export model"],
  ], [1900, 3000, 4126]),
  h2("4.2 Request flow"),
  ...mono([
    "Browser ──(multipart audio, ≤ 10 MB)──► POST /api/analyze",
    "   1. size and type check           reject early, 413 / 415",
    "   2. ffmpeg decode → 16 kHz mono   reject undecodable, 422",
    "   3. trim silence, normalise",
    "   4. windows of 4 s, hop 1 s       (one window if clip shorter)",
    "   5. XLS-R layers → pooled vectors",
    "   6. classifier → window scores → clip score",
    "   7. thresholds → verdict",
    "◄── JSON { verdict, score, duration, windows[], model, latency_ms }",
    "   audio buffer discarded; nothing written to disk",
  ]),
  gap(),
  h2("4.3 API contract"),
  table(["Endpoint", "Input", "Output"], [
    ["GET /api/health", "none", "{ status, model_loaded, device }"],
    ["POST /api/analyze", "multipart field \"file\": wav, flac, mp3, m4a, ogg, webm; max 10 MB; 1–30 s", "{ verdict, score (0–1), confidence, duration_s, speech_s, windows: [{start, end, score}], thresholds, latency_ms }"],
    ["GET /", "none", "the web app"],
  ], [2100, 3600, 3326]),
);

// ---------- 5 Data ----------
children.push(h1("5. Data"),
  h2("5.1 Datasets"),
  table(["Dataset", "Content", "Role"], [
    ["In-the-Wild (Müller et al., Interspeech 2022)", "Real and deepfake speech of 58 public figures collected online, 37.9 h, English, Apache-2.0", "Main training and testing, split by speaker so test speakers are never heard in training"],
    ["Kavach-Indic (ours)", "Team members reading Hindi, Gujarati and English sentences, recorded on phones, with consent", "Real side of our own test set"],
    ["Kavach-Clones (ours)", "Clones and synthetic speech made with local tools: Kokoro TTS, Veena Hindi TTS, SNAC neural-codec re-synthesis, RVC voice conversion", "Fake side of our own test set; every generator is unseen in training"],
  ], [2500, 3500, 3026]),
  h2("5.2 Why not ASVspoof 2019"),
  p("ASVspoof 2019 LA was the first choice, but its host server delivered 53 KB/s at the venue, which would take about 38 hours for 7 GB. In-the-Wild is the harder, real-world benchmark the PS also names, and our own modern cloners add generators released after 2019."),
  h2("5.3 Splits"),
  bullet([b("Speaker-disjoint: "), "speakers are assigned to train (≈70%), calibration (≈10%) and test (≈20%). No speaker appears in two splits."]),
  bullet([b("Unseen generators: "), "the detector is trained only on In-the-Wild. Every one of our own generators (SNAC, Kokoro, Veena, RVC) is used only for testing, so each is a cloner the model has never seen."]),
  bullet([b("Clip length: "), "evaluation clips are cut to 2–10 s to match the PS."]),
  h2("5.4 Ethics and consent"),
  bullet("Every voice we clone belongs to a team member who agreed to it."),
  bullet("Clones are used only for testing and the demo, and are deleted after the event."),
  bullet("The API keeps audio in memory only and writes nothing to disk."),
);

// ---------- 6 Evaluation ----------
children.push(h1("6. Evaluation"),
  h2("6.1 Metric: Equal Error Rate (EER)"),
  p("Set the decision threshold so that the share of real voices wrongly called fake equals the share of fake voices wrongly called real. That shared percentage is the EER. Lower is better: 0% is perfect, 50% is a coin toss. We also report accuracy of the three-way verdict and the share of NOT SURE answers."),
  h2("6.2 Experiments"),
  table(["#", "Experiment", "Question it answers"], [
    ["E1", "Baseline on unseen speakers (In-the-Wild test split)", "Does it work on people it never heard?"],
    ["E2", "Shortcut test: silence + loudness only classifier", "Does the data leak labels? Does our model rely on it?"],
    ["E3", "Clip length 2 s / 4 s / 10 s", "How much audio does it need?"],
    ["E4", "Phone-quality audio (8 kHz telephone band)", "Does it survive a phone line?"],
    ["E5", "Each of our 4 generators, never seen in training", "Does it catch a cloner it never saw?"],
    ["E6", "Hindi / Gujarati subset", "Does it work across languages?"],
  ], [700, 4300, 4026]),
  p([b("Reporting rule: "), "every number in the presentation is produced by a script in the repository and stored in runs/. No number is typed in by hand. Weak results are shown with their reason."]),
);

// ---------- 7 Prototype / UX ----------
children.push(h1("7. Prototype and user experience"),
  h2("7.1 Design direction: minimal neumorphism"),
  bullet("A single soft surface colour; controls appear pressed into or raised from it using paired light and dark shadows."),
  bullet("One accent colour per verdict: green REAL, amber NOT SURE, red FAKE. Nothing else competes for attention."),
  bullet("Large central verdict dial, readable from across a room during the demo."),
  bullet("Neumorphism has known contrast problems, so all text keeps a contrast ratio of at least 4.5:1 and focus states are clearly visible."),
  bullet("Light and dark themes, phone and desktop layouts."),
  h2("7.2 Screens and states"),
  table(["State", "What the user sees"], [
    ["Idle", "Title, short line on what Kavach does, two raised buttons: Upload clip, Record. Drop zone."],
    ["Recording", "Record button pressed in, live level meter, timer counting to 10 s, Stop."],
    ["Analysing", "Dial gently pulses; \"Listening for clone fingerprints…\""],
    ["Result", "Dial fills to the score in the verdict colour, verdict word, confidence, advice line, waveform timeline with suspicious seconds shaded."],
    ["Error", "Plain message saying what went wrong and how to fix it (too long, unsupported format, no speech found)."],
    ["History", "Small list of this session's checks with verdict chips; cleared on reload."],
  ], [1800, 7226]),
);

// ---------- 8 System design ----------
children.push(h1("8. System design considerations"),
  h2("8.1 Latency budget (target, single clip of 10 s)"),
  table(["Stage", "Target"], [
    ["Upload + decode", "< 300 ms"], ["Pre-processing", "< 50 ms"], ["XLS-R features (GPU)", "< 400 ms"], ["Classifier + verdict", "< 10 ms"], ["Total server time", "< 1 s"],
  ], [5000, 4026]),
  p("Measured values are reported by the load test; these are targets, not results."),
  h2("8.2 Scaling path"),
  bullet("The API is stateless: any number of replicas behind a load balancer."),
  bullet("Model loads once per process; requests share it under a lock or a small batching queue."),
  bullet("CPU-only deployment possible by exporting to ONNX and using a smaller backbone for low-cost tiers."),
  bullet("For telecom-scale use, scoring moves to streaming windows with a running verdict."),
  h2("8.3 Security and privacy design"),
  table(["Threat", "Control"], [
    ["Huge uploads / resource exhaustion", "10 MB request cap, 30 s duration cap, decode timeout, one inference at a time per worker"],
    ["Malformed or malicious media files", "Decoding in a separate ffmpeg process with fixed arguments, no shell, timeout; output format forced to raw PCM"],
    ["Path traversal / filename injection", "Uploaded filename never used on disk; audio handled as bytes in memory"],
    ["Cross-site abuse", "CORS limited to the app origin; no cookies or sessions"],
    ["Data leakage", "No audio stored, no audio in logs; logs carry only duration, verdict and latency"],
    ["Dependency vulnerabilities", "pip-audit on requirements; Semgrep and Bandit static analysis"],
    ["Misuse of the verdict", "NOT SURE zone; UI advice says to verify by calling back, never to trust the score alone"],
  ], [3200, 5826]),
);

// ---------- 9 Testing ----------
children.push(h1("9. Testing plan"),
  table(["Layer", "What we test", "Tool"], [
    ["Unit", "Silence trim, normalisation, windowing, score aggregation, threshold mapping, EER function", "pytest"],
    ["Model sanity", "Known real clip scores lower than known fake clip; output is deterministic for the same input", "pytest"],
    ["API integration", "Health endpoint, valid upload, each error code (413, 415, 422), JSON schema of the response", "pytest + FastAPI TestClient"],
    ["End to end", "Browser opens app, uploads a clip, sees a verdict; record flow with a fake microphone stream", "Playwright"],
    ["Security", "Oversized file, wrong type, corrupted file, zero-length file, file with a path-like name; static analysis; dependency audit", "pytest, Semgrep, Bandit, pip-audit"],
    ["Load / system", "Latency p50 / p95 per request, behaviour under concurrent requests, memory stays flat across many requests", "Python load script"],
    ["Accessibility", "Contrast, keyboard navigation, focus visibility, labels", "Manual + automated checks"],
  ], [1700, 4800, 2526]),
  p([b("Pass criteria: "), "all tests green, no high-severity static-analysis findings, no known-vulnerable dependencies, p95 latency within budget on the demo laptop."]),
);

// ---------- 10 Demo ----------
children.push(h1("10. Demo plan"),
  num([b("Hook: "), "\"Scammers need just a few seconds of your voice.\" Play a teammate's real recording. Kavach shows green REAL."], "demo"),
  num([b("The scam: "), "play the same teammate's cloned voice saying \"Mummy, I'm in trouble, send ₹50,000\"."], "demo"),
  num([b("Caught: "), "Kavach turns red FAKE, suspicious seconds highlighted."], "demo"),
  num([b("Unseen tool: "), "play a clone from a generator the model never trained on. Still red."], "demo"),
  num([b("Live: "), "a judge speaks into the microphone. Green REAL."], "demo"),
  num([b("Proof: "), "results slide: unseen speakers, unseen generator, Hindi, phone audio."], "demo"),
  p("A screen recording of the full demo is kept as a backup in case anything fails live."),
);

// ---------- 11 Risks ----------
children.push(h1("11. Risks and limitations"),
  table(["Risk / limitation", "Mitigation"], [
    ["No detector is perfect, especially on very short clips", "NOT SURE zone; we report errors honestly"],
    ["In-the-Wild is English only", "Our own Hindi and Gujarati test set"],
    ["Our own clone set is small", "Reported as a stress test, not as a benchmark"],
    ["Heavy noise or deliberate attacks can lower accuracy", "Phone-line simulation helps; adversarial robustness is future work"],
    ["Venue internet", "Datasets and model weights downloaded early; demo runs fully offline"],
  ], [4200, 4826]),
);

// ---------- 12 Roadmap ----------
children.push(h1("12. Impact and roadmap"),
  h2("12.1 Who would use it"),
  bullet([b("Banks and call centres: "), "flag cloned voices impersonating customers."]),
  bullet([b("Telecom operators: "), "network-level warning on suspicious calls."]),
  bullet([b("Families: "), "a phone app, or a small Bluetooth guard device for parents, since phone apps cannot read call audio directly."]),
  h2("12.2 Next steps"),
  bullet("Live call mode with streaming windows."),
  bullet("Larger multilingual training set covering more Indian languages."),
  bullet("Combining voice score with scam-language detection (urgency, money requests)."),
  bullet("Partial fine-tuning of the top XLS-R layers on a larger GPU."),
);

// ---------- 13 Timeline ----------
children.push(h1("13. Build timeline (24–25 October)"),
  table(["Time", "Phase", "Output"], [
    ["15:00–16:00", "P0 Setup", "Environment, model weights, dataset indexed"],
    ["16:00–17:30", "P1 Baseline", "Cached features, first classifier, first EER"],
    ["18:15–20:15", "P2 Generalisation", "Shortcut test, phone test, own clones, held-out generator table"],
    ["21:30–23:30", "P3 Prototype", "API + neumorphic web app working end to end"],
    ["23:30–01:00", "P4 Testing + numbers", "All test suites green, results into slides"],
    ["01:00–02:45", "P5 Rehearsal + submit", "Two timed rehearsals, backup video, submission"],
  ], [1800, 2600, 4626]),
);

// ---------- 14 References ----------
children.push(h1("14. References"),
  bullet("Müller, N. et al. (2022). Does Audio Deepfake Detection Generalize? Interspeech 2022. (In-the-Wild dataset)"),
  bullet("Müller, N. et al. (2021). Speech is Silver, Silence is Golden: What do ASVspoof-trained Models Really Learn? ASVspoof 2021 Workshop."),
  bullet("Babu, A. et al. (2022). XLS-R: Self-supervised Cross-lingual Speech Representation Learning at Scale. Interspeech 2022."),
  bullet("Wang, X. & Yamagishi, J. (2023). Spoofed training data for speech spoofing countermeasure can be efficiently created using neural vocoders. ICASSP 2023."),
  bullet("Wang, X. et al. (2020). ASVspoof 2019: A large-scale public database of synthesized, converted and replayed speech. Computer Speech & Language."),
);


// ---------- 15 Results (generated from runs/*.json) ----------
children.push(h1("15. Results"),
  p([i("Every number below is read from the result files produced by the scripts in this repository (runs/*.json). Nothing is typed by hand.")]));
if (RB) children.push(h2("15.1 Phase 1 model (In-the-Wild only)"),
  table(["Test (unseen speakers)", "EER", "n"], Object.entries(RB.experiments).filter(([k, v]) => v && v.eer != null && v.n).map(([k, v]) => [k.replace(/_/g, " "), P(v.eer), String(v.n)]), [5200, 1900, 1926]),
  p(`Shortcut-only classifier (duration, silence, loudness): EER ${P(RB.experiments.E2_shortcut_only_classifier.eer)}. Near 50% means the data does not leak the label through silence or loudness.`));
if (RK) children.push(h2("15.2 Final model (Phase 2): every test condition"),
  p("Trained on In-the-Wild (clean, phone-line, channel-augmented, replayed, noisy), modern neural TTS voices and clean real speech (LibriSpeech). About 25% of the modern TTS voices and all test speakers are never seen in training."),
  table(["Condition", "EER", "Fakes flagged", "False alarms on real"], Object.entries(RK.experiments).filter(([k]) => k !== "shortcut_only_classifier").map(([k, v]) =>
    [k, v.eer != null ? P(v.eer) : "–", v.fake_flagged != null ? P(v.fake_flagged) : "–", v.real_called_fake != null ? P(v.real_called_fake) : "–"]), [3600, 1700, 1800, 1926]));
if (RP) children.push(h2("15.3 Phase 2 requirements"),
  table(["Requirement", "Result", "Target", "Status"], [
    ["R1 channel robustness", `worst ${RP.R1_worst_condition}: ${RP.R1_worst_ratio.toFixed(2)}× clean (${Object.entries(RP.R1).map(([k, v]) => k + " " + P(v.eer)).join(", ")})`, "≤ 2.5×", RP.R1_worst_ratio <= 2.5 ? "Met" : "Not met"],
    ["R2 partial-fake localisation", `F1 ${P(RP.R2.f1)} (P ${P(RP.R2.precision)}, R ${P(RP.R2.recall)}) on ${RP.R2.n_test} partial fakes`, "report F1 at 0.5 s", "Reported"],
    ["R3 streaming", `update every ${RP.R3.interval_ms} ms; p50 ${RP.R3.p50_ms} ms, p95 ${RP.R3.p95_ms} ms per update (${RP.R3.device})`, "500 ms updates", RP.R3.pass ? "Met" : "Not met"],
    ["R4 Phase 1 guard", Object.entries(RP.R4).map(([k, v]) => k.split("_").slice(1).join(" ") + " " + (v.delta_points >= 0 ? "+" : "") + v.delta_points.toFixed(2) + " pts").join("; "), "within 2 pts", RP.R4_pass ? "Met" : "Not met"],
  ], [2000, 4300, 1300, 1426]));
if (RC) children.push(h2("15.4 Our own cloners (never in training)"),
  table(["Generator", "n", "EER vs real", "Phone-line EER", "Flagged FAKE"], Object.entries(RC.generators).map(([g, v]) => [g.toUpperCase(), String(v.n), P(v.eer_vs_itw_real), P(v.eer_phone_line), P(v.detected_as_fake)]), [1800, 1000, 2000, 2100, 2126]));
if (RL) children.push(h2("15.5 Load test"),
  p(`Sequential: median ${Math.round(RL.sequential.p50_ms)} ms, p95 ${Math.round(RL.sequential.p95_ms)} ms per request. Concurrent (${RL.concurrent.workers} workers, ${RL.concurrent.n} requests): median ${Math.round(RL.concurrent.p50_ms)} ms, ${RL.concurrent.errors} errors, ${RL.concurrent.throughput_rps.toFixed(1)} requests/s.`));

if (ST) {
  const cnt = (rows, pre, v) => String(rows.filter((r) => r.clip.startsWith(pre) && r.verdict === v).length);
  const H = ST.heldout, n = ST.heldout_n, pc = (o, k, d) => P((o[k] || 0) / d);
  children.push(h2("15.7 Red-team test: zero-shot clone from a WhatsApp note"),
    p("A speaker was cloned with F5-TTS, a zero-shot cloner never used in training, from a 3.9-second WhatsApp voice note. Three high-quality clones (NFE 64, denoised reference) were then laundered six ways each: as-is, WhatsApp Opus, phone AMR-NB, street noise 15 dB, speaker-to-mic replay, Opus + noise."),
    table(["", "FAKE", "NOT SURE", "REAL (missed)"], [
      ["Clones, before noise shield", cnt(ST.before, "clone", "FAKE"), cnt(ST.before, "clone", "NOT SURE"), cnt(ST.before, "clone", "REAL")],
      ["Clones, with noise shield", cnt(ST.after, "clone", "FAKE"), cnt(ST.after, "clone", "NOT SURE"), cnt(ST.after, "clone", "REAL")],
      ["Real voice note, with noise shield", cnt(ST.after, "original", "FAKE"), cnt(ST.after, "original", "NOT SURE"), cnt(ST.after, "original", "REAL")]], [4200, 1500, 1600, 1726]),
    p("Finding: background noise hid the clone fingerprint. The noise shield fixes most of this: when the estimated SNR is below 24 dB, the clip is also scored after Demucs vocal isolation. A red FAKE needs a denoised score above 0.90; a weaker signal gives NOT SURE."),
    table(["Held-out set (shield on, through the app)", "Result"], [
      [`Noisy fakes, 15 dB (n=${n.fake})`, `FAKE ${pc(H.noisy_fake, "FAKE", n.fake)}, NOT SURE ${pc(H.noisy_fake, "NOT SURE", n.fake)}, missed ${pc(H.noisy_fake, "REAL", n.fake)} (without shield: caught ${P(ST.heldout_raw.fake_caught)})`],
      [`Noisy real voices, 15 dB (n=${n.real})`, `REAL ${pc(H.noisy_real, "REAL", n.real)}, NOT SURE ${pc(H.noisy_real, "NOT SURE", n.real)}, wrongly FAKE ${pc(H.noisy_real, "FAKE", n.real)}`],
      ["Clean real voices (n=100)", `REAL ${pc(H.clean_real, "REAL", 100)}, wrongly FAKE ${pc(H.clean_real, "FAKE", 100)}`]], [4200, 4826]),
    p([i("The 0.90 cut-off and 24 dB switch were chosen on the 200 noisy validation clips listed in runs/denoise_validation.json; the clean-voice row uses different clips. The Phase 2 R1 numbers in 15.3 are measured without the shield.")]));
}

children.push(h2("15.6 Known limits"),
  bullet("Audio played through a speaker into a microphone (replay) is the hardest case: accuracy drops and some real replayed voices are flagged. The NOT SURE zone and the advice to call back exist for this reason."),
  bullet("Commercial assistants such as GPT and Gemini voice were not available as training data; modern neural TTS voices were used as the closest open substitute."),
  bullet("In-the-Wild is English; Hindi coverage comes from Kokoro and Veena voices and team recordings."));

const doc = new Document({
  creator: "Kavach team", title: "Kavach Project Document",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 34, bold: true, color: ACC, font: FONT }, paragraph: { spacing: { after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
                                 { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1000, hanging: 270 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    { reference: "demo", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "Kavach · HYPNEXIS'26 · page ", color: MUTED, size: 18 }), new TextRun({ children: [PageNumber.CURRENT], color: MUTED, size: 18 })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(__dirname + "/Kavach_Project_Document.docx", buf); console.log("written"); });
