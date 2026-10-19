# SPEC-014 validation scripts

Playwright (Chromium) scripts; axe-core is injected from a local path and is not a repository dependency. Servers: baseline worktree (`f9cc8c4`) and the branch against one backend. Results for the branch are in `after/`, the baseline in `baseline/`.

| Script | Purpose |
|---|---|
| `capture_baseline.py`, `capture_after.py`, `compare.py` | page states, API request/response sets, test ids, numbers, overflow |
| `capture_rich.py`, `compare_rich.py` | line-level architecture preservation, five Learn cases, chart geometry, EvidenceTag HTML, API JSON |
| `verify_static.py` | rail, disclosures on load, type tiers, axe, handoffs, 390px element checks |
| `state_matrix.py`, `verify_extended.py` | Sandbox state matrix, delayed responses, retention, keyboard/Tab traversal, Appendix A strings, Stage 4 values, rail vs canonical data |
| `verify_map.py` | System Map arrow counts |
| `learn_regression.py` | `/learn` at 375 and 1280 |
| `repro_baseline.py`, `repro_after.py` | product-review findings reproduced at the baseline and re-measured on the branch |

`capture_rich.py` outputs (about 60 MB each, they embed API responses) and all screenshots are not committed; regenerate them with the scripts.
