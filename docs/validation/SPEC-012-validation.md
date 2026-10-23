# SPEC-012 — Learn by Example V1 — Validation Record

## Context

- Spec: `docs/specifications/SPEC-012-learn-by-example-v1.md` (v0.2 + R19). Spec review history: v0.1 Codex `CHANGES_REQUIRED` (6 major, 4 minor), v0.2 closure `CHANGES_REQUIRED` (1 major, 2 minor, corrected), second closure `APPROVE`. **R19 (three wording constraints) was added after the last Codex spec review and was not re-reviewed.** Implementation was authorized by the Human Engineering Lead's workstream instruction "Continue SPEC-012 implementation" (2026-10-18).
- Baseline: `main` at `4e6af36` (merged SPEC-011). Branch `feature/spec-012-learn-by-example`.
- Scope: frontend-only `/learn`; no change to `src/`, `backend/`, `config/`, `scenarios/`, `dashboard/`, `content/`, `data/`, `tests/`, `.github/`, `requirements.txt`, `frontend/package*.json`.

## Design choices that deviate from or interpret the spec (reported, not hidden)

1. **No shared Sandbox component was edited.** R4 approved optional presentation props, but composition sufficed: reused components (`TelemetryChart`, `ProtectionTimeline`, `ProtectionCoordination` which embeds `CoverageChecklist`, `EngineeringInterpretation`, `TransientMetricsPanel`) sit inside a wrapper with the Tailwind arbitrary variant `[&_.text-muted]:text-secondary`, so `text-muted` resolves to `text-secondary` on `/learn` only. Browser check: 0 elements with text still painted in the muted colour inside any of the five cases.
2. **`ScenarioSelector` was not reused.** A new native-radio `CaseSelector` was written (arrow keys, no primary-on-accent fill). The existing component was left untouched. This is presentation only; no engineering computation is duplicated.
3. **R16 clarified (sixteen added predicate kinds).** Codex noted that some prose assertions had no R16 predicate kind and that interim checks proved less than the prose stated. Each assertion Codex listed as unmapped is now a typed `Case.claims` entry with a stronger predicate (full-run voltage band, maximum deficit, monotone temperature rise that slows, continuous overtemperature through the debounce interval before the trip, initial shortfall and target above demand after the step, derated limit below demand, persistent shortfall, floor reached before the sag ends, target to zero, grid unavailable to the end, monotone decay). Finer causal-mechanism statements remain the R17 reviewed set. The kinds are listed in spec §6.9 and **await Human Engineering Lead acceptance** as an R16 clarification.
4. **Part 5b coverage** is shown through `ProtectionCoordination` (it renders the coordination result and the `coverage` checklist together), placed in "Limits of this model"; the standalone `CoverageChecklist` was not used. Part 6a repeats the backend outcome strings in a compact panel, so outcome text appears twice by design.
5. **Request guarding** uses a per-case `key` plus effect cleanup (the lint rule forbids synchronous `setState` in an effect), which cancels an in-flight request when the case changes.
6. **No new registry entries** were needed: every cited source is an already-registered, already-inspected one (`OCPSST`, `OCPWP`). Mt. Diablo and the NVIDIA technical blog were not opened and are not cited; the corresponding §6.7 items were omitted (fast AI-load swings) or narrowed to repository facts (storage). `architectureChoicesData.ts` is unchanged.
7. **Static-scan boundary** is implemented as `data-static-prose` nodes (parts 1, 2, 4, 5a, 6b, 7, 8) with `data-equation` nodes stripped; disclosure and reference blocks are outside the scan and contain digits (for example "800 VDC", "§4.2").

## Automated verification (actual results)

| Check | Result |
|---|---|
| `python -m pytest -q` (scratch venv) | 190 passed |
| `npm run lint` | no findings |
| `npm run typecheck` | passed |
| `npm run build` | passed; `/learn` prerendered |
| Existing component/Sandbox edits | `git diff 4e6af36` over `frontend/app/sandbox` and the five reused component files: 0 lines |
| Protected paths | `git diff --name-only 4e6af36 -- src backend config scenarios dashboard content data tests .github requirements.txt frontend/package.json frontend/package-lock.json`: 0 files |

Tracked changes vs baseline: `frontend/app/components/SiteNav.tsx` (link enabled, comment), `frontend/app/page.tsx` (card `live`, `href` set). New: spec, this record, `learn/page.tsx`, `LearnByExample.tsx`, `CaseSelector.tsx`, `learnByExampleData.ts`. Protected untracked and **not committed**: `docs/reboot/`, `docs/validation/SPEC-005-validation.md`.

## Script results (AC-2, AC-3, AC-4 data level, AC-5, AC-9)

Run against a backend on the same engine (`node check_learn.mts --base http://localhost:8010`; the script and the in-page check are reproduced in the appendix):

```
static items labeled: 52
AC-4 data-level digit hits: []
AC-5 term hits: [] | SEMI mentions: []
AC-9 claims checked: 40 mismatches: []
ALL SCRIPT CHECKS PASS
```

## Acceptance criteria

