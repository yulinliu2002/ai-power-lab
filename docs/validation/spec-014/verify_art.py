"""Conditions of the Instrument Console approval (visual direction, PR #10):
1 'Tends to favor' stays conditional, supports multiple architectures, never implies a ranking;
2 large live Sandbox values are synchronized with the scrubber and the displayed run, and current/minimum/reference/final are distinguished;
4 charts do not need scrolling at desktop width; 5 System Map topology is the primary visual element.
Usage: python verify_art.py BASE_URL DATA_TS OUT.json"""
import glob, json, os, re, sys
from playwright.sync_api import sync_playwright
BASE, DATA, OUT = sys.argv[1:4]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
def ok(name, cond, detail=""):
    res.append({"result": "PASS" if cond else "FAIL", "check": name, "detail": str(detail)[:300]}); print(res[-1]["result"], name, str(detail)[:160])

data = open(DATA.replace("infrastructureMapData.ts", "architectureChoicesData.ts")).read()
fav = {}
for m in re.finditer(r'(rd\d): \{\s*dominantDriver: "rd\d",\s*favored: \[([^\]]*)\]', data):
    fav[m.group(1)] = re.findall(r'"([a-z0-9-]+)"', m.group(2))
NAMES = {"conventional-ac": "Conventional AC", "ac-to-800vdc": "AC-fed 800 VDC", "mv-to-800vdc": "Conceptual MV-to-800 VDC via SST"}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    for vp, (w, h) in {"desktop": (1440, 900), "mobile": (390, 844)}.items():
        pg = b.new_context(viewport={"width": w, "height": h}).new_page()
        pg.goto(BASE + "/architecture", wait_until="networkidle"); pg.wait_for_timeout(800)
        multi = 0
        for i in range(1, 8):
            pg.locator(f"label:has([data-testid='driver-option-rd{i}'])").click(); pg.wait_for_timeout(120)
            board = pg.locator(f"[data-testid='compare-rd{i}']")
            marked = pg.eval_on_selector_all(f"[data-testid='compare-rd{i}'] .ic-colhead[data-fav='true'] h3", "els=>els.map(e=>e.textContent.trim())")
            exp = [NAMES[x] for x in fav[f"rd{i}"]]
            ok(f"{vp} rd{i}: marked columns equal the data's favored set (conditional, not computed)", sorted(marked) == sorted(exp) and len(exp) >= 1, (marked, exp))
            multi += len(exp) >= 2
            if vp == "mobile":
                chips = pg.eval_on_selector_all(f"[data-testid='compare-rd{i}'] .ic-mfavor", "els=>els.map(e=>({vis:!!(e.offsetWidth||e.offsetHeight),hidden:!!e.closest('[aria-hidden=true]'),t:e.textContent}))")
                ok(f"mobile rd{i}: favored chips are visible, exposed to assistive tech and state the condition", len(chips) == len(exp) and all(c["vis"] and not c["hidden"] and "conditional" in c["t"].lower() and "not a ranking" in c["t"].lower() for c in chips), chips)
            ok(f"{vp} rd{i}: conditional wording present (legend + accessible chip text + decision band)",
               "conditional tendency" in pg.inner_text(f"[data-testid='compare-rd{i}'] .ic-legend").lower()
               and (vp == "mobile" or pg.locator(f"[data-testid='compare-rd{i}'] .ic-favor .sr-only").first.inner_text().lower().count("not a ranking") == 1)
               and "this tends to favor" in pg.inner_text(f"[data-testid='decision-card-rd{i}']").lower())
        ok(f"{vp}: at least one requirement marks multiple architectures", multi >= 1, multi)
        txt = pg.inner_text("main").lower()
        for sent in ["this page does not rank architectures or name a winner; every conditional statement depends on which driver dominates for a given site.",
                     "columns marked tends to favor are a conditional tendency if this requirement dominates for a site, with the exceptions below. they are not a ranking, a score or a winner.",
                     "a conditional tendency with its exceptions, not a verdict."]:
            txt = txt.replace(sent, "")
        for ph in ["not a score", "not a ranking, a score or a winner", "name a winner", "does not rank", "not a verdict", "not a ranking or a winner", "not a ranking, a score or a winner", "no winner", "not a ranking"]:
            txt = txt.replace(ph, "")
        bad = re.findall(r"\b(best|winner|ranking|ranked|score|leader|top choice|optimal)\b", txt)
        ok(f"{vp}: no ranking/score/winner/best language outside the negating sentences", not bad, set(bad))
    # Architecture stage navigation: every link focuses its heading; aria-current tracks; survives driver change and show-all
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page(); pg.goto(BASE + "/architecture", wait_until="networkidle"); pg.wait_for_timeout(800)
    HEADS = {"step-requirement": "h-requirement", "step-compare": "h-compare", "step-tradeoffs": "h-tradeoffs", "step-validation": "h-validation", "references": "h-references"}
    def stage_pass(tag):
        for sid, hid in HEADS.items():
            pg.locator(f"nav[aria-label='Steps on this page'] a[href='#{sid}']").click(); pg.wait_for_timeout(250)
            ok(f"Architecture stage nav {tag}: #{sid} moves focus to its heading", pg.evaluate("()=>document.activeElement.id") == hid, pg.evaluate("()=>document.activeElement.id"))
        for sid in HEADS:
            pg.evaluate(f"()=>{{const el=document.getElementById('{sid}');window.scrollTo({{top: window.scrollY + el.getBoundingClientRect().top - 120, behavior: 'instant'}})}}"); pg.wait_for_timeout(500)
            cur = pg.eval_on_selector_all("nav[aria-label='Steps on this page'] a[aria-current]", "els=>els.map(e=>e.getAttribute('href'))")
            # the requirement list and the board (step 2) start at the same height by design, so either marks that screen; the order rule picks the earlier
            expect = ["#step-requirement"] if sid in ("step-requirement", "step-compare") else [f"#{sid}"]
            ok(f"Architecture stage nav {tag}: with #{sid} scrolled to the top, aria-current is the expected stage ({expect[0]})", cur == expect, cur)
    stage_pass("(default)")
    pg.locator("label:has([data-testid='driver-option-rd4'])").click(); pg.wait_for_timeout(300); stage_pass("(after changing driver)")
    pg.click("[data-testid='show-all-drivers']"); pg.wait_for_timeout(300); stage_pass("(show-all)")

    # Sandbox synchronization
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page(); resp = []
    pg.on("response", lambda r: resp.append(r) if "/simulations/" in r.url else None)
    pg.goto(BASE + "/sandbox", wait_until="networkidle"); pg.wait_for_timeout(1500)
    ls = next(r for r in resp if r.url.endswith("/simulations/load-step")).json(); tv = ls["timeseries"]
    def hero(): return pg.inner_text(".ic-hero-num").replace("V", "").strip()
    def sync(label):
        idx = int(pg.input_value("[data-testid=state-at-time] input[aria-label=Time]"))
        minis = pg.inner_text(".ic-minis")
        exp_v = f"{tv['v_dc_v'][idx]:.1f}"; exp_l = f"{tv['p_load_w'][idx]/1e3:.1f}"; exp_s = f"{tv['p_sst_w'][idx]/1e3:.1f}"
        n = pg.eval_on_selector_all(".ic-minis > div .n", "els=>els.map(e=>e.textContent.replace('kW','').trim())")
        gap = abs(tv["p_load_w"][idx] - tv["p_sst_w"][idx]) / 1e3
        ok(f"Sandbox {label}: hero V_dc, P_load, P_sst and the power gap (each in its own field) equal the displayed run at the scrubber sample {idx}", hero() == exp_v and n == [exp_l, exp_s, f"{gap:.1f}"], (hero(), exp_v, n, exp_l, exp_s, f"{gap:.1f}"))
    sync("default (voltage-minimum sample)")
    pg.focus("[data-testid=state-at-time] input[aria-label=Time]"); pg.keyboard.press("Home"); pg.wait_for_timeout(200); sync("scrubber Home")
    pg.keyboard.press("End"); pg.wait_for_timeout(200); sync("scrubber End")
    vals = pg.inner_text("[data-testid=reference-values]")
    vref = ls["thresholds"]["voltage_reference_v"]
    ev_t = ls["events"][0]["time_s"]; imin = min((i for i, t in enumerate(tv["time_s"]) if t >= ev_t), key=lambda i: tv["v_dc_v"][i])
    ok("Sandbox: current / reference / minimum / final values are distinct and labelled", all(k.lower() in vals.lower() for k in ["Reference", "Minimum in run", "Final (end of run)"]) and f"{vref:.0f} V" in vals and f"{tv['v_dc_v'][imin]:.1f} V" in vals and f"{tv['v_dc_v'][-1]:.1f} V" in vals and "current" in pg.inner_text(".ic-metrics").lower(), vals.replace("\n", " | "))
    # after a new run the hero follows the displayed run
    pg.evaluate("""()=>{const el=document.querySelector('#stage-configure input[type=range]');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(el,'0.95');el.dispatchEvent(new Event('input',{bubbles:true}))}""")
    n0 = len(resp); pg.get_by_role("button", name="Run Experiment").click(); pg.wait_for_timeout(2500)
    ls2 = [r for r in resp[n0:] if r.url.endswith("/simulations/load-step")][-1].json(); tv = ls2["timeseries"]
    sync("after Run Experiment (new displayed run)")
    pg.click("[data-testid='scenario-option-grid_sag']"); pg.wait_for_timeout(2200)
    gs = [r for r in resp if "grid_sag" in r.url][-1].json(); tv = gs["timeseries"]
    sync("Grid Sag (fixed preset; no derived minimum shown)")
    ok("Grid Sag: no derived 'Minimum in run' value is shown for non-Load-Step scenarios", "Minimum in run" not in pg.inner_text("[data-testid=reference-values]"))
    # charts: no scrolling needed at desktop width (Load Step)
    pg.click("[data-testid='scenario-option-load_step']"); pg.wait_for_timeout(2200)
    ok("Sandbox desktop: no chart or schematic needs horizontal scrolling at 1440px (no scroll hints)", pg.locator("[data-testid=scroll-hint]").count() == 0, pg.locator("[data-testid=scroll-hint]").count())
    # System Map topology
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page(); pg.goto(BASE + "/system-map", wait_until="networkidle"); pg.wait_for_timeout(1000)
    top = pg.evaluate("()=>{const t=document.querySelector('.ic-topology').getBoundingClientRect();return [t.top,t.height,t.width]}")
    nodes = pg.locator(".ic-topology [data-main=true]").count()
    inview = pg.evaluate("()=>[...document.querySelectorAll('.ic-topology [data-main=true]')].every(e=>{const r=e.getBoundingClientRect();return r.right<=document.documentElement.clientWidth&&r.left>=0})")
    ok("System Map desktop: topology starts within the first 760px and is the widest element of the page body", top[0] < 760 and top[2] > 1100, top)
    ok("System Map desktop: every main-path node is visible without horizontal scrolling for the Conventional AC view", inview and nodes == 7 and pg.locator("[data-testid=scroll-hint]").count() == 0, (nodes, inview))
    for i in range(1, 3):
        pg.locator("[role=radiogroup][aria-label='Architecture view'] button").nth(i).click(); pg.wait_for_timeout(300)
        cnt = pg.locator(".ic-topology [data-main=true]").count()
        inv = pg.evaluate("()=>[...document.querySelectorAll('.ic-topology [data-main=true]')].every(e=>{const r=e.getBoundingClientRect();return r.right<=document.documentElement.clientWidth&&r.left>=0})")
        ok(f"System Map desktop view {i+1}: all {cnt} main-path nodes inside the viewport (expected 7, 7, 6 per view), no scroll hint", cnt == [7, 7, 6][i] and inv and pg.locator("[data-testid=scroll-hint]").count() == 0, (cnt, inv))
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
print("FAILS:", sum(1 for r in res if r["result"] == "FAIL"))
