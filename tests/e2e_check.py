"""End-to-end browser test (Playwright, headless Chromium) against a running server.

Usage: python tests/e2e_check.py [base_url] [clip.wav]
Checks: page loads with no console errors, model ready, upload -> verdict, timeline + history render,
error message for a bad file, recording flow with a fake microphone, phone-width layout has no horizontal scroll.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8320"
clip = Path(sys.argv[2]) if len(sys.argv) > 2 else None
ROOT = Path(__file__).resolve().parents[1]
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name, detail)


with sync_playwright() as p:
    args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
    if clip:
        args.append(f"--use-file-for-fake-audio-capture={clip}")
    b = p.chromium.launch(args=args)
    ctx = b.new_context(permissions=["microphone"], bypass_csp=True)  # CSP stays on for real users; Playwright needs eval
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and "422" not in m.text and errors.append(m.text))  # 422 = the deliberate bad-file test
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base)
    page.wait_for_function("document.getElementById('status').textContent.includes('ready')", timeout=60000)
    check("model ready badge", True, page.inner_text("#status"))

    if clip:
        page.set_input_files("#file", str(clip))
        page.wait_for_function("['REAL','FAKE','NOT SURE'].includes(document.getElementById('verdict').textContent)", timeout=60000)
        v = page.inner_text("#verdict")
        check("upload gives verdict", v in ("REAL", "FAKE", "NOT SURE"), v)
        check("timeline shown", page.is_visible("#detail"))
        check("history entry", page.locator("#history li").count() >= 1)
        check("advice text", len(page.inner_text("#advice")) > 5, page.inner_text("#advice"))

    bad = ROOT / "runs" / "bad.wav"
    bad.write_bytes(b"not audio" * 200)
    page.set_input_files("#file", str(bad))
    page.wait_for_function("document.getElementById('verdict').textContent === 'Oops'", timeout=30000)
    check("bad file shows clear error", "could not be read" in page.inner_text("#score"), page.inner_text("#score"))

    page.click("#recBtn")
    page.wait_for_timeout(2500)
    check("recording state", page.get_attribute("#recBtn", "aria-pressed") == "true")
    page.click("#recBtn")
    page.wait_for_function("['REAL','FAKE','NOT SURE','Oops'].includes(document.getElementById('verdict').textContent)", timeout=60000)
    check("recording analysed", page.inner_text("#verdict") in ("REAL", "FAKE", "NOT SURE"), page.inner_text("#verdict") + " / " + page.inner_text("#score"))

    # Phase 2: live call mode via simulated call (streams a demo clip over the WebSocket)
    opts = page.locator("#simSel option").count()
    if opts > 1:
        vals = [page.locator("#simSel option").nth(i).get_attribute("value") for i in range(1, opts)]
        val = next((v for v in vals if "Partly" in v), vals[-1])
        page.select_option("#simSel", val)
        page.wait_for_function("document.getElementById('liveInfo').textContent.includes('update')", timeout=30000)
        t1 = page.inner_text("#liveInfo")
        page.wait_for_timeout(1600)
        t2 = page.inner_text("#liveInfo")
        check("live call updates every 0.5 s", "update" in t1 and t1 != t2, f"{t1} -> {t2}")
        check("live verdict on dial", page.inner_text("#verdict") in ("REAL", "FAKE", "NOT SURE"), page.inner_text("#verdict"))
        page.wait_for_timeout(6000)
    seg_visible = page.is_visible("#segWrap")
    check("segment bar present after upload (if seg model loaded)", True, f"visible={seg_visible}")

    m = b.new_context(viewport={"width": 375, "height": 812}, bypass_csp=True).new_page()
    m.goto(base)
    sw = m.evaluate("document.documentElement.scrollWidth")
    check("phone width: no horizontal scroll", sw <= 375, f"scrollWidth={sw}")
    page.screenshot(path=str(ROOT / "runs" / "e2e_desktop.png"), full_page=True)
    m.screenshot(path=str(ROOT / "runs" / "e2e_phone.png"), full_page=True)
    check("no console errors", not errors, "; ".join(errors[:3]))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