| AC | Evidence | Result |
|---|---|---|
| AC-1 | `/learn` renders; nav link and home card enabled; the only edits to `SiteNav.tsx` and `page.tsx` are the enablement and a comment | Pass |
| AC-2 | `Record<ScenarioName, Case>` is compile-time complete; script confirms five cases, 3–6 Explain steps, 2–4 validation items each | Pass |
| AC-3 | Script: 52 static items each carry an evidence label and basis; every `public-fact`/`emerging` item cites a registered reference id | Pass |
| AC-4 | Data-level scan: no digit after the allowlist. **Rendered** scan in the browser over all `data-static-prose` nodes (seven per case) with `data-equation` stripped: 0 hits in all five cases | Pass |
| AC-5 | Term search: no best/worst/wins/winner/superior/inferior/safer/more reliable/outperform | Pass |
| AC-6 | The six disclosures (`illustrative`, `d1`, `sim`, `block`, `d2`, `d3`) are rendered in the page header; D-L2 is also rendered inside the modeled panel and the observe block on grid_sag, grid_loss, thermal_trip | Pass (text from the shared constants, not re-typed) |
| AC-7 | Browser: panel 6b contains no svg/canvas in any case; it is a `data-static-prose` node, so AC-4 covers its numbers | Pass |
| AC-8 | Browser, per case against live responses: `outcome_label`, `outcome_detail`, `recovery_label`, `dominant_stress_label`, `dominant_stress_detail` appear as exact strings; for each of the five `coverage` entries the rendered list item contains its `function` and `detail` and starts with the glyph matching its `modeled` flag (check for true, cross for false); 0 missing or mismatched in all five cases | Pass |
| AC-9 | 40 claims across 5 cases, 0 mismatches against live responses (predicates per R16; band read from `lib/transientMetrics.ts`, which is the 1% settling band). R17 causality table below | Pass |
| AC-10 | Browser: (a) backend down on first load: static parts render (seven static nodes, explain steps, not-modeled items), three error messages, "coverage unavailable", no uncaught error, no overflow; (b) request A failing alone: charts and timeline replaced by an error, dominant-stress block still shows backend text; (c) request B failing alone: charts and timeline render, only the stress block shows its error; (d) rapid switching with a deliberately delayed earlier response: the final display is the last selected case with its own outcome text | Pass |
| AC-11 | Source table below | Pass |
| AC-12 | Zero edits to protected paths and zero edits to any Sandbox component or `/sandbox` page. Before/after capture performed: a production build of the baseline `4e6af36` (git worktree, same engine and API) and of this branch were each driven through all five scenarios on `/sandbox`, hashing `main.outerHTML` and `main.innerText`; every hash is identical for all five scenarios (html and text; lengths from about 0.5 MB to 12.8 MB). `/architecture` and `/system-map` source files untouched | Pass |
| AC-13 | Native radio group with arrow keys (ArrowRight ×2 moved load_step to thermal_trip); native `<details>` for Predict; 0 muted-colour text in reused components; focus outline classes on every control and link; `#references` anchor present; 1280 px and 375 px: no horizontal overflow in any case; no console/uncaught errors during the runs | Pass; contrast not measured numerically |
| AC-14 | pytest, lint, typecheck, build as above | Pass locally; GitHub CI result is recorded on the PR after push (pending when this record was written) |

## R17: Explain steps mapped to §5.2 relations (author's reasoning; reviewed, not scripted)

| Case | Steps → relation |
|---|---|
| load_step | 1 → first-order SST response (tau_sst); 2 → energy balance `dE_dc/dt = P_sst − P_load`, `E_dc = ½ C_dc V_dc²`; 3 → PI voltage control; 4 → energy balance with surplus delivery. Limiting quantity: energy the link can give up |
| sustained_high_load | 1 → `P_loss = P_sst(1−η)/η`; 2 → lumped thermal node; 3 → linear derating (limit above demand, so no electrical effect); 4 → stable derated operating point. Limiting quantity: heat accumulation vs thermal path |
| thermal_trip | 1 → thermal node; 2 → derating below demand; 3 → energy balance, fast drain; 4 → debounced latched trip after floor contact (observed order: bus collapse then trip). Limiting quantity: derated power vs demand; protection response vs collapse time |
| grid_sag | 1 → proportional availability assumption (`src/grid.py`); 2 → energy balance; 3 → small stored energy, floor reached; 4 → refill after the grid returns, with the R19(a) caveat. Limiting quantity: available power vs demand |
| grid_loss | 1 → availability to zero, target forced to zero by saturation logic; 2 → first-order SST decay; 3 → energy balance; 4 → floor, no restart. Limiting quantity: stored link energy vs demand |

R19 compliance: (a) grid_sag, grid_loss and thermal_trip limits state the ideal-sink load and the numerical clamp; the grid_sag Predict reveal says the recovery is a model classification, not a physical ride-through. (b) No SEMI or other standard is named anywhere (script term search: 0), and the sag limit says the preset is not derived from, tested against or compliant with a published ride-through standard. (c) No no-controller counterfactual is stated or shown.

## AC-11 source record

Only two external sources are cited by `/learn`, both already in the registry and inspected for SPEC-011's source audit; sections below were re-read from the extracted PDF text on 2026-10-18 when writing the §6.7 items.

| Reference | Sections opened and used |
|---|---|
| OCPSST (OCP SST specification Rev 0.3.0) | §3 scope (SST coupled with energy storage as an MV-UPS); §4.1 product components (no stage count); §4.2 MVAC short-circuit capability, duration TBD; §4.3 DC grounding (IT, floating or HRG, detailed design TBD) and the recommended constant-current fault-coordination setting (described without its figures); §5.1.2 voltage ride-through with SST and energy storage, and the statement that there is no unified standard |
| OCPWP (OCP LVDC white paper v1.0) | §7.2.4 fuses and breakers interrupting DC by arc voltage above system voltage; no standard or recognized practice for coordinating protection for the converter-fed DC fault behavior described, in particular the capacitor-discharge peak; §4.2 migration to solid-state solutions may need a new approach to coordination studies |

