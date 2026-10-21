"""Structured captures for preservation checks (SPEC-014 AC-4, AC-11, AC-13-15, AC-28).
Run against the base commit server and the branch server; compare with compare_rich.py.
Usage: python capture_rich.py BASE_URL OUT.json [after]"""
import glob, json, os, re, sys
from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1], sys.argv[2]
AFTER = len(sys.argv) > 3 and sys.argv[3] == "after"
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
norm = lambda t: re.sub(r"\s+", " ", t.strip().lower())
def lines(t): return [norm(x) for x in t.split("\n") if norm(x)]
out = {"arch": {}, "learn": {}, "charts": {}, "api": {}}

GROUPS = {"driver": "[data-testid^='driver-rd']", "compare": "[data-testid^='compare-rd']", "boundary": "[data-testid^='boundary-']:not([data-testid^='boundary-option'])",
          "decision": "[data-testid^='decision-card-']", "validation": "[data-testid^='validation-']"}

PAGE_LINES = set()

def group_text(pg):
    PAGE_LINES.update(lines(pg.inner_text("main")))
    res = {}
    for g, sel in GROUPS.items():
        res[g] = {}
        for el in pg.query_selector_all(sel):
            res[g][el.get_attribute("data-testid")] = lines(el.inner_text())
    res["references"] = lines(pg.inner_text("#references")) if pg.query_selector("#references") else lines(pg.inner_text("section:has(h2:text-is('References'))"))
    res["evidence_tags"] = sorted(norm(e.inner_text()) for e in pg.query_selector_all("main p.border-t.border-hairline"))
    return res

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    apis = []
    def on_resp(r):
        if "/simulations/" in r.url:
            try: apis.append((r.url, r.json()))
            except Exception: pass
    pg.on("response", on_resp)

    # ---- Architecture
    pg.goto(BASE + "/architecture", wait_until="networkidle")
    if AFTER:
        union = {}
        def merge(dst, src):
            for g, v in src.items():
                if isinstance(v, dict):
                    dst.setdefault(g, {}).update(v)
                else:
                    dst[g] = sorted(set(dst.get(g, [])) | set(v)) if isinstance(v, list) else v
        for i in range(1, 8):  # every driver selection in the default view
            pg.locator(f"label:has([data-testid='driver-option-rd{i}'])").click(); pg.wait_for_timeout(100)
            merge(union, group_text(pg))
        pg.click("[data-testid='show-all-drivers']"); pg.click("[data-testid='show-all-boundaries']"); pg.wait_for_timeout(300)
        merge(union, group_text(pg))
        out["arch"] = union
    else:
        un = {}
        for i in range(1, 8):
            pg.locator(f"label:has([data-testid='driver-option-rd{i}'])").click(); pg.wait_for_timeout(100)
            gt = group_text(pg)
            un.setdefault("decision", {}).update(gt["decision"])
            if i == 1: un.update({k: v for k, v in gt.items() if k != "decision"})
        out["arch"] = un
    out["arch"]["_page_lines"] = sorted(PAGE_LINES)
    out["arch"]["disclosures_visible"] = [norm(t) for t in [e.inner_text() for e in pg.query_selector_all("[data-testid='disclosures'] li")]]

    # ---- Learn: five cases
    pg.goto(BASE + "/learn", wait_until="networkidle"); pg.wait_for_timeout(1500)
    n = pg.locator("label:has([data-testid^=case-option])").count()
    for i in range(n):
        pg.locator("label:has([data-testid^=case-option])").nth(i).click(); pg.wait_for_timeout(1500)
        prev = None
        for _ in range(20):  # wait until the live charts have stopped changing (large series render late)
            cur = pg.evaluate("()=>[...document.querySelectorAll('main svg polyline')].map(e=>(e.getAttribute('points')||'').length).join(',')")
            if cur == prev and cur: break
            prev = cur; pg.wait_for_timeout(500)
        out["learn"][f"case{i+1}"] = {
            "text": lines(pg.inner_text("main")),
            "links": sorted(a.get_attribute("href") for a in pg.query_selector_all("main a")),
            "evidence_html": sorted(e.evaluate("x=>x.outerHTML") for e in pg.query_selector_all("main p.border-t.border-hairline")),
            "chart_points": [e.get_attribute("points") for e in pg.query_selector_all("main svg polyline")],
        }

    # ---- Sandbox charts per scenario + the default API response
    pg.goto(BASE + "/sandbox", wait_until="networkidle"); pg.wait_for_timeout(1500)
    for sc in ["load_step", "sustained_high_load", "thermal_trip", "grid_sag", "grid_loss"]:
        pg.click(f"[data-testid='scenario-option-{sc}']"); pg.wait_for_timeout(1800)
        out["charts"][sc] = {
            "polylines": [e.get_attribute("points") for e in pg.query_selector_all("main svg polyline")],
            "ticks": [norm(e.text_content()) for e in pg.query_selector_all("main svg text")],
        }
    out["api"] = {u: j for u, j in apis if "load-step" in u or "protection-scenarios" in u}
    b.close()
json.dump(out, open(OUT, "w"))
print("ok", {k: len(v) for k, v in out.items()})
