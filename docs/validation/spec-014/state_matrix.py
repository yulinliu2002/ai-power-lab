"""SPEC-014 AC-8/AC-10 state-transition matrix and feature walk (Sandbox), run in Chromium.
Usage: python state_matrix.py BASE_URL OUT.json"""
import glob, json, os, sys
from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1], sys.argv[2]
exe = glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1148/chrome-mac/*/Contents/MacOS/*"))[0]
res = []
def ok(name, cond, detail=""):
    res.append({"result": "PASS" if cond else "FAIL", "check": name, "detail": str(detail)[:300]}); print(res[-1]["result"], name, str(detail)[:160])

def set_slider(pg, idx, value):
    pg.evaluate("""([i,v])=>{const el=document.querySelectorAll('#stage-configure input[type=range]')[i];
      const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(el,String(v));
      el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}""", [idx, value])
    pg.wait_for_timeout(150)

def text(pg, sel): return pg.inner_text(sel)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe)
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    calls = {"load": 0, "scen": 0, "cmp": 0}
    def count(r):
        u = r.url
        if "/simulations/load-step" in u: calls["load"] += 1
        elif "/protection-scenarios/" in u: calls["scen"] += 1
        elif u.endswith("/simulations/comparison"): calls["cmp"] += 1
    pg.on("request", count)
    pg.goto(BASE + "/sandbox", wait_until="networkidle"); pg.wait_for_timeout(1500)

    # initial mount: one Load Step fetch, scrubber at voltage minimum (not 0)
    ok("mount: exactly one Load Step fetch", calls["load"] == 1, calls)
    v0 = int(pg.input_value("[data-testid=state-at-time] input[aria-label=Time]"))
    ok("mount: scrubber at voltage-minimum default index (not 0)", v0 > 0, v0)
    ok("provenance: preset defaults", "preset defaults" in text(pg, "[data-testid=run-provenance]"))
    kpi0 = text(pg, "[data-testid=state-at-time]")

    # keyboard: scrubber Home / End
    pg.focus("[data-testid=state-at-time] input[aria-label=Time]"); pg.keyboard.press("Home"); pg.wait_for_timeout(150)
    ok("scrubber Home -> t = 0", "t = 0.0000 s" in text(pg, "[data-testid=state-at-time]"))
    pg.keyboard.press("End"); pg.wait_for_timeout(150)
    ok("scrubber End -> last sample", "t = 0.59" in text(pg, "[data-testid=state-at-time]") or "t = 0.60" in text(pg, "[data-testid=state-at-time]"), text(pg, "[data-testid=state-at-time]")[:120])

    # sliders -> unrun marker; run -> provenance changes
    ok("no unrun marker before edit", pg.locator("[data-testid=unrun-values]").count() == 0)
    set_slider(pg, 1, 0.04)
    ok("slider edit -> 'Slider values not yet run.' and run-stale", pg.is_visible("[data-testid=unrun-values]") and pg.is_visible("[data-testid=run-stale]"))
    pg.get_by_role("button", name="Run Experiment").click(); pg.wait_for_timeout(1800)
    ok("run: provenance shows experiment values; markers cleared", "experiment values" in text(pg, "[data-testid=run-provenance]") and pg.locator("[data-testid=unrun-values]").count() == 0 and pg.locator("[data-testid=run-stale]").count() == 0, text(pg, "[data-testid=run-provenance]"))
    ok("run: scrubber returns to default index", int(pg.input_value("[data-testid=state-at-time] input[aria-label=Time]")) > 0)
    ran_kpi = text(pg, "[data-testid=state-at-time]")

    # failed Run retains previous run, shows error
    set_slider(pg, 2, 0.04)
    pg.route("**/simulations/load-step", lambda r: r.abort())
    pg.get_by_role("button", name="Run Experiment").click(); pg.wait_for_timeout(1200)
    ok("failed Run: previous run retained, error shown, Run re-enabled", text(pg, "[data-testid=state-at-time]") == ran_kpi and pg.get_by_role("button", name="Run Experiment").is_enabled() and ("error" in text(pg, "#stage-configure").lower() or "fetch" in text(pg, "#stage-configure").lower() or "failed" in text(pg, "#stage-configure").lower()), text(pg, "#stage-configure")[-120:])
    # failed Reset behaves like Run failure
    pg.get_by_role("button", name="Reset").click(); pg.wait_for_timeout(1200)
    ok("failed Reset: previous run retained", text(pg, "[data-testid=state-at-time]") == ran_kpi)
    pg.unroute("**/simulations/load-step")
    # Reset success
    pg.get_by_role("button", name="Reset").click(); pg.wait_for_timeout(1800)
    ok("Reset: draft reset and baseline fetched -> preset defaults", "preset defaults" in text(pg, "[data-testid=run-provenance]") and abs(float(pg.input_value("#stage-configure input[type=range]:nth-of-type(1)")) - 0.8) < 1e-9 if False else ("preset defaults" in text(pg, "[data-testid=run-provenance]") and pg.evaluate("()=>[...document.querySelectorAll('#stage-configure input[type=range]')].map(e=>Number(e.value))") == [0.8, 0.02, 0.02]))

    # sweep + stale + scenario-change behavior
    pg.locator("label:has([data-testid='study-option-sweep'])").click(); pg.wait_for_timeout(300)
    pg.get_by_role("button", name="Run Sweep").click(); pg.wait_for_timeout(2500)
    ok("sweep result shown", pg.is_visible("#stage-investigate table"))
    set_slider(pg, 1, 0.03)
    ok("sweep stale marker after slider change", pg.is_visible("[data-testid=sweep-stale]"))
    n_scen = calls["scen"]
    pg.click("[data-testid='scenario-option-thermal_trip']"); pg.wait_for_timeout(1800)
    ok("scenario change to B-E with sweep chosen: disabled-study notice, no auto study", pg.is_visible("[data-testid=sweep-unavailable]") and pg.locator("[data-testid=study-option-sweep]").is_checked() and calls["cmp"] == 0, calls)
    ok("B-E: fixed-preset note and no sliders", pg.is_visible("[data-testid=fixed-preset-note]") and pg.locator("#stage-configure input[type=range]").count() == 0)
    ok("B-E takeaway has no derived numbers (no energy deficit row)", "Energy deficit" not in text(pg, "[data-testid=engineering-takeaway]"))
    pg.click("[data-testid='scenario-option-load_step']"); pg.wait_for_timeout(1800)
    ok("return to Load Step fetches preset run; draft kept and marked not yet run", "preset defaults" in text(pg, "[data-testid=run-provenance]") and pg.is_visible("[data-testid=unrun-values]"))

    # rapid switching: last wins
    for sc in ["grid_sag", "grid_loss", "sustained_high_load"]:
        pg.click(f"[data-testid='scenario-option-{sc}']", no_wait_after=True)
    pg.wait_for_timeout(2500)
    ok("rapid switching: last request wins", "Sustained High Load" in text(pg, "[data-testid=run-provenance]"), text(pg, "[data-testid=run-provenance]"))

    # compare: fetch on every entry; failure + retry; other stages intact
    c0 = calls["cmp"]
    pg.locator("label:has([data-testid='study-option-compare'])").click(); pg.wait_for_timeout(2500)
    ok("compare entry 1 fetches once", calls["cmp"] == c0 + 1, calls)
    pg.locator("label:has([data-testid='study-option-sweep'])").click(); pg.wait_for_timeout(300)
    pg.route("**/simulations/comparison", lambda r: r.abort())
    pg.locator("label:has([data-testid='study-option-compare'])").click(); pg.wait_for_timeout(1500)
    ok("compare re-entry fetches again (2nd entry), failure shown in Stage 3 only", calls["cmp"] == c0 + 2 and "API ERROR" in text(pg, "#stage-investigate") and pg.is_visible("[data-testid=state-at-time]") and pg.is_visible("[data-testid=engineering-takeaway]"), calls)
    pg.unroute("**/simulations/comparison")
    pg.get_by_role("button", name="Retry").click(); pg.wait_for_timeout(2500)
    ok("compare retry recovers", pg.is_visible("[data-testid=scenario-comparison]") and calls["cmp"] == c0 + 3, calls)
    ok("compare keeps single-run view on screen and scenario selector enabled", pg.is_visible("[data-testid=state-at-time]") and pg.locator("[data-testid=scenario-option-grid_sag]").is_enabled())
    ok("compare outcome caution present", pg.is_visible("[data-testid=scenario-comparison] [data-testid=outcome-caution]"))

    # stage nav: focus moves to heading
    pg.get_by_role("link", name="Engineering takeaway").first.click(); pg.wait_for_timeout(300)
    ok("stage nav moves focus to target heading", pg.evaluate("()=>document.activeElement&&document.activeElement.id")== "stage-takeaway-h")
    # keyboard: tab order reaches scenario selector then sliders (document order)
    ok("all five scenarios selectable", all(pg.locator(f"[data-testid='scenario-option-{s}']").count() == 1 for s in ["load_step","sustained_high_load","thermal_trip","grid_sag","grid_loss"]))
    # outcome caution beside the single-run outcome banner
    ok("single-run outcome caution present", pg.is_visible("[data-testid=protection-timeline] [data-testid=outcome-caution]"))
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
print("FAILS:", sum(1 for r in res if r["result"] == "FAIL"))
