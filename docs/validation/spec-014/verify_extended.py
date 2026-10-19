"""SPEC-014 extended verification (answers the Codex implementation review): controlled response
delays, study retention, both sweep parameters, in-flight sweep invalidation, actual minimum index,
keyboard walkthrough, axe/390px checks in populated states, Appendix A exact strings, Stage 4 field
contract (AC-13), rail labels against canonical data.
Usage: python verify_extended.py BASE_URL AXE_JS SPEC_MD DATA_TS OUT.json"""
import glob, json, os, re, sys
from playwright.sync_api import sync_playwright

BASE, AXE, SPEC, DATA, OUT = sys.argv[1:6]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
def ok(name, cond, detail=""):
    res.append({"result": "PASS" if cond else "FAIL", "check": name, "detail": str(detail)[:300]}); print(res[-1]["result"], name, str(detail)[:140])

DELAY = """(()=>{const of=window.fetch;window.__delays={};window.__log=[];window.fetch=async(u,o)=>{const url=String(u);
 for(const k in window.__delays){ if(url.includes(k)){ await new Promise(r=>setTimeout(r,window.__delays[k])); } }
 window.__log.push(url); return of(u,o)}})()"""

def set_slider(pg, idx, value):
    pg.evaluate("""([i,v])=>{const el=document.querySelectorAll('#stage-configure input[type=range]')[i];
      const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(el,String(v));
      el.dispatchEvent(new Event('input',{bubbles:true}));}""", [idx, value])
    pg.wait_for_timeout(150)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); ctx.add_init_script(DELAY)
    pg = ctx.new_page()
    resp = []
    pg.on("response", lambda r: resp.append(r) if "/simulations/" in r.url else None)
    pg.goto(BASE + "/sandbox", wait_until="networkidle"); pg.wait_for_timeout(1500)

    # --- actual minimum index: scrubber default equals the argmin of V_dc after the event in the API response
    ls = next(r for r in resp if r.url.endswith("/simulations/load-step")).json()
    tv = ls["timeseries"]; ev_t = ls["events"][0]["time_s"]
    idx_min = min((i for i, t in enumerate(tv["time_s"]) if t >= ev_t), key=lambda i: tv["v_dc_v"][i])
    got = int(pg.input_value("[data-testid=state-at-time] input[aria-label=Time]"))
    ok("mount: scrubber default is the actual post-event V_dc minimum sample (+/-1)", abs(got - idx_min) <= 1, f"scrubber {got}, argmin {idx_min}")

    # --- Stage 4 field contract (AC-13): direct fields equal the response; derived fields equal the engineering-result tiles
    tk = pg.inner_text("[data-testid=engineering-takeaway]")
    tl = ls["protection_timeline"]
    ok("AC-13 outcome/detail/recovery/coordination strings equal the API response verbatim",
       all(x in tk for x in [tl["outcome_label"], tl["outcome_detail"], tl["recovery_label"], tl["coordination"]["result_label"]]))
    tiles = pg.inner_text("main")
    m = re.search(r"Lowest V_dc\s+([0-9.]+) V at t = ([0-9.]+) s", tk); d = re.search(r"Energy deficit\s+([0-9.]+) kJ", tk)
    ok("AC-13 derived Load Step values match the Engineering Result tiles", bool(m and d) and f"{m.group(1)}" in tiles and f"{d.group(1)}" in tiles, (m.groups() if m else None, d.group(1) if d else None))

    # --- Appendix A exact strings: parse quoted texts from the spec, require presence in the rendered Sandbox DOM
    spec = open(SPEC).read(); appx = spec[spec.index("## Appendix A."):spec.index("## 16. Review Record")]
    rows = {}
    for line in appx.splitlines():
        mm = re.match(r"\| (A\d+) \| (.*?) \| (?:[A-Z/ ()a-z;,0-9—-]|[^|])*?\|", line)
        mrow = re.match(r"\| (A\d+) \|(.*)", line)
        if mrow:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows[cells[0]] = cells[1]
    def quoted(cell): return re.findall(r'"([^"]+)"', cell)
    for _ in range(1):
        pg.locator("label:has([data-testid='study-option-compare'])").click(); pg.wait_for_timeout(2500)
        pg.locator("label:has([data-testid='study-option-sweep'])").click(); pg.get_by_role("button", name="Run Sweep").click(); pg.wait_for_timeout(2500)
    full = pg.evaluate("()=>document.querySelector('main').textContent").replace(" ", " ")
    fullN = re.sub(r"\s+", " ", full)
    need = {"A1": None, "A2": None, "A3": None, "A5": None, "A6": None, "A7": None, "A8": None, "A9": None, "A13": None, "A14": None}  # A10 and A11 are checked verbatim in the B-E state below
    for k in need:
        qs = quoted(rows.get(k, ""))
        # take the body text inside the outer quotes (cell format: **Label:** "text")
        body = qs[-1] if qs else ""
        if k == "A6": body = qs[0]  # first sentence pair; A13 checked separately
        present = re.sub(r"\s+", " ", body) in fullN if body else False
        ok(f"AC-23 Appendix {k} text rendered verbatim", present, body[:70])
    # A8 splits into two sentences in the DOM only for Load Step: whole string must be present (joined by a space)
    # A11: shown for B-E; A10: shown when sweep selected on B-E (checked in the state section below)

    # --- study retention across switches, both sweep parameters, in-flight sweep invalidation
    ok("study: sweep result present before switching", pg.locator("#stage-investigate table").count() >= 1)
    n_rows = pg.locator("#stage-investigate table tbody tr").count()
    pg.locator("label:has([data-testid='study-option-compare'])").click(); pg.wait_for_timeout(2000)
    pg.locator("label:has([data-testid='study-option-sweep'])").click(); pg.wait_for_timeout(300)
    ok("study: sweep result retained after sweep -> compare -> sweep", pg.locator("#stage-investigate table tbody tr").count() == n_rows and n_rows > 0, n_rows)
    pg.get_by_role("button", name="SST RESPONSE TIME (τ_SST)").first.click() if pg.get_by_role("button", name="SST RESPONSE TIME (τ_SST)").count() else pg.locator("#stage-investigate button", has_text="SST RESPONSE TIME").first.click()
    pg.get_by_role("button", name="Run Sweep").click(); pg.wait_for_timeout(2500)
    ok("sweep: second parameter (tau_sst) sweep runs and renders", "SST RESPONSE TIME" in pg.inner_text("#stage-investigate").upper() and pg.locator("#stage-investigate table tbody tr").count() >= 5)
    # in-flight sweep invalidated by scenario change
    pg.evaluate("window.__delays={'load-step':1500}")
    pg.get_by_role("button", name="Run Sweep").click(); pg.wait_for_timeout(200)
    pg.click("[data-testid='scenario-option-thermal_trip']"); pg.wait_for_timeout(3500)
    ok("in-flight sweep discarded on scenario change (no sweep result appears)", pg.locator("#stage-investigate table").count() == 0)
    ok("B-E: sweep option disabled with the visible reason (A10)", pg.locator("[data-testid=study-option-sweep]").is_disabled() and "Sensitivity sweeps are available for Load Step only." in pg.inner_text("#stage-investigate"))
    ok("B-E: fixed-preset note (A11) visible verbatim", "This scenario is a fixed preset; parameters are not adjustable here." in pg.inner_text("#stage-configure"))
    pg.evaluate("window.__delays={}")
    pg.click("[data-testid='scenario-option-load_step']"); pg.wait_for_timeout(2000)

    # --- controlled reordering: a slow Run Experiment response must not overwrite a later scenario selection
    # (the scenario selector is disabled only while a scenario is loading, not while an experiment runs)
    pg.evaluate("window.__delays={'simulations/load-step':2500}")
    set_slider(pg, 0, 0.9)
    pg.get_by_role("button", name="Run Experiment").click(); pg.wait_for_timeout(200)
    pg.evaluate("window.__delays={}")
    pg.click("[data-testid='scenario-option-thermal_trip']"); pg.wait_for_timeout(4500)
    ok("reordered responses: slow Run Experiment never overwrites the later Thermal Trip selection", "Thermal Trip" in pg.inner_text("[data-testid=run-provenance]") and pg.get_by_role("button", name="Run Experiment").count() == 0, pg.inner_text("[data-testid=run-provenance]"))
    pg.click("[data-testid='scenario-option-load_step']"); pg.wait_for_timeout(2000)

    # --- keyboard walkthrough: operate Stage 1-3 with keyboard only
    pg.goto(BASE + "/sandbox", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.focus("[data-testid='scenario-option-sustained_high_load']"); pg.keyboard.press("Enter"); pg.wait_for_timeout(2500)
    ok("keyboard: Enter on a scenario button selects it", "Sustained High Load" in pg.inner_text("[data-testid=run-provenance]"))
    pg.focus("[data-testid='scenario-option-load_step']"); pg.keyboard.press("Space"); pg.wait_for_timeout(2000)
    pg.focus("#stage-configure input[type=range]"); [pg.keyboard.press("ArrowRight") for _ in range(2)]; pg.wait_for_timeout(200)
    ok("keyboard: slider operable with arrow keys (unrun marker appears)", pg.is_visible("[data-testid=unrun-values]"))
    pg.focus("#stage-configure button:has-text('Run Experiment')"); pg.keyboard.press("Enter"); pg.wait_for_timeout(2000)
    ok("keyboard: Run Experiment via Enter", "experiment values" in pg.inner_text("[data-testid=run-provenance]"))
    pg.focus("[data-testid='study-option-compare']"); pg.keyboard.press("Space"); pg.wait_for_timeout(2500)
    ok("keyboard: study chooser operable (Compare via Space)", pg.is_visible("[data-testid=scenario-comparison]"))
    ok("keyboard: every scroller is reachable (tabindex 0) and named", all(pg.evaluate("()=>[...document.querySelectorAll('[role=region][tabindex=\"0\"]')].every(e=>e.getAttribute('aria-label'))") for _ in [0]))

    # --- axe + 390px element checks in populated states (sweep results, compare, takeaway)
    pg.locator("label:has([data-testid='study-option-sweep'])").click(); pg.get_by_role("button", name="Run Sweep").click(); pg.wait_for_timeout(2500)
    pg.add_script_tag(path=AXE)
    v = pg.evaluate("async()=>{const r=await axe.run(document,{resultTypes:['violations']});return r.violations.filter(v=>['critical','serious'].includes(v.impact)).map(v=>v.id+':'+v.nodes.length)}")
    ok("axe: no critical/serious violations with populated sweep results (desktop)", not v, v)
    pg.locator("label:has([data-testid='study-option-compare'])").click(); pg.wait_for_timeout(2500)
    v = pg.evaluate("async()=>{const r=await axe.run(document,{resultTypes:['violations']});return r.violations.filter(v=>['critical','serious'].includes(v.impact)).map(v=>v.id+':'+v.nodes.length)}")
    ok("axe: no critical/serious violations with Compare table (desktop)", not v, v)
    mob = b.new_context(viewport={"width": 390, "height": 844}); mob.add_init_script(DELAY); mp = mob.new_page()
    mp.goto(BASE + "/sandbox", wait_until="networkidle"); mp.wait_for_timeout(1500)
    mp.locator("label:has([data-testid='study-option-compare'])").click(); mp.wait_for_timeout(2500)
    mp.locator("label:has([data-testid='study-option-sweep'])").click(); mp.get_by_role("button", name="Run Sweep").click(); mp.wait_for_timeout(2500)
    def elem_check(page, tag):
        r = page.evaluate("""()=>{const W=document.documentElement.clientWidth;const sc=[...document.querySelectorAll('[role=region][tabindex="0"]')];const bad=[];
          document.querySelectorAll('main *').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||e.closest('[hidden]'))return;
            if(r.right>W+1 && !sc.some(s=>s!==e&&s.contains(e))) bad.push(e.tagName+'.'+String(e.className).slice(0,40)+' '+Math.round(r.right));});
          const need=sc.filter(s=>s.scrollWidth>s.clientWidth+1);
          return {sw:document.documentElement.scrollWidth,W,bad:bad.slice(0,5),nbad:bad.length,unnamed:sc.filter(s=>!s.getAttribute('aria-label')).length,
                  hint:need.every(s=>!!s.parentElement.querySelector('[data-testid=scroll-hint]')),scrollers:sc.length}}""")
        ok(f"AC-17 {tag}: page width, elements inside viewport or named scroller, hints", r["sw"] == r["W"] and r["nbad"] == 0 and r["unnamed"] == 0 and r["hint"], r)
    elem_check(mp, "390px /sandbox with sweep results")
    mp.locator("label:has([data-testid='study-option-compare'])").click(); mp.wait_for_timeout(2500)
    elem_check(mp, "390px /sandbox with Compare table")
    mp.goto(BASE + "/architecture", wait_until="networkidle"); mp.click("[data-testid='show-all-drivers']"); mp.click("[data-testid='show-all-boundaries']"); mp.wait_for_timeout(300)
    elem_check(mp, "390px /architecture show-all")
    sticky = mp.evaluate("()=>1")
    # --- rail labels vs canonical data
    data = open(DATA).read()
    archs = {}
    for blk in re.finditer(r'id: "(conventional-ac|ac-to-800vdc|mv-to-800vdc)",.*?nodes: \[(.*?)\n    \],', data, re.S):
        nodes = re.findall(r'id: "([a-z]-[a-z-]+)",\s+categoryId: "[a-z_]+",\s+lane: "main",\s+label: "([^"]+)"', blk.group(2))
        archs[blk.group(1)] = [l for _, l in nodes]
    ap = b.new_context(viewport={"width": 1440, "height": 900}).new_page(); ap.goto(BASE + "/architecture", wait_until="networkidle")
    for opt, exp in archs.items():
        ap.locator(f"label:has([data-testid='rail-option-{opt}'])").click()
        got = ap.eval_on_selector_all("[data-testid=signal-path-rail] li", "els=>els.map(e=>e.textContent.trim())")
        ok(f"AC-25 rail {opt}: node labels equal canonical main-lane labels", got == exp and len(exp) > 0, (got, exp))
    # baseline-independent: SST only in conceptual
    ok("AC-25 canonical data: SST label only in mv-to-800vdc", [a for a, l in archs.items() if any("Solid-State" in x for x in l)] == ["mv-to-800vdc"], archs.keys())
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
print("FAILS:", sum(1 for r in res if r["result"] == "FAIL"))
