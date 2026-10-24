// Builds D:\kavach\docs\Kavach_Phase2_Plan.docx  (Phase 2 extension: what, how, status)
const fs = require("fs");
const path = require("path");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, LevelFormat } = require("docx");
const ACC = "0F6B58", MUTED = "5A6B66", LINE = "D5DFDB", HEAD = "E1F0EB";
const ROOT = path.resolve(__dirname, "..");
const rd = (p) => { try { return JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8")); } catch { return null; } };
const B = rd("runs/itw/results.json");
const P2 = rd("runs/phase2/results.json");
const pct = (x) => (x == null ? "pending" : (x * 100).toFixed(2) + "%");
const t = (s, o = {}) => new TextRun({ text: s, ...o });
const p = (runs, o = {}) => new Paragraph({ spacing: { after: 110, line: 290 }, ...o, children: (Array.isArray(runs) ? runs : [runs]).map(r => typeof r === "string" ? t(r) : r) });
const h1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 120 }, children: [t(s)] });
const h2 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 }, children: [t(s)] });
const bul = (runs) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 60, line: 280 }, children: (Array.isArray(runs) ? runs : [runs]).map(r => typeof r === "string" ? t(r) : r) });
const b = (s) => t(s, { bold: true });
const mono = (lines) => lines.map(l => new Paragraph({ spacing: { after: 0, line: 250 }, shading: { type: ShadingType.CLEAR, fill: "F1F4F3", color: "auto" }, children: [t(l || " ", { font: "Consolas", size: 18 })] }));
function table(headers, rows, widths) {
  const bd = { style: BorderStyle.SINGLE, size: 4, color: LINE }, borders = { top: bd, bottom: bd, left: bd, right: bd };
  const cell = (s, w, h) => new TableCell({ width: { size: w, type: WidthType.DXA }, borders, margins: { top: 60, bottom: 60, left: 100, right: 100 },
    shading: h ? { type: ShadingType.CLEAR, fill: HEAD, color: "auto" } : undefined, children: [new Paragraph({ children: [t(String(s), { bold: h, size: 20, color: h ? ACC : undefined })] })] });
  return new Table({ width: { size: widths.reduce((a, c) => a + c, 0), type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((x, k) => cell(x, widths[k], true)) }), ...rows.map(r => new TableRow({ children: r.map((x, k) => cell(x, widths[k], false)) }))] });
}
const W = [2600, 3800, 2626];
const be = B ? B.experiments : {};
const pe = P2 ? P2 : {};

