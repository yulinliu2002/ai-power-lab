"""SPEC-014 checks: rail semantics (AC-25), disclosures visible on load (AC-26),
type tiers (AC-27), accessibility basics / axe (AC-16), handoff links (AC-5), 390px
element checks (AC-17). Usage: python verify_static.py BASE_URL AXE_JS OUT.json
(axe-core is injected from a local path; it is not a repository dependency.)"""
import glob, json, os, re, sys
from playwright.sync_api import sync_playwright

BASE, AXE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
def ok(name, cond, detail=""):
    res.append({"result": "PASS" if cond else "FAIL", "check": name, "detail": str(detail)[:400]}); print(res[-1]["result"], name, str(detail)[:200])

DIS = {
 "sst": "SST is one candidate technology for the medium-voltage-to-DC stage. It is not required for 800 VDC: the AC-fed 800 VDC architecture reaches the same bus without one.",
 "block": "Blocks in these architectures are functional abstractions, not literal single-stage converters or literal racks; real equipment is internally multi-stage.",
 "sim": "The Advanced Sandbox simulates only the Conceptual MV-to-800 VDC via SST slice, as a simplified average-value model. It does not validate, size or benchmark Conventional AC or AC-fed 800 VDC, and it is not evidence that any architecture is better.",
 "illustrative": "Requirement drivers are illustrative teaching assumptions, not a design basis for any facility.",
 "noWinner": "This page does not rank architectures or name a winner; every conditional statement depends on which driver dominates for a given site.",
}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    for vp, (w, h) in {"desktop": (1440, 900), "mobile": (390, 844)}.items():
        pg = b.new_context(viewport={"width": w, "height": h}).new_page()
        # AC-26 disclosures visible on initial load, no interaction
        pg.goto(BASE + "/architecture", wait_until="networkidle")
        for k, t in DIS.items():
            loc = pg.get_by_text(t, exact=True).first
            ok(f"AC-26 {vp} /architecture D-{k} visible verbatim on load", loc.is_visible())
        pg.goto(BASE + "/sandbox", wait_until="networkidle")
        ok(f"AC-26 {vp} /sandbox D-SIM visible verbatim on load", pg.get_by_text(DIS["sim"], exact=True).first.is_visible())
        # AC-25 rail semantics
        pg.goto(BASE + "/architecture", wait_until="networkidle")
        arch_labels = {
          "conventional-ac": ["Utility Grid","Substation","MV Switchgear","UPS + Battery Plant","AC Distribution","Rack PSUs","AI Servers"],
        }
        for opt in ["conventional-ac", "ac-to-800vdc", "mv-to-800vdc"]:
            pg.locator(f"label:has([data-testid='rail-option-{opt}'])").click()
            labels = pg.eval_on_selector_all("[data-testid=signal-path-rail] li", "els=>els.map(e=>e.textContent.trim())")
            name = pg.get_attribute("[data-testid=signal-path-rail]", "aria-label")
            has_sst = any("Solid-State" in l for l in labels)
            ok(f"AC-25 {vp} rail {opt}: SST node only in conceptual SST architecture", has_sst == (opt == "mv-to-800vdc"), labels)
            ok(f"AC-25 {vp} rail {opt}: accessible name lists node sequence", all(l in name for l in labels), name[:140])
        rh = pg.evaluate("()=>document.querySelector('[data-testid=signal-path-rail]').getBoundingClientRect().height")
        sw = pg.evaluate("()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth]")
        ok(f"AC-25 {vp} rail compact, no page overflow", sw[0] == sw[1] and (vp == "desktop" or rh < 160), f"height {rh:.0f}px {sw}")
        pg.goto(BASE + "/sandbox", wait_until="networkidle")
        dashed = pg.eval_on_selector_all("[data-testid=signal-path-rail] li span.border-dashed", "els=>els.map(e=>e.textContent.trim())")
        ok(f"AC-25 {vp} /sandbox rail pinned to SST arch with dashed simulated nodes + legend", dashed == ["Solid-State Transformer","800 VDC Distribution","AI Servers"] and pg.is_visible("[data-testid=rail-legend]"), dashed)
        # AC-27 type tiers
        for path in ["/", "/system-map", "/architecture", "/sandbox"]:
            pg.goto(BASE + path, wait_until="networkidle")
            h1 = pg.evaluate("()=>[...document.querySelectorAll('h1')].map(e=>({t:e.textContent,fs:getComputedStyle(e).fontSize,fw:getComputedStyle(e).fontWeight}))")
            exp = "40px" if vp == "desktop" else "28px"
            ok(f"AC-27 {vp} {path}: one h1, {exp}, weight 600", len(h1) == 1 and h1[0]["fs"] == exp and h1[0]["fw"] == "600", h1)
        # AC-16 axe on key pages
        for path in ["/", "/system-map", "/architecture", "/sandbox"]:
            pg.goto(BASE + path, wait_until="networkidle"); pg.wait_for_timeout(1200)
            pg.add_script_tag(path=AXE)
            r = pg.evaluate("async()=>{const r=await axe.run(document,{resultTypes:['violations']});return r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,t:v.nodes[0].target.join(' ').slice(0,80)}))}")
            bad = [v for v in r if v["impact"] in ("critical", "serious")]
            ok(f"AC-16 {vp} {path}: axe no critical/serious violations", not bad, bad or f"{len(r)} minor/moderate: {[v['id'] for v in r]}")
        # AC-5 handoffs
        for path, href in [("/system-map", "/architecture"), ("/architecture", "/learn"), ("/sandbox", "/architecture")]:
            pg.goto(BASE + path, wait_until="networkidle")
            ok(f"AC-5 {vp} {path} next-step link to {href}", pg.locator(f"main header a[href='{href}']").count() >= 1)
        pg.goto(BASE + "/", wait_until="networkidle")
        ok(f"AC-5 {vp} / shows ordered path and Industry as planned text (not a link)", pg.locator("main ol li").count() == 4 and pg.locator("a[href='/industry']").count() == 0)
        # AC-17 element-level inside viewport or inside labeled scroller (390 only)
        if vp == "mobile":
            for path in ["/system-map", "/architecture", "/sandbox"]:
                pg.goto(BASE + path, wait_until="networkidle"); pg.wait_for_timeout(1200)
                r = pg.evaluate("""()=>{const W=document.documentElement.clientWidth;const bad=[];
                  const scrollers=[...document.querySelectorAll('[role=region][tabindex="0"]')];
                  document.querySelectorAll('main *').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||getComputedStyle(e).position==='fixed')return;
                    if(r.right>W+1){ if(!scrollers.some(s=>s.contains(e)&&s!==e)) bad.push(e.tagName+'.'+String(e.className).slice(0,40)+' right='+Math.round(r.right)); }});
                  const bareScrollers=scrollers.filter(s=>s.scrollWidth>s.clientWidth+1 && !(s.getAttribute('aria-label')||'').length).length;
                  const hints=scrollers.filter(s=>s.scrollWidth>s.clientWidth+1).map(s=>!!s.parentElement.querySelector('[data-testid=scroll-hint]'));
                  return {bad:bad.slice(0,6),n:bad.length,bareScrollers,hints}}""")
                ok(f"AC-17 {path}: every element inside viewport or a named scroller; scrollers show a hint", r["n"] == 0 and r["bareScrollers"] == 0 and all(r["hints"]), r)
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
print("FAILS:", sum(1 for r in res if r["result"] == "FAIL"))