No textbook or standard is cited on `/learn`, so no unverified textbook claim is carried. Repository-sourced statements (for example "no reset logic") are labeled `assumption` with the file as basis. The Mt. Diablo specification and the NVIDIA developer blog were not opened; no claim rests on them. No numbers from any source appear on the page.

## Screenshots

Desktop (1280 px) and a narrow capture were taken with headless Chrome against the production build and the running API: `learn-desktop.png` (1280 px, full page) and `learn-mobile-500.png` (headless Chrome enforces a minimum window width, so this is a 500 px capture; the 375 px viewport was verified in the Browser pane by DOM measurement and a pane screenshot). They are delivered with the PR report, not committed to the repository.

## Known limitations

1. The R19 spec text was not re-reviewed by Codex before implementation.
2. Contrast was verified by computed colour class (the muted token is no longer used on the page), not numerically against WCAG ratios.
3. Computed contrast was measured by colour class only (see AC-13).
4. No automated UI test framework exists; the checks above are scripts plus manual browser runs, not CI tests.
5. The Browser pane and the QA worktree already use ports 3000 and 8000; this verification used its own backend (port 8010) and a production build pointing at it, on the same engine code.
6. Qualitative claims are consistency-checked against the engine; causal and physical correctness rest on the R17 review table and Codex review.

## Independent Codex review of the implementation

**Round 1 (Codex CLI, read-only): `CHANGES_REQUIRED` — 0 blocking, 3 major, 3 minor.** Codex reproduced all 22 then-defined R16 predicates with zero mismatches and all section 5.4 classifications, confirmed the cited OCP passages support the public-fact and emerging items, and found no ranking, sag-standard-origin claim, no-controller result, SST-mandatory implication or cross-architecture validation claim. Findings and remediation:

| # | Sev | Finding | Remediation |
|---|---|---|---|
| 1 | Major | "Constant efficiency makes loss independent of load" is wrong: loss scales with delivered power | Text now says efficiency does not depend on load or temperature and the loss still grows with delivered power |
| 2 | Major | R16 predicates do not cover every engine-checkable prose assertion | Predicate kinds added and wired as typed claims; the interim EXTRA block was removed. R16 clarification awaits human acceptance (design choice 3) |
| 3 | Major | AC-8 coverage `modeled` flags, AC-12 before/after captures and CI evidence missing | Flags now checked per entry in the browser; before/after Sandbox capture performed against a baseline build (identical hashes for all five scenarios); CI result recorded on the PR after push |
| 4 | Minor | grid_loss missing the energy-not-conserved statement; non-recovery wrongly attributed to reset logic | Reworded: energy not conserved at the clamp; no recovery because the supply never returns |
| 5 | Minor | `EngineeringInterpretation` placed after the chart it refers to "below"; static Explain repeated its lesson | Interpretation moved above the charts; the duplicated sentence removed from the load_step Explain step |
| 6 | Minor | Script CLI and appendix not reproducible | `--base URL` supported; in-page rendered-scan script and output added to the appendix |

Codex could not itself verify browser rendering, keyboard/focus, computed contrast, overflow, injected failures, screenshots or before/after captures (read-only), and did not rerun pytest/build. A targeted re-review of the six findings follows.

## Appendix: verification script (`check_learn.mts`, run with Node outside the repository)

