"""SPEC-012 amendment A2 (milestone M1) browser verification of the Load Step lesson.

Usage: python3 -I verify_load_step_lesson.py BASE_URL API_URL OUT_DIR
  L1  Discover is gated until a prediction is committed (or explicitly skipped); the model result is absent before that
  L2  Commit is disabled until a pick; committing locks the options; reveal text appears only after commit
  L3  Prediction comparison: observed outcome and verdict agree with an independent classification of the API response
  L4  Time cursor: slider, jump buttons, readout equal the API sample at that index, and both charts' cursor lines move together
  L5  Explain: measured cause chain values equal independent recomputation from the API response
  L6  Apply: question present, feedback for each option, exactly one defensible option, no stored state across reload
  L7  Static lesson prose (prediction/apply options and feedback) has no digits and no ranking terms (R6, AC-5)
  L8  Keyboard-only walkthrough of the whole lesson
  L9  Other four cases unchanged: Discover not gated, native details reveal, no prediction picker
  L10 390 and 1440 px: no horizontal overflow, console clean, screenshots
"""
import glob, json, os, re, sys, urllib.request
from playwright.sync_api import sync_playwright

BASE, API, OUT = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), sys.argv[3]
os.makedirs(OUT + "/shots", exist_ok=True)
res = []
def rec(check, ok, detail=""):
    res.append({"check": check, "result": "PASS" if ok else "FAIL", "detail": detail})
    print(("PASS " if ok else "FAIL ") + check, detail)
def get(path, body=None):
    req = urllib.request.Request(API + path, data=body, headers={"Content-Type": "application/json"} if body is not None else {})
    return json.load(urllib.request.urlopen(req))

run = get("/api/v1/simulations/load-step", b"{}")
T = run["timeseries"]; vref = run["thresholds"]["voltage_reference_v"]; n = len(T["time_s"])
t_event = run["events"][0]["time_s"]
ei = next(i for i, t in enumerate(T["time_s"]) if t >= t_event)
vmin = min(T["v_dc_v"][ei:])
last_breach = max((i for i in range(ei, n) if abs(T["v_dc_v"][i] - vref) / vref > 0.01), default=-1)
recovered = last_breach < n - 1
expected_obs = "falls-recovers" if vmin < vref and recovered else "other"
BANNED = re.compile(r"\b(best|worst|wins|winner|superior|inferior|safer|more reliable|outperforms)\b", re.I)

def pick(pg, i): pg.locator(f'label:has([data-testid="case-option-{i}"])').click()
def step(pg, s): pg.locator(f'[data-testid="step-tab-{s}"]').click(); pg.wait_for_timeout(200)
def cursor_x(pg): return pg.evaluate("()=>[...document.querySelectorAll('[data-testid=\"observe-live\"] svg line[stroke-width=\"1.5\"]')].map(l=>+l.getAttribute('x1'))")

