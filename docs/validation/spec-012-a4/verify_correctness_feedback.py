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
  C8  Controlled API responses (rises / flat / falls-stays): 'Correct' follows the run, not a hardcoded answer
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
    """Anything that could reveal correctness, including hidden DOM text, every attribute, and
    text reached through aria-describedby / aria-labelledby."""
    return pg.evaluate("""()=>{
      const out=[]; const W=/\\b(correct|incorrect|defensible)\\b/i;
      const all=[...document.querySelectorAll('body, body *')];
      for (const e of all) {
        if (['SCRIPT','STYLE'].includes(e.tagName)) continue;
        // textContent includes display:none / sr-only / aria-hidden text that innerText omits
        const own=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ');
        if (W.test(own.replace(/not a claim/gi,''))) out.push('text:'+e.tagName+':'+own.trim().slice(0,40));
        for (const a of e.attributes) {
          if (a.name==='data-testid' && /(status|feedback)/i.test(a.value)) out.push('testid:'+a.value);
          if (/^data-/.test(a.name) && /(status|correct|defensible|good|critical|verdict)/i.test(a.name+' '+a.value)) out.push('data:'+a.name);
          if (W.test(a.value)) out.push('attr:'+a.name+'='+a.value.slice(0,30));
          if (/status-good|status-critical|check|cross/i.test(a.name==='class'?a.value:'')) out.push('class:'+a.value.slice(0,40));
        }
        for (const k of ['aria-describedby','aria-labelledby']) {
          const v=e.getAttribute(k); if (!v) continue;
          for (const id of v.split(/\\s+/)) { const t=document.getElementById(id); if (t && W.test(t.textContent)) out.push(k+':'+id); }
        }
      }
      return out;}""")

def unsel_clean(pg, kind):
    """Every UNSELECTED option: no 'Your answer', no status/correctness words, no status classes, no svg icon, no data-status."""
    return pg.evaluate("""(kind)=>[...document.querySelectorAll('input[data-testid^="'+kind+'-"][type=radio]')].filter(i=>!i.checked).every(i=>{
      const l=i.closest('label'); const h=l.outerHTML;
      return !/your answer/i.test(l.textContent) && !/\\b(correct|incorrect|defensible)\\b/i.test(l.textContent)
        && !/status-good|status-critical|data-status/.test(h) && l.querySelectorAll('svg').length===0;})""", kind)

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
        ok4 &= yours.count() == 1 and yours.evaluate("e=>e.closest('label').querySelector('input').checked") is True and others == 1 and yours.inner_text().strip().lower() == "your answer" and unsel_clean(pg, "prediction")
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
        ok4a &= mine.count() == 1 and mine.evaluate("e=>e.closest('label').querySelector('input').checked") is True and mine.inner_text().strip().lower() == "your answer" and unsel_clean(pg, "apply")
        cls = st.get_attribute("class"); ok5a &= ("status-good" in cls) == (oid == DEFENSIBLE) and ("status-critical" in cls) == (oid != DEFENSIBLE)
        pg.screenshot(path=f"{OUT}/shots/a4-1440-apply-{oid}.png", full_page=True)
    rec("C2 Apply: 'Defensible engineering judgment' only for the defensible option, 'Not defensible' otherwise; icon + text + explanation", ok2)
    rec("C4 Apply: submitted answer tagged 'Your answer' (one only, on the checked option)", ok4a)
    rec("C5 Apply: status classes are status-good / status-critical tokens", ok5a)
    lab(pg, "apply", "agree").click(); pg.wait_for_timeout(100)
    rec("C6 Apply: changing the pick clears the previous verdict", pg.locator('[data-testid="apply-feedback"]').count() == 0 and pg.locator('[data-testid="apply-your-answer"]').count() == 0)

    # C9 positive controls: the secrecy probe must fire on each kind of leak it claims to catch
    fresh()
    inj = {
      "hidden text": "()=>{const d=document.createElement('span');d.style.display='none';d.textContent='Correct';document.body.appendChild(d)}",
      "sr-only text": "()=>{const d=document.createElement('span');d.className='sr-only';d.textContent='Incorrect';document.body.appendChild(d)}",
      "data attribute": "()=>document.body.setAttribute('data-verdict','good')",
      "aria-describedby": "()=>{const d=document.createElement('p');d.id='zz';d.hidden=true;d.textContent='Defensible';document.body.appendChild(d);document.body.setAttribute('aria-describedby','zz')}",
      "aria-labelledby": "()=>{const d=document.createElement('p');d.id='zy';d.textContent='Incorrect';document.body.appendChild(d);document.body.setAttribute('aria-labelledby','zy')}",
      "data-testid": "()=>document.body.setAttribute('data-testid','correct-answer')",
      "aria-label": "()=>document.body.setAttribute('aria-label','correct answer')",
      "status class": "()=>document.body.classList.add('text-status-good')",
    }
    caught = {}
    for k, js in inj.items():
        fresh(); pg.evaluate(js); caught[k] = bool(leaks(pg))
    rec("C9 secrecy probe is not vacuous: it flags hidden text, sr-only text, data-*, data-testid, aria-describedby, aria-labelledby, aria-label and status classes", all(caught.values()), str(caught))

    # C8 observed-outcome dependency: controlled API responses that produce other outcome classes
    def controlled(label, mutate, expect):
        pg2 = b.new_page(viewport={"width": 1440, "height": 900})
        def fulfil(route):
            r = json.loads(json.dumps(run)); mutate(r); route.fulfill(status=200, content_type="application/json", body=json.dumps(r))
        pg2.route("**/api/v1/simulations/load-step*", fulfil)
        res_ = {}
        for oid in PRED:
            pg2.goto(BASE + "/learn", wait_until="networkidle"); pg2.wait_for_timeout(900)
            pg2.locator(f'label:has([data-testid="prediction-{oid}"])').click(); pg2.locator('[data-testid="commit-prediction"]').click(); pg2.wait_for_timeout(250)
            res_[oid] = pg2.locator('[data-testid="predict-status"]').inner_text().strip()
        pg2.close()
        rec(f"C8 Predict follows the run: {label} -> only '{expect}' is Correct", all(v == ("Correct" if k == expect else "Incorrect") for k, v in res_.items()), str(res_))
    def to_rises(r): r["timeseries"]["v_dc_v"] = [vref * 1.02] * n
    def to_flat(r): r["timeseries"]["v_dc_v"] = [vref] * n
    def to_stays_down(r):
        v = r["timeseries"]["v_dc_v"]; r["timeseries"]["v_dc_v"] = [x if i < ei else vref * 0.9 for i, x in enumerate(v)]
    controlled("voltage above reference, never below", to_rises, "rises")
    controlled("voltage exactly at reference", to_flat, "flat")
    controlled("voltage falls and stays down", to_stays_down, "falls-stays")

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