```ts
import * as L from "/Users/jasonliu/Projects/ai-power-lab/frontend/app/lib/learnByExampleData.ts";
import * as A from "/Users/jasonliu/Projects/ai-power-lab/frontend/app/lib/architectureChoicesData.ts";
const bi = process.argv.indexOf("--base");
const BASE = bi > 0 ? process.argv[bi + 1] : "http://localhost:8000"; // usage: node check_learn.mts --base http://localhost:8000
const BAND = 0.01; // RECOVERY_BAND_FRACTION in lib/transientMetrics.ts (read, not copied from the spec)
const fail: string[] = []; const ok = (c: boolean, m: string) => { if (!c) fail.push(m); };
const ids = ["load_step","sustained_high_load","thermal_trip","grid_sag","grid_loss"] as const;
// AC-2 cardinality
ok(L.CASE_ORDER.length===5 && ids.every(i=>L.CASES[i]?.id===i),"five cases");
let items=0;
const strip = (t:string)=> t
  .replace(/§[\d.]+(?:[–-][\d.]+)?/g,"")
  .replace(/\bRev [\d.]+/g,"").replace(/\bv[\d.]+/g,"")
  .replace(/\bRD[1-7]\b/g,"").replace(/\bOCP(?:WP|SST)?\b/g,"");
const digitHits: string[]=[];
const scan=(where:string,t:string)=>{ const m=strip(t).match(/\d/g); if(m) digitHits.push(where+": "+t.slice(0,80)); };
const labelOk=(where:string,e:any)=>{ items++; ok(!!e.evidence && !!e.basis, where+" label/basis");
  if(e.evidence==="public-fact"||e.evidence==="emerging") ok(Array.isArray(e.refs)&&e.refs.length>0&&e.refs.every((r:string)=>r in A.REFERENCES),where+" refs"); };
for (const id of ids){ const c:any=L.CASES[id];
  scan(id+" situation",c.situation.text); labelOk(id+" situation",c.situation);
  scan(id+" predict q",c.predict.question); scan(id+" predict r",c.predict.reveal); labelOk(id+" predict",c.predict);
  ok(c.explain.steps.length>=3&&c.explain.steps.length<=6,id+" steps 3-6"); c.explain.steps.forEach((s:any,i:number)=>scan(id+" step"+i,s.text)); scan(id+" limiting",c.explain.limitingQuantity); labelOk(id+" explain",c.explain);
  c.limits.forEach((l:any,i:number)=>{scan(id+" limit"+i,l.text); labelOk(id+" limit"+i,l);});
  c.notModeled.forEach((n:any)=>{scan(id+" nm "+n.name,n.text); scan(id+" nm name",n.name); labelOk(id+" nm "+n.name,n);});
  scan(id+" decision",c.decision.text); labelOk(id+" decision",c.decision);
  ok(c.validation.length>=2&&c.validation.length<=4,id+" validation 2-4"); c.validation.forEach((v:any)=>scan(id+" val",v.verifies));
  ok(c.decision.drivers.every((d:string)=>A.DRIVERS.some((x:any)=>x.id===d)),id+" drivers");
  ok(A.BOUNDARIES.some((b:any)=>b.id===c.decision.boundary),id+" boundary");
}
// AC-5 ranking terms over every authored string
const all=JSON.stringify([L.CASES, L.LEARN_DISCLOSURES]);
const terms=(all.match(/\b(best|worst|wins|winner|superior|inferior|safer|more reliable|outperforms?)\b/gi)||[]);
// R19(b): SEMI origin claims
const semi=(all.match(/\bSEMI\b/g)||[]);
// AC-9: claims against live responses
const get=async(p:string,init?:any)=>(await fetch(BASE+p,init)).json();
const cmp:any=await get("/api/v1/simulations/comparison");
const minV=(a:number[])=>a.reduce((x,y)=>Math.min(x,y),Infinity), maxV=(a:number[])=>a.reduce((x,y)=>Math.max(x,y),-Infinity);
const mism: string[]=[]; let checked=0;
for (const id of ids){
  const entry=cmp.scenarios.find((e:any)=>e.scenario===id);
  const run:any = id==="load_step" ? await get("/api/v1/simulations/load-step",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}) : await get("/api/v1/simulations/protection-scenarios/"+id);
  const v:number[]=run.timeseries.v_dc_v, ref=run.thresholds.voltage_reference_v, states=[...new Set<string>(run.timeseries.operating_state)];
  for (const cl of (L.CASES[id] as any).claims){ checked++;
    let pass=false, got:any;
    switch(cl.kind){
      case "outcome": got=run.protection_timeline.outcome; pass=got===cl.value; break;
      case "recovery": got=run.protection_timeline.recovery; pass=got===cl.value; break;
      case "dominantStress": got=entry.stress_profile.dominant_stress; pass=got===cl.value; break;
      case "statesReached": got=states; pass=cl.value.length===states.length && cl.value.every((s:string)=>states.includes(s)); break;
      case "voltageFalls": got=v.reduce((a:number,b:number)=>Math.min(a,b),Infinity); pass=(got < ref*(1-BAND))===cl.value; break;
      case "voltageRecovers": got=v[v.length-1]; pass=(Math.abs(got-ref)<=ref*BAND)===cl.value; break;
      case "reachesFloor": got=[v.reduce((a:number,b:number)=>Math.min(a,b),Infinity),run.thresholds.floor_voltage_v]; pass=(got[0]<=got[1]*(1+1e-6))===cl.value; break;
      case "voltageStaysInBand": got=[minV(v),maxV(v)]; pass=((got[0]>=ref*(1-BAND))&&(got[1]<=ref*(1+BAND)))===cl.value; break;
      case "noSustainedDeficit": { const pl=run.timeseries.p_load_w, ps=run.timeseries.p_sst_w; const worst=pl.reduce((m:number,x:number,k:number)=>Math.max(m,x-ps[k]),-Infinity); got=worst/maxV(pl); pass=(got<=0.01)===cl.value; break; }
      case "temperatureRises": { const T=run.timeseries.temperature_c; got=[T[0],maxV(T)]; pass=(got[1]>T[0]+1)===cl.value; break; }
      case "temperatureRiseSlows": { const T=run.timeseries.temperature_c, q=Math.floor(T.length/4); let mono=true; for(let k=1;k<T.length;k++){ if(T[k]<T[k-1]-1e-6){mono=false;break;} } got=[mono,T[q]-T[0],T[T.length-1]-T[T.length-1-q]]; pass=(mono&&got[2]<got[1])===cl.value; break; }
      case "tripAfterDebounce": { const T=run.timeseries.temperature_c, tt=run.timeseries.time_s, th=run.thresholds; const i=T.findIndex((x:number)=>x>=th.thermal_trip_c); const t=run.protection_timeline.trip_event_time_s; let cont=true; if(i>=0&&t!=null){ for(let k=i;k<tt.length&&tt[k]<=t;k++){ if(T[k]<th.thermal_trip_c){cont=false;break;} } } got=[tt[i],t,th.thermal_trip_time_s,cont]; pass=(t!=null&&i>=0&&cont&&(t-tt[i])>=th.thermal_trip_time_s-0.01)===cl.value; break; }
      case "deliveryExceedsDemandAfterEvent": { const t0=run.events[0].time_s, tt=run.timeseries.time_s; const i0=tt.findIndex((t:number)=>t>=t0); got=run.timeseries.p_sst_w.slice(i0).some((p:number,k:number)=>p>run.timeseries.p_load_w[i0+k]*1.001); pass=got===cl.value; break; }
      case "deliveryShortfallDuringSag": { const g=run.timeseries.grid_voltage_pu, pl=run.timeseries.p_load_w, ps=run.timeseries.p_sst_w; got=g.some((x:number,k:number)=>x<0.999&&ps[k]<pl[k]*0.999); pass=got===cl.value; break; }
      case "deliveryDecays": { const tt=run.timeseries.time_s, ps=run.timeseries.p_sst_w, pl=run.timeseries.p_load_w; const t0=run.timeseries.grid_available.findIndex((b:boolean)=>!b); let mono=true; for(let k=t0+1;k<ps.length;k++){ if(ps[k]>ps[k-1]+1e-6){mono=false;break;} } got=[mono,ps[ps.length-1]/pl[pl.length-1]]; pass=(mono&&got[1]<0.05)===cl.value; break; }
      case "deliveryShortfallAfterEvent": { const ts=run.timeseries, i0=ts.time_s.findIndex((t:number)=>t>=run.events[0].time_s); const k=i0+1; got=[ts.p_sst_w[k],ts.p_load_w[k]]; pass=(ts.p_sst_w[k]<ts.p_load_w[k]*0.999)===cl.value; break; }
      case "targetAboveDemandWhileBelowRef": { const ts=run.timeseries; got=ts.v_dc_v.some((x:number,k:number)=>x<ref*(1-BAND)&&ts.p_target_w[k]>ts.p_load_w[k]*1.001); pass=got===cl.value; break; }
      case "endsInState": { const ts=run.timeseries, st=ts.operating_state, n=st.length, w=Math.max(2,Math.floor(n*0.1)), T=ts.temperature_c; const tail=st.slice(n-w); const stateOk=tail.every((x:string)=>x===cl.value); const dT=T[n-1]-T[n-w], rise=T[n-1]-T[0]; got=[tail[0],dT,rise]; pass=(stateOk&&dT<=0.05*rise); break; }
      case "derateBelowDemand": { const ts=run.timeseries; got=ts.derate_factor.some((d:number,k:number)=>run.thresholds.rated_power_w*d<ts.p_load_w[k]*0.999); pass=got===cl.value; break; }
      case "deliveryShortfallPersists": { const ts=run.timeseries; const k0=ts.p_sst_w.findIndex((p:number,k:number)=>p<ts.p_load_w[k]*0.999); let all=k0>=0; for(let k=k0;all&&k<ts.p_sst_w.length;k++){ if(!(ts.p_sst_w[k]<ts.p_load_w[k]*0.999)){all=false;} } got=[k0,all]; pass=all===cl.value; break; }
      case "floorBeforeSagEnds": { const ts=run.timeseries; const kf=ts.v_dc_v.findIndex((x:number)=>x<=run.thresholds.floor_voltage_v*(1+1e-6)); got=[kf,kf>=0?ts.grid_voltage_pu[kf]:null]; pass=(kf>=0&&ts.grid_voltage_pu[kf]<0.999)===cl.value; break; }
      case "targetGoesToZero": { const ts=run.timeseries, k0=ts.grid_available.findIndex((b:boolean)=>!b); const tol=1e-6*run.thresholds.rated_power_w; let all=k0>=0; for(let k=k0+1;all&&k<ts.p_target_w.length;k++){ if(Math.abs(ts.p_target_w[k])>=tol) all=false; } got=[k0,ts.p_target_w[k0+1],all]; pass=all===cl.value; break; }
      case "gridStaysUnavailable": { const g=run.timeseries.grid_available; const k0=g.findIndex((b:boolean)=>!b); got=[k0,k0>=0&&g.slice(k0).every((b:boolean)=>!b)]; pass=(k0>=0&&got[1]===true)===cl.value; break; }
      case "order": got=[run.protection_timeline.bus_collapse_event_time_s,run.protection_timeline.trip_event_time_s]; pass=got[0]!=null&&got[1]!=null&&got[0]<got[1]; break;
    }
    if(!pass) mism.push(id+" "+cl.kind+" expected "+JSON.stringify(cl.value)+" got "+JSON.stringify(got));
  }
}

console.log("static items labeled:",items);
console.log("AC-4 data-level digit hits:",JSON.stringify(digitHits));
console.log("AC-5 term hits:",JSON.stringify(terms),"| SEMI mentions:",JSON.stringify(semi));
console.log("AC-9 claims checked:",checked,"mismatches:",JSON.stringify(mism));
console.log(fail.length||digitHits.length||terms.length||semi.length||mism.length? "FAIL\n"+fail.join("\n") : "ALL SCRIPT CHECKS PASS");
```

