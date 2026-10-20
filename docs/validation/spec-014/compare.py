"""Compare baseline vs after captures (SPEC-014 AC-4, AC-6, AC-7, AC-9, AC-11, AC-17).
Usage: python compare.py baseline/capture.json after/capture.json
"""
import json, re, sys
B = json.load(open(sys.argv[1])); A = json.load(open(sys.argv[2]))
out = []
def ok(name, cond, detail=""):
    out.append(("PASS" if cond else "FAIL", name, detail)); return cond

# AC-6: problems (success-path runs)
ok("AC-6 baseline problems", True, f"{len(B['problems'])} (dev-only font request): {B['problems'][:2]}")
ok("AC-6 after: 0 console/page/network problems", len(A["problems"]) == 0, str(A["problems"][:3]))

# AC-7: API requests identical as sets (method, url, body, response hash)
bs = {tuple(x) for x in B["api"]}; as_ = {tuple(x) for x in A["api"]}
ok("AC-7 API request/response set identical", bs == as_, f"baseline {len(bs)} unique, after {len(as_)} unique; only-baseline {sorted(bs-as_)[:3]}; only-after {sorted(as_-bs)[:3]}")
ok("AC-7 same number of API calls", len(B["api"]) == len(A["api"]), f"{len(B['api'])} vs {len(A['api'])}")

# AC-9 / AC-4: testids union
def union(states, keys):
    u = set()
    for k, v in states.items():
        if any(k.startswith(p) for p in keys): u |= set(v["testids"])
    return u
bu = union(B["states"], ["architecture-desktop", "arch-driver"]); au = union(A["states"], ["architecture-desktop", "arch-driver", "architecture-show-all"])
retired_arch = {"disclosures"}  # kept; none retired on architecture except nothing
ok("AC-4 architecture testids: baseline union subset of after union", bu <= au, f"missing: {sorted(bu-au)}")
bs_ids = union(B["states"], ["sandbox-"]); as_ids = union(A["states"], ["sandbox-"])
declared = {"view-mode-toggle", "view-mode-option-single", "view-mode-option-compare"}
ok("AC-9 sandbox testids: only declared retirements missing", (bs_ids - as_ids) <= declared, f"missing: {sorted(bs_ids-as_ids)}")

# AC-11: numeric tokens from baseline appear in after, per paired state
num = re.compile(r"\d+(?:\.\d+)?")
pairs = [("sandbox-load_step-desktop","sandbox-load_step-desktop"),("sandbox-sustained_high_load-desktop","sandbox-sustained_high_load-desktop"),
         ("sandbox-thermal_trip-desktop","sandbox-thermal_trip-desktop"),("sandbox-grid_sag-desktop","sandbox-grid_sag-desktop"),
         ("sandbox-grid_loss-desktop","sandbox-grid_loss-desktop"),("sandbox-experiment-run-desktop","sandbox-experiment-run-desktop"),
         ("sandbox-sweep-run-desktop","sandbox-sweep-run-desktop"),("sandbox-compare-desktop","sandbox-compare-desktop")]
for bk, ak in pairs:
    bt = set(num.findall(B["states"][bk]["text"])); at = set(num.findall(A["states"][ak]["text"]))
    ok(f"AC-11 numbers in {bk} preserved", bt <= at, f"missing: {sorted(bt-at)[:12]}")

# architecture decision card text per driver identical
for i in range(1, 8):
    k = f"arch-driver-rd{i}-desktop"
    norm = lambda t: " ".join(t.lower().split())
    bt = [norm(x) for x in B["states"][k]["text"].split("\n") if norm(x)]; at = norm(A["states"][k]["text"])
    ok(f"AC-3 decision card rd{i}: every baseline line present (case/whitespace-normalized; layout merges adjacent label lines)", all(x in at for x in bt), [x for x in bt if x not in at][:2])

# AC-17: page overflow at mobile
for k, v in A["states"].items():
    if k.endswith("-mobile") and "overflow" in v:
        ok(f"AC-17 no page overflow {k}", v["overflow"]["sw"] == v["overflow"]["W"], str(v["overflow"]))
for l in out: print(*l)
print("FAILS:", sum(1 for l in out if l[0] == "FAIL"))
