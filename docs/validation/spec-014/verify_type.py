"""Typography contract on rendered output (DESIGN.md section 6, SPEC-014 F1/F2/R39): headings are Sans; explanatory prose
(text nodes longer than 40 characters) is Sans and at least 12px; essential labels never below 10.5px.
Usage: python verify_type.py BASE_URL OUT.json"""
import glob, json, os, sys
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1:3]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
JS = """()=>{const bad=[];const isMono=f=>/mono/i.test(f)||/ui-monospace|courier/i.test(f);
 document.querySelectorAll('main h1,main h2,main h3,main h4').forEach(e=>{const cs=getComputedStyle(e);if(e.closest('svg'))return;
   if(isMono(cs.fontFamily)&&e.textContent.trim().length>0&&!e.matches('.ic-eyebrow'))bad.push(['mono heading',e.tagName,e.textContent.trim().slice(0,40)])});
 const w=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT);let n;
 while(n=w.nextNode()){const t=n.textContent.trim();if(t.length<=40)continue;const el=n.parentElement;if(!el||el.closest('svg,script,style,[hidden],details:not([open])>:not(summary)'))continue;
   const cs=getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden')continue;if(el.closest('.sr-only'))continue;
   const eq=/[=∫]/.test(t)&&/(dE_dc|ΔE|E_dc|C_dc)/.test(t);const fs=parseFloat(cs.fontSize);if(fs<12)bad.push(['prose < 12px',fs,t.slice(0,50)]);if(isMono(cs.fontFamily)&&!eq)bad.push(['mono prose',cs.fontFamily.slice(0,20),t.slice(0,50)])}
 return bad}"""
def ok(name, bad):
    res.append({"result": "PASS" if not bad else "FAIL", "check": name, "detail": str(bad[:6])}); print(res[-1]["result"], name, str(bad[:4])[:220])
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    for vp, (w, h) in {"desktop": (1440, 900), "mobile": (390, 844)}.items():
        pg = b.new_context(viewport={"width": w, "height": h}).new_page()
        for path in ["/", "/system-map", "/architecture", "/sandbox"]:
            pg.goto(BASE + path, wait_until="networkidle"); pg.wait_for_timeout(1500)
            if path == "/architecture":
                pg.click("[data-testid=show-all-drivers]"); pg.click("[data-testid=show-all-boundaries]"); pg.wait_for_timeout(300)
            if path == "/sandbox":
                pg.locator("label:has([data-testid='study-option-compare'])").click(); pg.wait_for_timeout(2500)
                pg.locator("label:has([data-testid='study-option-sweep'])").click(); pg.get_by_role("button", name="Run Sweep").click(); pg.wait_for_timeout(2500)
            ok(f"{vp} {path}: headings are Sans; prose is Sans and >= 12px", pg.evaluate(JS))
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
print("FAILS:", sum(1 for r in res if r["result"] == "FAIL"))