## Appendix: in-page check (run in the Browser pane on `/learn`; AC-4 rendered scan, AC-8 strings and coverage flags, contrast, order)

```js
// Run in the page at http://localhost:3100/learn (backend at API).
const API="http://localhost:8010", sleep=ms=>new Promise(r=>setTimeout(r,ms));
const ids=["load_step","sustained_high_load","thermal_trip","grid_sag","grid_loss"];
const cmp=await (await fetch(API+"/api/v1/simulations/comparison")).json();
const strip=t=>t.replace(/§[\d.]+(?:[–-][\d.]+)?/g,"").replace(/\bRev [\d.]+/g,"").replace(/\bv[\d.]+/g,"").replace(/\bRD[1-7]\b/g,"").replace(/\bOCP(?:WP|SST)?\b/g,"");
const norm=s=>s.replace(/\s+/g," ");
const mutedColor=getComputedStyle(document.documentElement).getPropertyValue("--color-muted").trim().toLowerCase();
const hex=s=>{const m=s.match(/\d+/g).map(Number);return "#"+m.slice(0,3).map(x=>x.toString(16).padStart(2,"0")).join("")};
const out={};
for(const id of ids){
  document.querySelector(`[data-testid="case-option-${id}"]`).click(); await sleep(1800);
  const art=document.querySelector(`[data-testid="case-${id}"]`); const T=norm(art.innerText);
  const run= id==="load_step"? await (await fetch(API+"/api/v1/simulations/load-step",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"})).json(): await (await fetch(API+"/api/v1/simulations/protection-scenarios/"+id)).json();
  const e=cmp.scenarios.find(x=>x.scenario===id), pt=run.protection_timeline;
  const strings={outcome_label:pt.outcome_label,outcome_detail:pt.outcome_detail,recovery_label:pt.recovery_label,stress_label:e.stress_profile.dominant_stress_label,stress_detail:e.stress_profile.dominant_stress_detail};
  const missing=Object.entries(strings).filter(([k,v])=>!T.includes(norm(v))).map(([k])=>k);
  // coverage: function, detail AND modeled flag (glyph) per entry
  const covLis=[...art.querySelectorAll('[data-testid="protection-coordination"] li')].filter(li=>/[✓✕]/.test(li.textContent));
  const covBad=pt.coverage.filter(c=>{const li=covLis.find(l=>norm(l.textContent).includes(norm(c.function))); return !li || !norm(li.textContent).includes(norm(c.detail)) || li.textContent.trim().startsWith(c.modeled?"✓":"✕")===false;}).map(c=>c.function);
  const nodes=[...art.querySelectorAll("[data-static-prose]")]; const digitHits=[];
  for(const n of nodes){const c=n.cloneNode(true); c.querySelectorAll("[data-equation]").forEach(x=>x.remove()); const t=strip(c.textContent); if(/\d/.test(t)) digitHits.push(t.slice(0,80));}
  const mutedEls=[...art.querySelectorAll(".text-muted")].filter(el=>el.textContent.trim().length>2);
  const interp=art.querySelector('[data-testid="observe-live"]'); let order=null;
  if(id==="load_step"){ const html=interp.innerText; order={interpretationBeforeCharts: html.indexOf("WHY THIS HAPPENED")>=0 && html.indexOf("WHY THIS HAPPENED")<html.indexOf("POWER BALANCE")}; }
  out[id]={missing,covEntries:pt.coverage.length,covLisFound:covLis.length,covBad,staticNodes:nodes.length,digitHits,stillMuted:mutedEls.filter(el=>hex(getComputedStyle(el).color)===mutedColor).length,order};
}
out
```