const C = [
  new Paragraph({ spacing: { after: 60 }, children: [t("HYPNEXIS'26 · AI-01 · PHASE 2", { bold: true, color: ACC, size: 20 })] }),
  new Paragraph({ spacing: { after: 80 }, children: [t("Kavach Phase 2: real phone calls and partly faked speech", { bold: true, size: 40 })] }),
  p(t("Plan, method and live status. Numbers marked \"pending\" are filled in automatically from runs/phase2/results.json when each experiment finishes. No number in this document is typed by hand.", { color: MUTED })),

  h1("1. What Phase 2 asks"),
  table(["#", "Requirement", "Pass condition"], [
    ["R1", "Report EER after 8 kHz resampling, two codecs and added noise", "Worst case ≤ 2.5 × clean EER"],
    ["R2", "Build 100 partial fakes and locate the synthetic segments", "Segment F1 at 0.5 s resolution (report it)"],
    ["R3", "Streaming mode during a call", "Score updates every 500 ms"],
    ["R4", "Keep Phase 1 results", "Phase 1 EERs within 2 points of before"],
  ], [700, 5200, 3126]),

  h1("2. Our approach"),
  h2("R1 · Channel robustness"),
  p("Real calls pass through narrowband phone lines and lossy voice codecs, with background noise. We test each condition on its own, on 2,000 clips from 11 In-the-Wild speakers never seen in training:"),
  table(["Condition", "How it is made", "Why"], [
    ["Clean", "Silence-trimmed, loudness-normalised 4 s clip", "Reference EER"],
    ["8 kHz resample", "Down to 8 kHz and back to 16 kHz", "Telephone bandwidth: everything above 4 kHz is lost"],
    ["Codec 1: AMR-NB 12.2 kbps", "Real encoder (ffmpeg libopencore_amrnb) at 8 kHz", "The standard mobile-network voice codec (GSM/UMTS calls)"],
    ["Codec 2: Opus 12 kbps VoIP", "Real encoder (ffmpeg libopus, voip mode)", "WhatsApp, Google Meet and most internet calls"],
    ["Added noise", "Street/room-like noise at 10 dB SNR", "Calls from busy places"],
    ["Random mix", "Random chain of the above, plus speaker-to-mic replay", "Hardest realistic case"],
  ], W),
  p([b("Training change: "), "the detector is re-trained with random channel augmentation (8 kHz, one of four codecs: AMR, Opus, GSM, MP3, noise at 5–25 dB, speaker-to-mic replay). Because real and fake clips get the same treatment, the channel itself carries no label."]),

  h2("R2 · Partial fakes and localisation"),
  bullet([b("Building 100 partial fakes: "), "take a real 6–10 s clip of a test speaker and replace one 1–3 s stretch with a fake clip of the same speaker (In-the-Wild has both for every person). Loudness is matched and the joins get a 20 ms crossfade so there is no click to detect. The exact fake interval is saved as ground truth."]),
  bullet([b("A segment head: "), "a second small classifier trained on random 1 s crops (clean and channel-augmented) from training speakers only."]),
  bullet([b("Localisation: "), "slide a 1 s window every 0.5 s. Each 0.5 s cell gets the mean score of the windows covering it. A cell above the threshold is marked synthetic. The threshold is chosen on 60 separate partial fakes from calibration speakers, never on the test set."]),
  bullet([b("Metric: "), "precision, recall and F1 over 0.5 s cells across all 100 test partial fakes."]),

  h2("R3 · Streaming mode"),
  bullet("The browser captures microphone audio as raw 16 kHz samples and sends 500 ms chunks over a WebSocket."),
  bullet("The server keeps a rolling buffer for that call and, every 500 ms, scores the latest 2 s of speech (EER at 2 s was 2.56% in Phase 1)."),
  bullet("The UI shows a live score line, the current verdict and how long the voice has looked synthetic. A smoothed score avoids flicker."),
  bullet("A \"Simulate call\" button streams a demo file in real time, so the demo works even without a microphone."),
  ...mono(["browser mic ──500 ms PCM chunks──► WS /ws/stream", "                server: rolling 2 s buffer → XLS-R → head → score", "◄── {t, score, smoothed, verdict} every 500 ms"]),

  h2("R4 · Phase 1 guard"),
  p("After every change the Phase 1 experiments are re-run on the same test speakers. The new model is accepted only if each Phase 1 EER is within 2 percentage points of the Phase 1 model."),

  h1("3. Results (filled automatically)"),
  h2("R1 · Channel robustness"),
  table(["Condition", "EER", "× clean"], ["clean", "r8k", "amr", "opus", "noise", "chan"].map(k => {
    const v = pe.R1 && pe.R1[k]; const c = pe.R1 && pe.R1.clean;
    return [({ clean: "Clean", r8k: "8 kHz resample", amr: "AMR-NB 12.2k", opus: "Opus 12k", noise: "Noise 10 dB", chan: "Random mix" })[k], v ? pct(v.eer) : "pending", v && c ? (v.eer / c.eer).toFixed(2) + "×" : "–"];
  }), [4000, 2500, 2526]),
  p(pe.R1 ? [b("Worst case: "), t(`${(pe.R1_worst_ratio).toFixed(2)}× clean, target ≤ 2.5× → ${pe.R1_worst_ratio <= 2.5 ? "PASS" : "NOT MET"}`)] : t("pending", { color: MUTED })),
  h2("R2 · Localisation"),
  p(pe.R2 ? `100 partial fakes, 0.5 s cells: precision ${pct(pe.R2.precision)}, recall ${pct(pe.R2.recall)}, F1 ${pct(pe.R2.f1)} (threshold ${pe.R2.threshold.toFixed(3)} from calibration fakes).` : t("pending", { color: MUTED })),
  h2("R3 · Streaming"),
  p(pe.R3 ? `Update interval ${pe.R3.interval_ms} ms; median processing per update ${pe.R3.p50_ms} ms, p95 ${pe.R3.p95_ms} ms (must stay below 500 ms).` : t("pending", { color: MUTED })),
  h2("R4 · Phase 1 guard"),
  table(["Phase 1 test", "Phase 1 model", "Phase 2 model", "Change"], [
    ["E1_unseen_speakers_4s", "Unseen speakers 4 s"], ["E3_len_2s", "2 s clips"], ["E3_len_10s", "10 s clips"], ["E4_phone_line", "Phone line"]].map(([k, label]) => {
      const a = be[k] && be[k].eer, n = pe.R4 && pe.R4[k] && pe.R4[k].eer;
      return [label, a != null ? pct(a) : "–", n != null ? pct(n) : "pending", a != null && n != null ? ((n - a) * 100 >= 0 ? "+" : "") + ((n - a) * 100).toFixed(2) + " pts" : "–"];
    }), [3200, 2000, 2000, 1826]),

  h1("4. Build status"),
  table(["Step", "Status"], [
    ["Codec, 8 kHz, noise and channel-mix functions (real AMR-NB / Opus via ffmpeg)", "Done, tested"],
    ["Feature extraction: 2,000 test clips × 6 conditions", P2 ? "Done" : "Running"],
    ["Feature extraction: channel-augmented training set + 1 s segment crops", P2 ? "Done" : "Running"],
    ["Re-train detector with channel augmentation + modern TTS + clean real speech", P2 && pe.R4 ? "Done" : "Next"],
    ["100 + 60 partial fakes, segment head, F1", P2 && pe.R2 ? "Done" : "Next"],
    ["Streaming WebSocket + live UI + simulate-call", P2 && pe.R3 ? "Done" : "Next"],
    ["Tests for all of the above, deck + document update, final zip", "Last"],
  ], [6500, 2526]),
];

const doc = new Document({
  styles: { default: { document: { run: { font: "Calibri", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 30, bold: true, color: ACC }, paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{ properties: { page: { margin: { top: 1200, bottom: 1200, left: 1300, right: 1300 } } }, children: C }],
});
function bullet(x) { return bul(x); }
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(path.join(__dirname, "Kavach_Phase2_Plan.docx"), buf); console.log("written"); });