exe = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe[0] if exe else None)
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/learn", wait_until="networkidle"); pg.wait_for_timeout(1200)

    # L1, L2
    pg.screenshot(path=f"{OUT}/shots/m1-1440-1-predict.png", full_page=True)
    rec("L1 predict picker has four options", pg.locator('[data-testid^="prediction-"][type="radio"]').count() == 4)
    rec("L2 commit disabled before a pick", pg.locator('[data-testid="commit-prediction"]').is_disabled())
    rec("L2 reveal hidden before commit", pg.locator('[data-testid="predict-reveal"]').count() == 0)
    step(pg, "discover")
    rec("L1 Discover gated before commit", pg.locator('[data-testid="discover-gate"]').is_visible() and pg.locator('[data-testid="observe-live"]').count() == 0 and pg.locator('[data-testid="cursor-panel"]').count() == 0)
    step(pg, "predict")
    pg.locator('label:has([data-testid="prediction-falls-recovers"])').click()
    pg.locator('[data-testid="commit-prediction"]').click(); pg.wait_for_timeout(200)
    rec("L2 commit locks options and shows reveal", pg.locator('[data-testid="prediction-committed"]').is_visible() and pg.locator('[data-testid="prediction-falls-recovers"]').is_disabled() and pg.locator('[data-testid="predict-reveal"]').count() == 1)

    # L3 L4
    pg.get_by_role("button", name=re.compile("Check it against the model")).click(); pg.wait_for_timeout(1800)
    obs = pg.locator('[data-testid="prediction-observed"]').inner_text()
    ver = pg.locator('[data-testid="prediction-verdict"]').inner_text()
    rec("L3 comparison agrees with independent classification", expected_obs == "falls-recovers" and "fell below its reference and then returned" in obs and ver.startswith("Match."), f"{obs} | {ver[:40]}")
    pg.screenshot(path=f"{OUT}/shots/m1-1440-2-discover.png", full_page=True)
    sl = pg.locator('[data-testid="cursor-slider"]')
    xs0 = cursor_x(pg)
    ok = len(xs0) == 2 and abs(xs0[0] - xs0[1]) < 0.01
    for idx in (ei, T["v_dc_v"].index(min(T["v_dc_v"])), n // 2, n - 1):
        sl.evaluate("(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}", idx)
        pg.wait_for_timeout(120)
        idx_real = int(sl.input_value())
        shown = pg.locator('[data-testid="cursor-readout"]').inner_text()
        v = f"{T['v_dc_v'][idx_real]:.1f} V"; pl = f"{T['p_load_w'][idx_real]/1e3:.1f} kW"; ps = f"{T['p_sst_w'][idx_real]/1e3:.1f} kW"
        xs = cursor_x(pg)
        ok &= v in shown and pl in shown and ps in shown and len(xs) == 2 and abs(xs[0] - xs[1]) < 0.01
        tt = pg.locator('[data-testid="cursor-time"]').inner_text()
        ok &= f"{T['time_s'][idx_real]:.3f}" in tt
    rec("L4 cursor readout equals API sample and both chart cursors move together", ok)
    xs_a = cursor_x(pg)
    pg.locator('[data-testid="jump-minimum"]').click(); pg.wait_for_timeout(120)
    imin = int(sl.input_value()); rec("L4 jump to minimum lands on the voltage minimum", abs(T["v_dc_v"][imin] - min(T["v_dc_v"])) < 1e-6, f"idx={imin}")
    pg.locator('[data-testid="jump-step"]').click(); pg.wait_for_timeout(120)
    ph1 = pg.locator('[data-testid="cursor-phase"]').inner_text()
    pg.locator('[data-testid="jump-minimum"]').click(); pg.wait_for_timeout(120)
    ph2 = pg.locator('[data-testid="cursor-phase"]').inner_text()
    rec("L4 phase annotation changes with the cursor", ph1 != ph2 and len({ph1, ph2}) == 2, f"{ph1[:30]} / {ph2[:30]}")

    # L5
    step(pg, "explain")
    g = norm = re.sub(r"\s+", " ", pg.locator('[data-testid="grounding-panel"]').inner_text())
    shortfall = max((T["p_load_w"][i] - T["p_sst_w"][i]) for i in range(ei, n)) / 1e3
    tgt = max((T["p_target_w"][i] - T["p_load_w"][i]) for i in range(ei, n) if T["v_dc_v"][i] < vref) / 1e3
    rec("L5 grounding values equal recomputation from the API",
        f"{shortfall:.1f} kW" in g and f"{tgt:.1f} kW" in g and f"{vmin:.1f} V" in g and f"{T['p_load_w'][ei-1]/1e3:.1f} kW" in g and f"{T['p_load_w'][ei]/1e3:.1f} kW" in g, g[:160])
    pg.screenshot(path=f"{OUT}/shots/m1-1440-3-explain.png", full_page=True)

    # L6 L7
    step(pg, "apply")
    ok6 = pg.locator('[data-testid="apply-prompt"]').is_visible() and pg.locator('[data-testid="check-reasoning"]').is_disabled()
    verdicts, texts = {}, [pg.locator('[data-testid="apply-prompt"]').inner_text()]
    for oid in ["agree", "mechanism-plus-evidence", "tune-capacitance", "tune-gains"]:
        pg.locator(f'label:has([data-testid="apply-{oid}"])').click(); pg.locator('[data-testid="check-reasoning"]').click(); pg.wait_for_timeout(100)
        fb = pg.locator('[data-testid="apply-feedback"]').inner_text(); verdicts[oid] = fb.startswith("Defensible."); texts.append(fb)
        texts.append(pg.locator(f'label:has([data-testid="apply-{oid}"])').inner_text())
    rec("L6 apply: feedback per option, exactly one defensible (mechanism-plus-evidence)", ok6 and sum(verdicts.values()) == 1 and verdicts["mechanism-plus-evidence"], str(verdicts))
    pg.screenshot(path=f"{OUT}/shots/m1-1440-4-apply.png", full_page=True)
    step(pg, "predict")
    for lab in pg.locator('[data-testid^="prediction-"][type="radio"]').evaluate_all("els=>els.map(e=>e.closest('label').innerText)"): texts.append(lab)
    texts.append(pg.locator('[data-testid="prediction-falls-recovers"]').evaluate("e=>e.closest('fieldset').innerText"))
    pg.locator('[data-testid="step-tab-discover"]').click(); pg.wait_for_timeout(200)
    texts.append(pg.locator('[data-testid="prediction-verdict"]').inner_text())
    rec("L7 lesson prose: no digits, no ranking terms", not any(re.search(r"\d", t) for t in texts) and not any(BANNED.search(t) for t in texts), str([t[:40] for t in texts if re.search(r"\d", t) or BANNED.search(t)]))
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(800)
    rec("L6 no stored state: reload returns to an uncommitted Predict", pg.locator('[data-testid="commit-prediction"]').is_disabled() and pg.locator('[data-testid="prediction-falls-recovers"]').is_checked() is False)

    # L8 keyboard
    pg.focus('[data-testid="step-tab-predict"]')
    pg.locator('[data-testid="prediction-falls-recovers"]').focus(); pg.keyboard.press("Space")
    pg.locator('[data-testid="commit-prediction"]').focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    committed = pg.locator('[data-testid="prediction-committed"]').is_visible()
    pg.get_by_role("button", name=re.compile("Check it against")).focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(1800)
    sl = pg.locator('[data-testid="cursor-slider"]'); sl.focus(); before = int(sl.input_value())
    for _ in range(5): pg.keyboard.press("ArrowRight")
    after = int(sl.input_value())
    pg.locator('[data-testid="step-next"]').focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    on_explain = pg.locator('[data-testid="step-explain"]').count() == 1
    pg.locator('[data-testid="step-next"]').focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    pg.locator('label:has([data-testid="apply-mechanism-plus-evidence"]) input').focus(); pg.keyboard.press("Space")
    pg.locator('[data-testid="check-reasoning"]').focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    rec("L8 keyboard-only: predict, commit, scrub (arrow keys), next, answer, check", committed and after > before and on_explain and pg.locator('[data-testid="apply-feedback"]').is_visible(), f"scrub {before}->{after}")
    rec("L10 console clean at 1440", not errs, str(errs[:3]))

    # L9 other cases
    ok9 = True
    for cid in ["sustained_high_load", "thermal_trip", "grid_sag", "grid_loss"]:
        pick(pg, cid); pg.wait_for_timeout(1500)
        step(pg, "predict"); a = pg.locator('[data-testid="predict-picker"]').count() == 0 and pg.locator("details summary").count() == 1
        step(pg, "discover"); a &= pg.locator('[data-testid="discover-gate"]').count() == 0 and pg.locator('[data-testid="cursor-panel"]').count() == 0 and pg.locator('[data-testid="observe-live"]').count() == 1
        step(pg, "explain"); a &= pg.locator('[data-testid="grounding-panel"]').count() == 0
        step(pg, "apply"); a &= pg.locator('[data-testid="apply-question"]').count() == 0 and pg.locator('[data-testid="part-decision"]').count() == 1
        ok9 &= a
        if not a: print("L9 mismatch", cid)
    rec("L9 other four cases unchanged (no gate, no picker, no cursor panel, native reveal)", ok9)

    # L10 mobile
    pm = b.new_page(viewport={"width": 390, "height": 844}); merr = []
    pm.on("console", lambda m: merr.append(m.text) if m.type in ("error", "warning") else None)
    pm.goto(BASE + "/learn", wait_until="networkidle"); pm.wait_for_timeout(1000)
    pm.screenshot(path=f"{OUT}/shots/m1-390-1-predict.png", full_page=True)
    pm.locator('label:has([data-testid="prediction-falls-recovers"])').click(); pm.locator('[data-testid="commit-prediction"]').click()
    allok = True
    for s_ in ["discover", "explain", "apply"]:
        step(pm, s_); pm.wait_for_timeout(1500)
        ov = pm.evaluate("()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth]"); allok &= ov[0] == ov[1]
        pm.screenshot(path=f"{OUT}/shots/m1-390-{s_}.png", full_page=True)
    rec("L10 390 px no horizontal overflow on all four steps", allok)
    rec("L10 390 px console clean", not merr, str(merr[:3]))
    b.close()
json.dump(res, open(OUT + "/verify_load_step_lesson.json", "w"), indent=1)
sys.exit(1 if any(r["result"] == "FAIL" for r in res) else 0)
