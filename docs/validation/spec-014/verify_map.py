"""AC-18 (Q6): in every lane that renders arrows, exactly one arrow per adjacent node pair, in all 3 views (desktop)."""
import glob, json, os, sys
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1], sys.argv[2]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.goto(BASE + "/system-map", wait_until="networkidle"); pg.wait_for_timeout(1000)
    n_views = pg.locator("[role=radiogroup][aria-label='Architecture view'] [role=radio], [role=radiogroup][aria-label='Architecture view'] button").count()
    for i in range(n_views):
        pg.locator("[role=radiogroup][aria-label='Architecture view'] [role=radio], [role=radiogroup][aria-label='Architecture view'] button").nth(i).click(); pg.wait_for_timeout(300)
        lanes = pg.evaluate("""()=>[...document.querySelectorAll('[role=group]')].filter(g=>g.querySelector('button[aria-pressed]')).map(g=>({lane:g.getAttribute('aria-label'),nodes:g.querySelectorAll('button[aria-pressed]').length,arrows:g.querySelectorAll('svg path[d^="M1 5h9"]').length}))""")
        for l in lanes:
            exp = 0 if l["lane"].lower().startswith("monitor") else l["nodes"] - 1
            res.append({"view": i, **l, "expected": exp, "result": "PASS" if l["arrows"] == exp else "FAIL"})
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
for r in res: print(r["result"], r)
