"""Preservation comparison from capture_rich.py outputs. Usage: python compare_rich.py baseline/rich.json after/rich.json"""
import json, sys
B = json.load(open(sys.argv[1])); A = json.load(open(sys.argv[2]))
res = []
def ok(name, cond, detail=""):
    res.append(("PASS" if cond else "FAIL", name, str(detail)[:300]))

# ---- Architecture: every baseline line of every content group still present (case/whitespace-normalized)
HEADING_LINES = set()  # headings were renamed; content lines must all survive
after_blob = "\n".join(A["arch"].get("_page_lines", []))
for g in ["driver", "compare", "boundary", "decision", "validation"]:
    bl = B["arch"].get(g, {}); al = A["arch"].get(g, {})
    ok(f"AC-4 {g}: same block ids ({len(bl)} baseline blocks)", set(bl) == set(al), f"missing {sorted(set(bl)-set(al))} extra {sorted(set(al)-set(bl))}")
    for k, lines in bl.items():
        # layout may move a heading line out of its block or merge adjacent label lines; every baseline line must still
        # appear in the after page (as a whole line or inside a merged line), and body text must remain inside the same block
        miss = [x for x in lines if x not in after_blob]
        same_block_miss = [] if g == "driver" else [x for x in lines if len(x) > 60 and x not in al.get(k, [])]  # the driver question moved to the board headline (it is on the page, checked above)
        ok(f"AC-4 {g}:{k} every baseline line preserved on the page; long (content) lines preserved inside the same block", not miss and not same_block_miss, (miss[:3], same_block_miss[:3]))
refs_missing = [x for x in B["arch"]["references"] if x not in A["arch"]["references"] and not x.startswith("references")]
ok("AC-4 reference list lines preserved", not refs_missing, refs_missing[:3])
ok("AC-28 architecture evidence-tag texts (label + basis + refs): every baseline text present after (per-cell placement is covered by the per-block checks)", all(x in A["arch"]["evidence_tags"] for x in set(B["arch"]["evidence_tags"])), [x for x in set(B["arch"]["evidence_tags"]) if x not in A["arch"]["evidence_tags"]][:2])
dis = ["sst is one candidate technology", "blocks in these architectures", "the advanced sandbox simulates only", "requirement drivers are illustrative", "this page does not rank"]
ok("AC-26 five disclosures present in visible list after", all(any(d in x for x in A["arch"]["disclosures_visible"]) for d in dis), len(A["arch"]["disclosures_visible"]))

# ---- Learn: five cases; diff only the authorized propagation
ok("AC-15 Learn: five cases both", len(B["learn"]) == 5 == len(A["learn"]))
AUTH_SUBSTR = ["outcome labels are this simplified model", "v1 models only sustained thermal", "dc bus voltage", "power balance"]
for k in B["learn"]:
    bt, at = B["learn"][k]["text"], A["learn"][k]["text"]
    only_b = [x for x in bt if x not in at and not any(s in x for s in AUTH_SUBSTR)]
    only_a = [x for x in at if x not in bt and not any(s in x for s in AUTH_SUBSTR)]
    ok(f"AC-15 Learn {k}: text identical except authorized caution/footnote/chart-title casing", not only_b and not only_a, (only_b[:2], only_a[:2]))
    ok(f"AC-15 Learn {k}: links identical", B["learn"][k]["links"] == A["learn"][k]["links"])
    ok(f"AC-28 Learn {k}: default EvidenceTag HTML byte-identical", B["learn"][k]["evidence_html"] == A["learn"][k]["evidence_html"], f"{len(B['learn'][k]['evidence_html'])} tags")
    ok(f"AC-11 Learn {k}: chart polylines identical", B["learn"][k]["chart_points"] == A["learn"][k]["chart_points"])

# ---- Sandbox chart inputs (polyline geometry) and tick labels
for sc in B["charts"]:
    ok(f"AC-11 {sc}: chart polylines (data geometry) identical", B["charts"][sc]["polylines"] == A["charts"][sc]["polylines"])
    bt, at = B["charts"][sc]["ticks"], A["charts"][sc]["ticks"]
    ok(f"AC-11 {sc}: baseline chart tick/label texts all present", all(x in at for x in bt if x), [x for x in bt if x and x not in at][:4])

# ---- API responses identical per endpoint
ok("AC-7 API JSON identical per endpoint", B["api"] == A["api"], sorted(set(B["api"]) ^ set(A["api"])))
for r in res: print(*r)
print("FAILS:", sum(1 for r in res if r[0] == "FAIL"))
json.dump([{"result": a, "check": b, "detail": c} for a, b, c in res], open(sys.argv[2].replace("rich.json", "compare_rich.json"), "w"), indent=1)
