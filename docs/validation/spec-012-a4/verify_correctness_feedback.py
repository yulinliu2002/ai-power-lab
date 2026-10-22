"""SPEC-012 amendment A4 (milestone M1) browser verification of correctness feedback in Predict and Apply.

Usage: python3 -I verify_correctness_feedback.py BASE_URL API_URL OUT_DIR
  C1  Predict, each of the four options: status is "Correct" only for the option equal to an independent
      classification of the API response, "Incorrect" otherwise; icon (svg) AND text present; scope sentence present
  C2  Apply, each of the four options: "Defensible engineering judgment" only for the one defensible option,
      "Not defensible" otherwise; icon AND text; the existing explanation follows
  C3  Pre-submit secrecy (Predict and Apply): no status text, svg status icon, data-status, status colour class,
      or correctness-bearing accessible name anywhere in the page, before and after picking, before submit
  C4  Selected answer stays identifiable after submit ("Your answer" text on the selected option only);
      unselected options carry no status styling or marker
  C5  Status colour classes are the DESIGN.md tokens (status-good / status-critical); text alone distinguishes the states
  C6  Apply: changing the pick after submit clears the feedback (no stale verdict)
  C7  Screenshots at 1440 and 390 px, no horizontal overflow, console clean
"""
import glob, json, os, re, sys, urllib.request
from playwright.sync_api import sync_playwright

BASE, API, OUT = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), sys.argv[3]
os.makedirs(OUT + "/shots", exist_ok=True)
res = []
def rec(check, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + check, detail)

req = urllib.request.Request(API + "/api/v1/simulations/load-step", data=b"{}", headers={"Content-Type": "application/json"})
run = json.load(urllib.request.urlopen(req))
T = run["timeseries"]; vref = run["thresholds"]["voltage_reference_v"]; n = len(T["time_s"])
ei = next(i for i, t in enumerate(T["time_s"]) if t >= run["events"][0]["time_s"])
vmin = min(T["v_dc_v"][ei:])
last_breach = max((i for i in range(ei, n) if abs(T["v_dc_v"][i] - vref) / vref > 0.01), default=-1)
assert vmin < vref and last_breach < n - 1, "independent classification expects falls-recovers"
OBSERVED = "falls-recovers"
PRED = ["rises", "falls-recovers", "flat", "falls-stays"]
APPLY = ["agree", "mechanism-plus-evidence", "tune-capacitance", "tune-gains"]
DEFENSIBLE = "mechanism-plus-evidence"
STATUS_WORDS = re.compile(r"\b(correct|incorrect|defensible|not defensible)\b", re.I)

def lab(pg, kind, oid): return pg.locator(f'label:has([data-testid="{kind}-{oid}"])')
def leaks(pg):
    """Anything that could reveal correctness: status text, status nodes, status colours, aria names."""
    return pg.evaluate("""()=>{
      const out=[]; const body=document.body.innerText;
      if (/\\b(correct|incorrect|defensible)\\b/i.test(body.replace(/not a claim/gi,''))) out.push('text');
      for (const id of ['predict-status','apply-status','predict-feedback','apply-feedback']) if (document.querySelector('[data-testid="'+id+'"]')) out.push(id);
      if (document.querySelector('[data-status]')) out.push('data-status');
      if (document.querySelector('[class*="status-good"],[class*="status-critical"]')) out.push('colour-class');
      for (const e of document.querySelectorAll('[aria-label],[aria-describedby],[title]')) {
        const v=(e.getAttribute('aria-label')||'')+(e.getAttribute('title')||'');
        if (/correct|defensible|incorrect/i.test(v)) out.push('aria:'+v);
      }
      return out;}""")

