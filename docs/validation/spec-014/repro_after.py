"""AC-17/AC-18/AC-1 counterpart: re-measure the baseline findings on the branch. Usage: python repro_after.py BASE_URL OUT.json"""
import glob, json, os, sys
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1], sys.argv[2]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
def rec(id_, observed, fixed): res.append({"id": id_, "observed": observed, "fixed": bool(fixed)}); print(id_, bool(fixed), observed)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    m = b.new_context(viewport={"width": 390, "height": 844}).new_page(); d = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    m.goto(BASE + "/sandbox", wait_until="networkidle"); m.wait_for_timeout(1500)
    r = m.evaluate("()=>{const s=document.querySelector('[role=region][aria-label^=\"Power flow\"]');return [s.scrollWidth,s.clientWidth,!!s.parentElement.querySelector('[data-testid=scroll-hint]'),s.tabIndex]}")
    rec("Q1", f"schematic scroller {r[0]}/{r[1]}px, visible hint {r[2]}, focusable tabindex {r[3]}", r[2] and r[3] == 0)
    r = m.evaluate("()=>{const s=document.querySelector('main svg[viewBox=\"0 0 600 190\"]');return [s.getBoundingClientRect().width, 9.5*s.getBoundingClientRect().width/600]}")
    rec("Q2", f"chart drawn at {r[0]:.0f}px wide; 9.5-unit labels render at {r[1]:.1f}px (authored size kept), inside a named scroller", r[1] >= 9.5)
    m.locator("label:has([data-testid='study-option-sweep'])").click(); m.get_by_role("button", name="Run Sweep").click(); m.wait_for_timeout(2500)
    r = m.evaluate("()=>{const t=document.querySelector('#stage-investigate table');const w=t.closest('[role=region]');return [t.scrollWidth,w.clientWidth,w.getAttribute('aria-label'),!!w.parentElement.querySelector('[data-testid=scroll-hint]')]}")
    rec("Q3", f"sweep table {r[0]}px in named scroller '{r[2]}' ({r[1]}px), hint {r[3]}", r[3] and r[2])
    m.locator("label:has([data-testid='study-option-compare'])").click(); m.wait_for_timeout(2500)
    r = m.evaluate("()=>{const t=document.querySelector('[data-testid=scenario-comparison] table');const w=t.closest('[role=region]');return [t.scrollWidth,w.clientWidth,w.getAttribute('aria-label'),!!w.parentElement.querySelector('[data-testid=scroll-hint]'),getComputedStyle(t.querySelector('tbody td')).position]}")
    rec("Q4", f"compare table {r[0]}px in named scroller '{r[2]}', hint {r[3]}, sticky first column: {r[4]}", r[3] and r[4] == "sticky")
    m.goto(BASE + "/system-map", wait_until="networkidle"); m.wait_for_timeout(1000)
    r = m.evaluate("()=>{const g=document.querySelector('[role=region][aria-label^=\"Main Power Path\"]');return [g.scrollWidth,g.clientWidth]}")
    rec("Q5", f"Main Power Path stacked at 390px: scrollWidth {r[0]} = clientWidth {r[1]}", r[0] <= r[1] + 1)
    d.goto(BASE + "/sandbox", wait_until="networkidle"); d.wait_for_timeout(1500)
    r = d.evaluate("""()=>{const svg=document.querySelector('main svg[viewBox="0 0 600 190"]');const t=[...svg.querySelectorAll('text')];
      const unit=t.find(x=>['V','kW'].includes(x.textContent.trim()));const tick=t.find(x=>/s$/.test(x.textContent.trim())&&x.getAttribute('text-anchor')==='middle');
      const a=unit.getBoundingClientRect(),c=tick.getBoundingClientRect();return Math.max(0,Math.min(a.right,c.right)-Math.max(a.left,c.left))*Math.max(0,Math.min(a.bottom,c.bottom)-Math.max(a.top,c.top))}""")
    rec("Q7", f"unit label / first x tick overlap area {r:.1f}px^2", r == 0)
    d.locator("label:has([data-testid='study-option-sweep'])").click(); d.get_by_role("button", name="Run Sweep").click(); d.wait_for_timeout(2500)
    r = d.evaluate("""()=>{const svg=document.querySelector('#stage-investigate svg[viewBox="0 0 600 240"]');const ts=[...svg.querySelectorAll('text[text-anchor=middle]')].filter(x=>/^[0-9.]+$/.test(x.textContent.trim()));
      let ov=0;for(let i=0;i<ts.length;i++)for(let j=i+1;j<ts.length;j++){const a=ts[i].getBoundingClientRect(),c=ts[j].getBoundingClientRect();if(a.left<c.right&&c.left<a.right&&a.top<c.bottom&&c.top<a.bottom)ov++}return ov}""")
    rec("Q8", f"overlapping tick-label pairs: {r}", r == 0)
    m.goto(BASE + "/", wait_until="networkidle"); r = m.evaluate("()=>document.querySelector('nav[aria-label=Primary]').getBoundingClientRect().height")
    rec("Q9", f"nav height {r:.0f}px at 390 (two lines)", r < 60)
    d.goto(BASE + "/sandbox", wait_until="networkidle"); r = d.evaluate("()=>document.querySelector('main h1').textContent")
    rec("Q10", f"h1 = '{r}'", r == "Advanced Sandbox")
    d.goto(BASE + "/", wait_until="networkidle"); t = d.inner_text("main"); rec("D1", "executive-level absent", "executive-level" not in t)
    d.goto(BASE + "/sandbox", wait_until="networkidle"); t = d.inner_text("main")
    rec("D2/D3/D5", "no CONTROL CENTER, scope sentence visible, no CLAUDE.md", "CONTROL CENTER" not in t.upper() and "simulates only the Conceptual MV-to-800 VDC" in t and "CLAUDE.md" not in t)
    d.goto(BASE + "/system-map", wait_until="networkidle"); t = d.inner_text("main")
    rec("D4", "no 'Advanced Sandbox, below'", "Advanced Sandbox, below" not in t)
    hrefs = d.eval_on_selector_all("main a", "els=>els.map(e=>e.getAttribute('href'))"); rec("G2", f"links {hrefs[-3:]}", "/architecture" in hrefs[-3:])
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
print("not fixed:", [r["id"] for r in res if not r["fixed"]])
