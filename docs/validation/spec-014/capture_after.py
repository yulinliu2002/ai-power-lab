"""SPEC-014 'after' capture: the same fixed interaction script as capture_baseline.py,
adapted to the new controls (study chooser instead of view-mode toggle; parameter
panel and sweep always visible). Usage: python capture_after.py BASE_URL OUTDIR
"""
import glob, hashlib, json, os, sys
from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT + "/shots", exist_ok=True)
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
result = {"problems": [], "states": {}, "api": []}

def testids(pg):
    return sorted(pg.evaluate("()=>[...document.querySelectorAll('[data-testid]')].map(e=>e.getAttribute('data-testid'))"))

def snap(pg, name, vp):
    pg.screenshot(path=f"{OUT}/shots/{name}-{vp}.png", full_page=True)
    ov = pg.evaluate("()=>({sw:document.documentElement.scrollWidth,W:document.documentElement.clientWidth})")
    result["states"][f"{name}-{vp}"] = {"testids": testids(pg), "text": pg.inner_text("main"), "overflow": ov}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    for vp, (w, h) in {"desktop": (1440, 900), "mobile": (390, 844)}.items():
        ctx = b.new_context(viewport={"width": w, "height": h})
        pg = ctx.new_page()
        pg.on("console", lambda m, v=vp: result["problems"].append([v, pg.url, "console." + m.type, m.text]) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e, v=vp: result["problems"].append([v, pg.url, "pageerror", str(e)]))
        pg.on("requestfailed", lambda r, v=vp: result["problems"].append([v, pg.url, "reqfailed", r.url]))
        def on_resp(r, v=vp):
            if r.status >= 400:
                result["problems"].append([v, pg.url, f"http{r.status}", r.url])
            if ":8100" in r.url or ":8000" in r.url:
                try:
                    body = r.body()
                except Exception:
                    body = b""
                result["api"].append([v, r.request.method, r.url.split("//")[1].split("/", 1)[1], r.request.post_data or "", hashlib.sha256(body).hexdigest()[:16]])
        pg.on("response", on_resp)
        for path, slug in [("/", "home"), ("/system-map", "system-map"), ("/learn", "learn"), ("/architecture", "architecture"), ("/sandbox", "sandbox")]:
            pg.goto(BASE + path, wait_until="networkidle"); pg.wait_for_timeout(1500)
            snap(pg, slug, vp)
        pg.goto(BASE + "/architecture", wait_until="networkidle")
        for i in range(1, 8):
            pg.locator(f"label:has([data-testid='driver-option-rd{i}'])").click()
            pg.wait_for_timeout(150)
            result["states"][f"arch-driver-rd{i}-{vp}"] = {"testids": testids(pg), "text": pg.inner_text(f"[data-testid='decision-card-rd{i}']")}
        pg.click("[data-testid='show-all-drivers']"); pg.click("[data-testid='show-all-boundaries']"); pg.wait_for_timeout(300)
        snap(pg, "architecture-show-all", vp)
        pg.goto(BASE + "/sandbox", wait_until="networkidle"); pg.wait_for_timeout(1500)
        for sc in ["load_step", "sustained_high_load", "thermal_trip", "grid_sag", "grid_loss"]:
            pg.click(f"[data-testid='scenario-option-{sc}']"); pg.wait_for_timeout(1800)
            snap(pg, f"sandbox-{sc}", vp)
        pg.click("[data-testid='scenario-option-load_step']"); pg.wait_for_timeout(1800)
        pg.get_by_role("button", name="Run Experiment").click(); pg.wait_for_timeout(1800)
        snap(pg, "sandbox-experiment-run", vp)
        pg.locator("label:has([data-testid='study-option-sweep'])").click(); pg.wait_for_timeout(400)
        pg.get_by_role("button", name="Run Sweep").click(); pg.wait_for_timeout(2500)
        snap(pg, "sandbox-sweep-run", vp)
        pg.locator("label:has([data-testid='study-option-compare'])").click(); pg.wait_for_timeout(2500)
        snap(pg, "sandbox-compare", vp)
        ctx.close()
    b.close()
json.dump(result, open(OUT + "/capture.json", "w"), indent=1)
print("problems:", len(result["problems"]), "states:", len(result["states"]), "api:", len(result["api"]))
for pr in result["problems"][:10]:
    print(pr)
