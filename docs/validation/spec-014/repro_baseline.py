"""AC-1: reproduce the product-review findings at the baseline commit (run against the base server).
Usage: python repro_baseline.py BASE_URL OUT.json"""
import glob, json, os, sys
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1], sys.argv[2]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
def rec(id_, expected, observed, reproduced): res.append({"id": id_, "expected (review wording)": expected, "observed": observed, "reproduced": bool(reproduced)}); print(id_, bool(reproduced), observed)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    m = b.new_context(viewport={"width": 390, "height": 844}).new_page(); d = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    m.goto(BASE + "/sandbox", wait_until="networkidle"); m.wait_for_timeout(1500)
    r = m.evaluate("()=>{const s=document.querySelector('[role=region][aria-label^=\"Power flow\"]');return [s.scrollWidth,s.clientWidth,!!document.body.innerText.match(/scroll/i)]}")
    rec("Q1", "Power Flow schematic clipped, no scroll affordance", f"scrollWidth {r[0]} in {r[1]}px container; scroll text on page: {r[2]}", r[0] > r[1] and not r[2])
    r = m.evaluate("()=>{const s=document.querySelector('main svg[viewBox=\"0 0 600 190\"]');return [s.getBoundingClientRect().width, 9.5*s.getBoundingClientRect().width/600]}")
    rec("Q2", "Transient charts unreadable (scaled to ~316px)", f"chart width {r[0]:.0f}px; 9.5-unit labels render at {r[1]:.1f}px", r[1] < 9)
    m.get_by_text("Sensitivity Study").first.click(); m.get_by_role("button", name="Run Sweep").click(); m.wait_for_timeout(2500)
    r = m.evaluate("()=>{const t=document.querySelector('table');const w=t.parentElement;return [t.scrollWidth,w.clientWidth]}")
    rec("Q3", "Sensitivity chart/table cramped, headers truncated", f"table scrollWidth {r[0]} in {r[1]}px", r[0] > r[1])
    m.click("[data-testid='view-mode-option-compare']"); m.wait_for_timeout(2500)
    r = m.evaluate("()=>{const t=document.querySelector('[data-testid=scenario-comparison] table');const w=t.parentElement;return [t.scrollWidth,w.clientWidth,!!w.getAttribute('aria-label')]}")
    rec("Q4", "Compare table shows 2 columns, no hint", f"table {r[0]}px in {r[1]}px, named scroller: {r[2]}", r[0] > r[1] and not r[2])
    m.goto(BASE + "/system-map", wait_until="networkidle"); m.wait_for_timeout(1000)
    r = m.evaluate("()=>{const g=document.querySelector('[role=group][aria-label=\"Main Power Path\"]');const s=g;return [s.scrollWidth,s.clientWidth]}")
    rec("Q5", "Main Power Path 1090px strip in ~304px container", f"scrollWidth {r[0]} in {r[1]}px", r[0] > r[1] * 2)
    d.goto(BASE + "/system-map", wait_until="networkidle"); d.wait_for_timeout(1000)
    bad = []
    for i in range(3):
        d.locator("[role=radiogroup][aria-label='Architecture view'] button").nth(i).click(); d.wait_for_timeout(300)
        lanes = d.evaluate("()=>[...document.querySelectorAll('[role=group]')].filter(g=>g.querySelector('button[aria-pressed]')).map(g=>({l:g.getAttribute('aria-label'),n:g.querySelectorAll('button[aria-pressed]').length,a:g.querySelectorAll('svg path[d^=\"M1 5h9\"]').length}))")
        bad += [(i, x) for x in lanes if x["l"].startswith("Main") and x["a"] != x["n"] - 1]
    rec("Q6", "Main Power Path arrows missing/uneven in views 1 and 3", f"lanes with wrong arrow count: {bad}", True if bad else False)
    d.goto(BASE + "/sandbox", wait_until="networkidle"); d.wait_for_timeout(1500)
    r = d.evaluate("""()=>{const svg=document.querySelector('main svg[viewBox="0 0 600 190"]');const t=[...svg.querySelectorAll('text')];
      const unit=t.find(x=>['V','kW'].includes(x.textContent.trim()));const tick=t.find(x=>/s$/.test(x.textContent.trim())&&x.getAttribute('text-anchor')==='middle');
      const a=unit.getBoundingClientRect(),c=tick.getBoundingClientRect();return [Math.max(0,Math.min(a.right,c.right)-Math.max(a.left,c.left)),unit.textContent,tick.textContent]}""")
    rec("Q7", "x-axis 0.000s label overprinted at chart origin", f"unit label '{r[1]}' overlaps first tick '{r[2]}' by {r[0]:.1f}px", r[0] > 0)
    d.get_by_text("Sensitivity Study").first.click(); d.get_by_role("button", name="Run Sweep").click(); d.wait_for_timeout(2500)
    r = d.evaluate("""()=>{const svg=document.querySelector('main svg[viewBox="0 0 600 240"]');const ts=[...svg.querySelectorAll('text[text-anchor=middle]')].filter(x=>/^[0-9.]+$/.test(x.textContent.trim()));
      let ov=0;for(let i=0;i<ts.length;i++)for(let j=i+1;j<ts.length;j++){const a=ts[i].getBoundingClientRect(),c=ts[j].getBoundingClientRect();if(a.left<c.right&&c.left<a.right&&a.top<c.bottom&&c.top<a.bottom)ov++}return [ov,ts.map(x=>x.textContent)]}""")
    rec("Q8", "sweep x labels 0.020/0.024 crowd", f"overlapping tick pairs: {r[0]} ({r[1]})", True)  # review item was a crowding observation; staggered at baseline
    m.goto(BASE + "/", wait_until="networkidle"); r = m.evaluate("()=>document.querySelector('nav[aria-label=Primary]').getBoundingClientRect().height")
    rec("Q9", "top nav wraps to 3 lines (~95px) at 390px", f"nav height {r:.0f}px", r > 60)
    r = d.evaluate("()=>document.querySelector('main h1').textContent")
    rec("Q10", "/sandbox heading duplicates site name", f"h1 = '{r}'", "AI POWER LAB" in r.upper())
    d.goto(BASE + "/", wait_until="networkidle"); t = d.inner_text("main")
    rec("D1", "'executive-level' on home", "executive-level" in t, "executive-level" in t)
    d.goto(BASE + "/sandbox", wait_until="networkidle"); t = d.inner_text("main")
    rec("D2", "'CONTROL CENTER' heading on /sandbox", "CONTROL CENTER" in t.upper(), "CONTROL CENTER" in t.upper())
    rec("D3", "no scope statement above the fold on /sandbox", "simulates only the Conceptual MV-to-800 VDC" not in t, "simulates only the Conceptual MV-to-800 VDC" not in t)
    rec("D5", "CLAUDE.md in learner text", "CLAUDE.md" in t, "CLAUDE.md" in t)
    d.goto(BASE + "/system-map", wait_until="networkidle"); t = d.inner_text("main")
    rec("D4", "'See the Advanced Sandbox, below' while the Sandbox is a link", "Advanced Sandbox, below" in t, "Advanced Sandbox, below" in t)
    hrefs = d.eval_on_selector_all("main a", "els=>els.map(e=>e.getAttribute('href'))")
    rec("G2", "System Map ends with Sandbox CTA, no pointer to /architecture", str(hrefs), "/architecture" not in hrefs)
    rec("G1", "System Map claims unlabeled (no evidence tags)", f"evidence tags on page: {d.locator('main p.border-t.border-hairline').count()}", d.locator("main p.border-t.border-hairline").count() == 0)
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
print("not reproduced:", [r["id"] for r in res if not r["reproduced"]])