exe = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe[0] if exe else None)
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    def fresh():
        pg.goto(BASE + "/learn", wait_until="networkidle"); pg.wait_for_timeout(1000)

    # C3 Predict secrecy: before pick, after pick, before commit
    fresh(); a = leaks(pg)
    lab(pg, "prediction", "falls-recovers").click(); pg.wait_for_timeout(100); b2 = leaks(pg)
    lab(pg, "prediction", "rises").click(); pg.wait_for_timeout(100); b3 = leaks(pg)
    rec("C3 Predict: nothing reveals correctness before commit (no pick / each pick)", not (a or b2 or b3), str([a, b2, b3]))
    pg.screenshot(path=f"{OUT}/shots/a4-1440-predict-before-commit.png", full_page=True)

    # C1 / C4 / C5 Predict, every option
    ok1 = ok4 = ok5 = True
    for oid in PRED:
        fresh(); lab(pg, "prediction", oid).click(); pg.locator('[data-testid="commit-prediction"]').click(); pg.wait_for_timeout(250)
        st = pg.locator('[data-testid="predict-status"]')
        txt = st.inner_text().strip(); good = st.get_attribute("data-status") == "good"; icon = st.locator("svg").count() == 1
        scope = pg.locator('[data-testid="predict-scope"]').inner_text()
        want = "Correct" if oid == OBSERVED else "Incorrect"
        ok1 &= txt == want and icon and (good == (oid == OBSERVED)) and "simplified model" in scope and "not a claim about every real" in scope
        yours = pg.locator('[data-testid="prediction-your-answer"]')
        others = pg.locator('label:has([data-testid^="prediction-"]) [data-testid="prediction-your-answer"]').count()
        ok4 &= yours.count() == 1 and yours.evaluate("e=>e.closest('label').querySelector('input').checked") is True and others == 1
        cls = st.get_attribute("class")
        ok5 &= ("status-good" in cls) == (oid == OBSERVED) and ("status-critical" in cls) == (oid != OBSERVED)
        pg.screenshot(path=f"{OUT}/shots/a4-1440-predict-{oid}.png", full_page=True)
    rec("C1 Predict: Correct only for the observed outcome, Incorrect otherwise; icon + text + model-scope sentence", ok1)
    rec("C4 Predict: committed answer tagged 'Your answer' (one only, on the checked option)", ok4)
    rec("C5 Predict: status classes are status-good / status-critical tokens", ok5)

    # C3 Apply secrecy, then C2 / C4 / C5 / C6
    fresh(); lab(pg, "prediction", "falls-recovers").click(); pg.locator('[data-testid="commit-prediction"]').click()
    pg.locator('[data-testid="step-tab-apply"]').click(); pg.wait_for_timeout(300)
    sec = leaks(pg)
    for oid in APPLY:
        lab(pg, "apply", oid).click(); pg.wait_for_timeout(80)
        sec += leaks(pg)
    rec("C3 Apply: nothing reveals defensibility before 'Check my reasoning' (any pick)", not sec, str(sec))
    pg.screenshot(path=f"{OUT}/shots/a4-1440-apply-before-check.png", full_page=True)
    ok2 = ok4a = ok5a = True
    for oid in APPLY:
        lab(pg, "apply", oid).click(); pg.locator('[data-testid="check-reasoning"]').click(); pg.wait_for_timeout(150)
        st = pg.locator('[data-testid="apply-status"]'); txt = st.inner_text().strip(); good = st.get_attribute("data-status") == "good"
        want = "Defensible engineering judgment" if oid == DEFENSIBLE else "Not defensible"
        expl = pg.locator('[data-testid="apply-feedback"] p').inner_text().strip()
        ok2 &= txt == want and st.locator("svg").count() == 1 and good == (oid == DEFENSIBLE) and len(expl) > 40
        mine = pg.locator('[data-testid="apply-your-answer"]')
        ok4a &= mine.count() == 1 and mine.evaluate("e=>e.closest('label').querySelector('input').checked") is True
        cls = st.get_attribute("class"); ok5a &= ("status-good" in cls) == (oid == DEFENSIBLE) and ("status-critical" in cls) == (oid != DEFENSIBLE)
        pg.screenshot(path=f"{OUT}/shots/a4-1440-apply-{oid}.png", full_page=True)
    rec("C2 Apply: 'Defensible engineering judgment' only for the defensible option, 'Not defensible' otherwise; icon + text + explanation", ok2)
    rec("C4 Apply: submitted answer tagged 'Your answer' (one only, on the checked option)", ok4a)
    rec("C5 Apply: status classes are status-good / status-critical tokens", ok5a)
    lab(pg, "apply", "agree").click(); pg.wait_for_timeout(100)
    rec("C6 Apply: changing the pick clears the previous verdict", pg.locator('[data-testid="apply-feedback"]').count() == 0 and pg.locator('[data-testid="apply-your-answer"]').count() == 0)

    # C7 mobile
    m = b.new_page(viewport={"width": 390, "height": 844}); merr = []
    m.on("console", lambda x: merr.append(x.text) if x.type in ("error", "warning") else None)
    m.goto(BASE + "/learn", wait_until="networkidle"); m.wait_for_timeout(1000)
    m.locator('label:has([data-testid="prediction-rises"])').click(); m.locator('[data-testid="commit-prediction"]').click(); m.wait_for_timeout(250)
    m.screenshot(path=f"{OUT}/shots/a4-390-predict-incorrect.png", full_page=True)
    ov1 = m.evaluate("()=>document.documentElement.scrollWidth>innerWidth")
    m.locator('[data-testid="step-tab-apply"]').click(); m.wait_for_timeout(250)
    m.locator('label:has([data-testid="apply-mechanism-plus-evidence"])').click(); m.locator('[data-testid="check-reasoning"]').click(); m.wait_for_timeout(150)
    m.screenshot(path=f"{OUT}/shots/a4-390-apply-defensible.png", full_page=True)
    ov2 = m.evaluate("()=>document.documentElement.scrollWidth>innerWidth")
    rec("C7 no horizontal overflow at 390 px; console clean at both widths", not ov1 and not ov2 and not errs and not merr, str(errs[:2] + merr[:2]))
    b.close()
print("TOTAL", sum(res), "PASS", len(res) - sum(res), "FAIL")
sys.exit(0 if all(res) else 1)
