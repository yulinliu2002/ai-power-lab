"""AC-15: /learn at 375x812 and 1280x800 after SPEC-014 token/shared-component changes: loads, console clean, no overflow, screenshots."""
import glob, os, sys, json
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1], sys.argv[2]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    for vp, (w, h) in {"375": (375, 812), "1280": (1280, 800)}.items():
        pg = b.new_context(viewport={"width": w, "height": h}).new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE + "/learn", wait_until="networkidle"); pg.wait_for_timeout(1500)
        cases = pg.locator("[data-testid^=case-option]").count()
        for i in range(cases):
            pg.locator("label:has([data-testid^=case-option])").nth(i).click(); pg.wait_for_timeout(1800)
            ov = pg.evaluate("()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth]")
            pg.screenshot(path=f"{OUT}/shots/learn-{vp}-case{i+1}.png", full_page=True)
            res.append({"vp": vp, "case": i + 1, "overflow": ov, "console_problems": len(errs), "result": "PASS" if ov[0] == ov[1] and not errs else "FAIL"})
    b.close()
json.dump(res, open(OUT + "/learn_regression.json", "w"), indent=1)
for r in res: print(r)