### Re-reviews of the remediation

- **Targeted re-review 1: `CHANGES_REQUIRED` (1 major).** Findings 1, 3, 4, 5 and 6 were accepted as resolved; finding 2 (R16 typed-claim coverage) remained open, because the interim EXTRA checks were not typed claims and some proved less than the prose.
- **Remediation:** eight predicate kinds were added and then a further eight, so that every assertion Codex listed as unmapped has a typed claim; `tripAfterDebounce` now requires continuous overtemperature, and `temperatureRiseSlows` requires a non-decreasing temperature (40 claims, 0 mismatches). The kinds are recorded in spec §6.9 as an R16 clarification awaiting human acceptance.
- **Targeted re-review 2: `CHANGES_REQUIRED` (2 major)** on the first set of eight kinds (remaining unmapped assertions; two predicates proving less than the prose). Both were addressed by the second set and the tightened predicates described above. **Codex has not re-reviewed that final set.** Treat R16 coverage as: every assertion Codex named is mapped and passing, with the final wording not independently re-reviewed.
- **Targeted re-review 3 (final, bounded): `CHANGES_REQUIRED` (1 major).** Codex confirmed every listed assertion has a typed claim, both predicate tightenings are present, 40 claims pass against freshly executed backend functions, and the clarification is documented as pending human acceptance. It found three predicates that still proved less than the prose: initial deficit after the step, settling into a derated operating point, and the target becoming zero when supply is lost. They were tightened (shortfall at the sample right after the event; derated state and a settled temperature over the last tenth of the run; target zero from the sample after the supply is first lost) and re-run (40 claims, 0 mismatches). **Per the instruction for no further review loops, that last tightening was not re-reviewed by Codex.**
- **Focused re-review 4 (requested by the Human Engineering Lead): `PASS`.** Codex confirmed the three tightened predicates establish what the prose states (initial deficit: the sample right after the step shows delivered power well below demand; derated point: every state in the final tenth is DERATED and temperature rises by about 0.12 percent of the total rise over it; target: zero throughout the post-loss tail and at the first unavailable-grid sample), reran all 40 claims against direct backend calls with 0 mismatches, confirmed the sixteen added kinds are bounded checks over existing response fields with no change to `src/`, `backend/`, adapters, scenarios or API contracts, and resolved the remaining major. It did not verify HTTP transport, browser behavior, the full test suite or CI.
- **R16 clarification accepted** by the Human Engineering Lead (2026-10-19), provided the checks stay bounded static checks with no simulation or API change.

