"""SPEC-012 amendment A1 browser verification of the four-step /learn shell.

Usage: python3 -I verify_learn_steps.py BASE_URL API_URL OUT_DIR
Checks (each prints PASS/FAIL, exit code 1 on any FAIL):
  S1  six disclosures visible on initial load, before any interaction (AC-6)
  S2  every case x step reachable by click; only the current step is mounted
  S3  AC-4 rendered scan: digits in data-static-prose nodes (equations stripped, R6 allowlist), union over steps = 7 nodes/case
  S4  AC-8: backend strings present verbatim in the Discover step; coverage entries in the Explain step
  S5  switching steps never refetches (one run request + one comparison request per case view)
  S6  keyboard: Tab to a step button, Enter activates it, focus lands on the step heading
  S7  AC-10: API blocked -> static steps render; Discover shows per-request errors; Explain shows coverage unavailable
  S8  rapid case switching with a slowed response ends on the selected case
  S9  1440 and 390 px: no horizontal overflow, console clean, screenshots
"""
import glob, json, os, re, sys, urllib.request
from playwright.sync_api import sync_playwright

BASE, API, OUT = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), sys.argv[3]
os.makedirs(OUT + "/shots", exist_ok=True)
IDS = ["load_step", "sustained_high_load", "thermal_trip", "grid_sag", "grid_loss"]
STEPS = ["predict", "discover", "explain", "apply"]
PARTS = {"predict": ["situation", "predict"], "discover": ["observe", "modeled"], "explain": ["explain", "limits"], "apply": ["not-modeled", "decision", "validation"]}
D_L = [
    "These cases run the five fixed Sandbox scenarios on a simplified average-value model. Results show how the model behaves under stated illustrative assumptions, not how real equipment behaves.",
    "In the grid-sag, grid-loss and thermal-trip cases, 'bus collapse' means the integrator reached its numerical energy floor. It is not a physically meaningful residual voltage.",
    "Real-world fault behavior listed under 'not modeled' is described from public sources or general engineering principle. It is not simulated here, and no result on this page validates it.",
]
def _src(rel, key):
    m = re.search(key + r':\s*\n?\s*"((?:[^"\\]|\\.)*)"', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../frontend/app/lib", rel)).read())
    return m.group(1).replace('\\"', '"')
SRC_D = [_src("architectureChoicesData.ts", k) for k in ("sim", "block", "illustrative")]
norm = lambda s: re.sub(r"\s+", " ", s)
strip = lambda t: re.sub(r"\bOCP(?:WP|SST)?\b", "", re.sub(r"\bRD[1-7]\b", "", re.sub(r"\bv[\d.]+", "", re.sub(r"\bRev [\d.]+", "", re.sub(r"§[\d.]+(?:[–-][\d.]+)?", "", t)))))
res = []
def rec(check, ok, detail=""):
    res.append({"check": check, "result": "PASS" if ok else "FAIL", "detail": detail})
    print(("PASS " if ok else "FAIL ") + check, detail)

def get(path, body=None):
    req = urllib.request.Request(API + path, data=body, headers={"Content-Type": "application/json"} if body is not None else {})
    return json.load(urllib.request.urlopen(req))

cmp = get("/api/v1/simulations/comparison")
def truth(i):
    run = get("/api/v1/simulations/load-step", b"{}") if i == "load_step" else get("/api/v1/simulations/protection-scenarios/" + i)
    return run["protection_timeline"], next(e for e in cmp["scenarios"] if e["scenario"] == i)["stress_profile"]

def step(pg, s):
    pg.locator(f'[data-testid="step-tab-{s}"]').click(); pg.wait_for_timeout(150)

def pick(pg, i):
    pg.locator(f'label:has([data-testid="case-option-{i}"])').click()

exe = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe[0] if exe else None)
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    reqs = []
    pg.on("request", lambda r: reqs.append(r.url) if r.url.startswith(API) else None)
    pg.goto(BASE + "/learn", wait_until="networkidle"); pg.wait_for_timeout(1500)

    # S1
    panel = norm(pg.locator('[data-testid="learn-disclosures"]').inner_text())
    rec("S1 six disclosures visible on load", pg.locator('[data-testid="learn-disclosures"] li').count() == 6 and all(norm(d) in panel for d in D_L + SRC_D)
        and pg.locator('[data-testid="learn-disclosures"]').is_visible())

    for i in IDS:
        pick(pg, i); pg.wait_for_timeout(1800)
        base_reqs = len(reqs)
        pt, sp = truth(i)
        art = pg.locator(f'[data-testid="case-{i}"]')
        # S2 + S3
        mounted_ok, hits, nodes = True, [], 0
        for s in STEPS:
            step(pg, s)
            others = [x for x in STEPS if x != s]
            mounted_ok &= pg.locator(f'[data-testid="step-{s}"]').count() == 1 and all(pg.locator(f'[data-testid="step-{o}"]').count() == 0 for o in others)
            for t in art.locator("[data-static-prose]").evaluate_all("ns=>ns.map(n=>{const c=n.cloneNode(true);c.querySelectorAll('[data-equation]').forEach(x=>x.remove());return c.textContent})"):
                nodes += 1
                if re.search(r"\d", strip(t)): hits.append(t[:80])
            # A1-R1 mapping: exactly this step's parts are mounted, none of the other steps' parts
            want = [f"part-{x}" for x in PARTS[s]]
            unwanted = [f"part-{x}" for o in others for x in PARTS[o]]
            mounted_ok &= all(pg.locator(f'[data-testid="{w}"]').count() == 1 for w in want) and all(pg.locator(f'[data-testid="{u}"]').count() == 0 for u in unwanted)
            # A1-R3: exactly the current step button carries aria-current="step"
            cur = pg.locator('[data-testid="learn-stepper"] button[aria-current="step"]')
            mounted_ok &= cur.count() == 1 and cur.get_attribute("data-testid") == f"step-tab-{s}"
            ov1 = pg.evaluate("()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth]")
            mounted_ok &= ov1[0] == ov1[1]
            if s == "discover":
                T = norm(art.inner_text())
                strings = {"outcome_label": pt["outcome_label"], "outcome_detail": pt["outcome_detail"], "recovery_label": pt["recovery_label"],
                           "stress_label": sp["dominant_stress_label"], "stress_detail": sp["dominant_stress_detail"]}
                miss = [k for k, v in strings.items() if norm(v) not in T]
                rec(f"S4 {i} Discover backend strings verbatim", not miss, str(miss))
                if i in ("grid_sag", "grid_loss", "thermal_trip"):
                    rec(f"S4 {i} D-L2 present in Discover", norm(D_L[1]) in T)
            if s == "explain":
                T = norm(art.inner_text())
                bad = [c["function"] for c in pt["coverage"] if norm(c["function"]) not in T or norm(c["detail"]) not in T]
                rec(f"S4 {i} Explain coverage entries verbatim", not bad, str(bad))
            pg.screenshot(path=f"{OUT}/shots/learn-1440-{i}-{s}.png", full_page=True)
        rec(f"S2 {i} four steps reachable, only current mounted", mounted_ok)
        rec(f"S3 {i} static scan (union over steps = 7 nodes)", nodes == 7 and not hits, f"nodes={nodes} hits={hits}")
        rec(f"S5 {i} no refetch on step change", len(reqs) == base_reqs, f"extra={len(reqs) - base_reqs}")

    # Back navigation, case-change reset, re-activating the current step (Codex findings 2 and 3)
    pick(pg, "load_step"); pg.wait_for_timeout(1200)
    step(pg, "explain")
    pg.locator('[data-testid="step-prev"]').click(); pg.wait_for_timeout(150)
    back_ok = pg.locator('[data-testid="step-discover"]').count() == 1
    pick(pg, "grid_sag"); pg.wait_for_timeout(1200)
    reset_ok = pg.locator('[data-testid="step-predict"]').count() == 1
    pg.locator('[data-testid="step-tab-predict"]').click(); pg.wait_for_timeout(150)
    same_focus = pg.evaluate("()=>document.activeElement && document.activeElement.textContent") or ""
    rec("S6 Back works, case change resets to Predict, re-activating the current step focuses its heading", back_ok and reset_ok and "Step 1 of 4" in same_focus, same_focus)
    # Focus from the bottom of a long step brings the heading into view (Codex finding 1)
    pick(pg, "load_step"); pg.wait_for_timeout(1500); step(pg, "discover")
    pg.locator('[data-testid="step-next"]').scroll_into_view_if_needed(); pg.locator('[data-testid="step-next"]').focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    box = pg.evaluate("()=>{const e=document.activeElement.getBoundingClientRect();return [e.top,e.bottom,innerHeight]}")
    rec("S6 Next from the bottom of Discover leaves the new step heading in view (1440 px)", 0 <= box[0] < box[2] and box[1] <= box[2], str(box))

    # S6 keyboard
    pick(pg, "load_step"); pg.wait_for_timeout(800)
    pg.locator('[data-testid="step-tab-predict"]').focus()
    pg.keyboard.press("Tab"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    focused = pg.evaluate("()=>document.activeElement && document.activeElement.textContent")
    rec("S6 keyboard Tab+Enter moves to Discover and focuses its heading", bool(focused) and "Step 2 of 4" in focused, str(focused))
    pg.locator('[data-testid="step-next"]').click(); pg.wait_for_timeout(150)
    rec("S6 Next button advances to Explain", pg.locator('[data-testid="step-explain"]').count() == 1)
    rec("S9 console clean on 1440 walkthrough", not errs, str(errs[:3]))

    # S8 rapid switching, slowed response
    pg2 = b.new_page(viewport={"width": 1440, "height": 900})
    def slow(route):
        if "load_step" in route.request.url or "load-step" in route.request.url:
            pg2.wait_for_timeout(2500)
        route.continue_()
    pg2.route("**/api/v1/simulations/**", slow)
    pg2.goto(BASE + "/learn"); pg2.wait_for_timeout(500)
    for i in IDS: pick(pg2, i); pg2.wait_for_timeout(100)
    pick(pg2, "load_step"); pick(pg2, "grid_loss"); pg2.wait_for_timeout(4500)
    step(pg2, "discover")
    rec("S8 rapid switching ends on selected case", pg2.locator('[data-testid="case-grid_loss"]').count() == 1 and pg2.locator('[data-testid="case-load_step"]').count() == 0)
    pg2.close()

    # S7 backend blocked
    pg3 = b.new_page(viewport={"width": 1440, "height": 900})
    pg3.route(API + "/**", lambda r: r.abort())
    pg3.goto(BASE + "/learn"); pg3.wait_for_timeout(2000)
    ok = pg3.locator('[data-testid="part-predict"]').count() == 1
    step(pg3, "discover"); ok &= pg3.locator('[data-testid="remote-error"]').count() >= 2
    step(pg3, "explain"); ok &= pg3.locator('[data-testid="coverage-unavailable"]').count() == 1 and pg3.locator('[data-testid="part-explain"]').count() == 1
    step(pg3, "apply"); ok &= pg3.locator('[data-testid="part-decision"]').count() == 1
    rec("S7 backend blocked: static steps render, live parts show errors", ok)
    pg3.close()

    # S9 mobile
    pm = b.new_page(viewport={"width": 390, "height": 844}); merr = []
    pm.on("console", lambda m: merr.append(m.text) if m.type in ("error", "warning") else None)
    pm.goto(BASE + "/learn", wait_until="networkidle"); pm.wait_for_timeout(1200)
    allok = True
    for i in IDS:
        pick(pm, i); pm.wait_for_timeout(1500)
        for s in STEPS:
            step(pm, s)
            ov = pm.evaluate("()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth]")
            allok &= ov[0] == ov[1]
            if not ov[0] == ov[1]: print("overflow", i, s, ov)
            pm.screenshot(path=f"{OUT}/shots/learn-390-{i}-{s}.png", full_page=True)
    pick(pm, "load_step"); pm.wait_for_timeout(1500); step(pm, "discover")
    pm.locator('[data-testid="step-next"]').scroll_into_view_if_needed(); pm.locator('[data-testid="step-next"]').focus(); pm.keyboard.press("Enter"); pm.wait_for_timeout(300)
    mb = pm.evaluate("()=>{const e=document.activeElement.getBoundingClientRect();return [e.top,e.bottom,innerHeight]}")
    rec("S6 Next from the bottom of Discover leaves the new step heading in view (390 px)", 0 <= mb[0] < mb[2] and mb[1] <= mb[2], str(mb))
    rec("S9 390 px no horizontal overflow, 5 cases x 4 steps", allok)
    rec("S9 390 px console clean", not merr, str(merr[:3]))
    b.close()
json.dump(res, open(OUT + "/verify_learn_steps.json", "w"), indent=1)
sys.exit(1 if any(r["result"] == "FAIL" for r in res) else 0)