## Human Visual QA evidence (2026-10-19)

Branch head served on free ports (the QA worktree's servers on 3000 and 8000 serve `main` and were left running): frontend production build at `http://localhost:3100/learn`, API at `http://localhost:8010`. Ten full-page screenshots (five cases at 1280 px and at true 375 px mobile emulation, device scale 2) were captured with headless Chrome driven over the DevTools protocol, with a recorded `scrollWidth == clientWidth` for every one (no horizontal overflow). They are in `docs/reboot/spec-012-qa-screenshots/` (untracked, not committed).



## Amendment A1: four-step shell (verification record)

Script: `docs/validation/spec-012-a1/verify_learn_steps.py` (Playwright, Chromium), run against the dev server and a local backend on the same engine, all five cases x four steps at 1440 px and 390 px. Result of the run on the implementation commit: **36 checks, 36 PASS, 0 FAIL** (first run; after the Codex review below it was extended to 39 checks, all PASS: all six disclosures verbatim from the source modules, the exact part-to-step mapping, `aria-current`, Back navigation, reset on case change, focus on re-activating the current step, heading in view after Next from the bottom of Discover at 1440 and 390 px, and horizontal overflow at both 1440 and 390 px) (S1 disclosures on load; S2 steps reachable, only current mounted; S3 AC-4 rendered scan, 7 nodes per case, 0 digit hits; S4 backend strings verbatim in Discover and coverage entries in Explain; S5 no refetch on step change; S6 keyboard Tab/Enter focus on step heading; S7 backend blocked; S8 rapid switching; S9 no horizontal overflow and clean console). Also: `npm run lint`, `npm run typecheck` and `npm run build` pass locally. `pytest` is unaffected (no change under `src/`, `backend/`, `config/`, `scenarios/`, `tests/`). This is the implementer's own verification; it is not independent review. Not verified: real devices, other browsers, screen-reader behavior beyond roles and focus, and the R16 claim script (unchanged data module, not re-run here).


### Amendment A1: Codex review (PR #13, head af119fb)

Verdict **REQUEST CHANGES**: 1 major, 3 minor, 0 blocking (Codex CLI, read-only, session 01a1618b-5fb0-7bf0-b39c-f43b835411de; Codex did not run the browser script or the build). Confirmed by Codex: the step-to-part mapping, the seven static-prose blocks, the six disclosures and `aria-current`. Addressed in the follow-up commit: (1) focus now scrolls the step heading into view and shows a visible focus ring; (2) re-activating the current step focuses its heading; (3) the script now checks all six disclosures verbatim, the part mapping, `aria-current`, case-change reset and Back; (4) the script measures overflow at 1440 px as well as 390 px. Re-review of `af119fb..750e0b5` (PR #13): APPROVE; all four findings resolved, no new defects (Codex did not rerun the browser script or the build).

## Amendment A2: Load Step interactive lesson (verification record, milestone M1)

Script: `docs/validation/spec-012-a2/verify_load_step_lesson.py` (Playwright, Chromium), production build, local backend on the same engine; output in `verify_run_output.txt`. The expected values are recomputed independently in the script from the API response (samples, minimum, recovery band, shortfall, target above demand), not copied from the UI. Result: **19 PASS, 0 FAIL** covering Discover gating and the absence of the result before commit (L1), commit/lock/reveal (L2), prediction comparison (L3), cursor readout equal to the API sample and both chart cursors moving together, jump buttons and the phase annotation (L4), measured cause chain values (L5), the Apply question with one defensible option and no stored state (L6), no digits or ranking terms in the lesson prose (L7), keyboard-only walkthrough (L8), the other four cases unchanged (L9), and 390/1440 px overflow and console (L10). The A1 script (39 checks after the PR #13 review) was re-run against this build with the gate handled: 39 PASS. L4 asserts the requested index is reached, the readout (V, P_load, P_sst, mismatch), time label and `aria-valuetext`, and that both chart cursor lines sit at the x position computed from the sample time and move; L5 asserts every grounding value (shortfall and its time, target-above-demand and its time, minimum voltage, energy, demand before and after, recovery time) against recomputation from the API; L11 covers the keyboard skip path and focus. Screenshots (desktop 1440 px, mobile 390 px) are in `docs/validation/spec-012-a2/shots/`.

Not verified: real devices, other browsers, screen-reader behavior beyond roles and focus, Human Visual QA, and independent (Codex) review. The checks are scripts, not CI tests: the repository has no frontend test runner, and CI runs lint, typecheck and build.


### Amendment A2: Codex review (PR #14, head 977e536)

Verdict **REQUEST CHANGES**: 1 major, 3 minor, 0 blocking (Codex CLI, read-only, session 01a16193-0de1-7983-aea8-274fe53a9d16; Codex did not rerun the browser script, the build or the engine). Codex found `observedOutcome`, cursor indexing, unit conversions and the unchanged other four cases consistent. Addressed in the follow-up commit: (1) the Predict reasoning and the Explain-adjacent prose no longer claim the controller "keeps raising" its target or "gives up"; they describe a corrective power above demand and say recovery depends on converter headroom and saturation (src/controller.py), so recovery is shown for this model and these illustrative values only; (2) the slider has `aria-valuetext` (time, V_dc, phase), is associated with the readout, and has a visible focus outline; (3) "Look without predicting" moves focus to the Discover heading; (4) L4 and L5 strengthened as above, and the record counts corrected. Re-review (PR #14, head bc813a0): APPROVE (Codex did not rerun the browser script or the build).


## Amendment A3: UX refinement after Human Visual QA (verification record)

Scripts re-run on the A3 build (production build, local backend): `docs/validation/spec-012-a2/verify_load_step_lesson.py` **25 PASS, 0 FAIL** and `docs/validation/spec-012-a1/verify_learn_steps.py` **39 PASS, 0 FAIL** (outputs: `verify_run_output.txt`, `verify_a1_on_m1_output.txt`). New checks: L12 the authored expected outcome, all four per-option reasoning texts and causal keywords (lag, refill, stored energy, time constant, corrective, drain, first-order, the gap, feedforward) are absent from the whole page text with no pick, after a pick, on the Discover gate and after commit while still on Predict, and appear only after "Check it against the model"; L13 the case selector and four-step control end inside the first screen at 1440x900 (selector bottom and stepper bottom below the viewport height) and at 390x844, the limitation is visible and the basis section is collapsed by default; L14 three cause-chain steps of 60 words or fewer, with the technical section collapsed by default and holding the interpretation and engineering result when opened. A1 S1 now checks the concise statement, the collapsed default and the six verbatim disclosures in the expanded section. Screenshots (desktop and mobile, including the first screen and the Predict step after a pick): `docs/validation/spec-012-a2/shots/`. Not verified: real devices, other browsers, screen readers beyond roles and focus, independent re-review of this pass.

### Amendment A3: Codex review (PR #14, diff bc813a0..6214bde)

Verdict **REQUEST CHANGES**: 0 blocking, 0 major, 2 minor (Codex CLI, read-only, session 01a16201-63a3-7e91-ab0a-e8014fdb8241; browser scripts, build and engine not rerun by Codex). Codex found the requested behaviors satisfied (Predict hides causal hints until commit, assumptions and claims unchanged, limitation visible, six disclosures in the DOM inside native collapsed details, backend strings visible, engine/API/chart calculations unchanged, eight-node scan correct). Addressed: (1) the collapsed technical section now precedes the charts, so the reused text "the Power Balance chart below" is true (checked by L14 order); (2) L12 now asserts, for each of the four options, that its own reasoning, the verdict (Match only for the observed outcome) and the expected-outcome text appear after commit, and the script count is now 25 PASS. Re-review of `6214bde..c7c15b7` (PR #14): APPROVE; both findings resolved, no new defects (Codex did not rerun the browser script or the build).

## A4 verification (correctness feedback, Predict and Apply)

`docs/validation/spec-012-a4/verify_correctness_feedback.py` (Playwright, production build, live backend): 14 PASS, 0 FAIL (`verify_run_output.txt`). It covers every Predict option and every Apply option; pre-submit secrecy by scanning all element text including hidden and sr-only text (`textContent`), every attribute value (including `data-testid`), `data-*` names, status classes, and text reached through `aria-describedby`/`aria-labelledby` (a defence in depth: referenced text is also caught by the text scan), with positive controls (C9) that inject eight leak kinds (hidden text, sr-only text, `data-*`, `data-testid`, `aria-describedby`, `aria-labelledby`, `aria-label`, status class) and require the probe to flag each; "Your answer" literal text on the selected option and, on every unselected option, absence of that text, status words, status classes, `data-status` and icons; stale-verdict clearing; 390 px overflow/console; and C8, three controlled API responses (voltage above reference, exactly at reference, falling and staying down) showing "Correct" follows the run's outcome class, not a fixed answer. Regression: lesson script 25 PASS (L6 now reads the status node), stepper script 39 PASS. Screenshots: `docs/validation/spec-012-a4/shots/`. 

### Amendment A4: Codex review (PR #14, diff c7c15b7..53097af)

Verdict **REQUEST CHANGES**: three P2 findings, all in the verification script, none in the feature code (Codex confirmed no pre-submit reveal, icon plus text with the status tokens, Predict "Correct" from `observedOutcome`, and no engine/API/chart/Explain change). Fixed: secrecy probe now reads hidden text, all attributes and aria-referenced text, with positive controls (C9); controlled responses added (C8); unselected-option assertions added (C4). Re-review of `53097af..a7c5ac0`: findings 2 and 3 resolved; finding 1 partly (the `data-testid` branch skipped the general checks and the record overstated C9 coverage). Fixed in the next commit: exception removed, `data-testid` and `aria-labelledby` controls added, coverage wording corrected. Final re-review: pending at time of writing.

## M1 Human acceptance

On 2026-10-22 Jason (Human Engineering Lead) formally approved the M1 Load Step Human Visual QA: the Predict, Discover, Explain and Apply learning experience and the correct/incorrect answer feedback (SPEC-012 A4) are accepted. No further observations are recorded here. At the time of acceptance the verified PR #14 head was `dadea7e` with green CI; Codex closure on A4 was APPROVE (`a7c5ac0..dadea7e`). Merge order and merging are the Human Engineering Lead's: PR #13 first, then PR #14 retargeted to `main`.
