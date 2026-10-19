"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DISCLOSURES } from "../../lib/architectureChoicesData";
import { fetchProtectionScenario, type ProtectionScenarioResponse } from "../../lib/simulationApi";
import { sstStatus } from "../../lib/statusRoles";
import { STATUS_SVG_COLOR, SVG_COLOR } from "../../lib/theme";
import { AreaHeader, BasisBar, EvidenceChip, LineChart } from "../ui";

/**
 * Learn by Example — interaction model: PREDICT.
 *
 * Demonstration of ONE case (thermal trip) in a four-step shell:
 *   Predict  = SPEC-012 parts 1 Situation + 2 Predict
 *   Discover = part 3 Observe (+ 6a modeled outcome), live
 *   Explain  = part 4 Explain + part 5 Limits
 *   Apply    = part 6b not modeled + 7 Decision link + 8 Validation reasoning
 * Conformance with SPEC-012 that this demo keeps: all steps are freely
 * reachable (no gating, no scoring); the expected outcome is a native
 * <details> reveal (no JS state); authored prose has no numeric values;
 * static steps render with the backend down; the live request has its own
 * loading/error state. Production reads these from learnByExampleData.ts.
 */
const STEPS = [
  { name: "Predict", sub: "Commit to an answer" },
  { name: "Discover", sub: "Check the model" },
  { name: "Explain", sub: "Trace the cause" },
  { name: "Apply", sub: "What to validate" },
] as const;

/** Verbatim SPEC-012 §6.5 D-L1..D-L3 (production imports LEARN_DISCLOSURES). */
const D_L1 =
  "These cases run the five fixed Sandbox scenarios on a simplified average-value model. Results show how the model behaves under stated illustrative assumptions, not how real equipment behaves.";
const D_L2 =
  "In the grid-sag, grid-loss and thermal-trip cases, 'bus collapse' means the integrator reached its numerical energy floor. It is not a physically meaningful residual voltage.";
const D_L3 =
  "Real-world fault behavior listed under 'not modeled' is described from public sources or general engineering principle. It is not simulated here, and no result on this page validates it.";

export default function LearnLab() {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<ProtectionScenarioResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchProtectionScenario("thermal_trip").then(setData).catch((e: Error) => setErr(e.message));
  }, []);

  const tl = data?.protection_timeline;
  const t = data?.timeseries;
  const th = data?.thresholds;
  const total = tl ? tl.segments[tl.segments.length - 1].end_time_s : 1;

  return (
    <>
      <AreaHeader
        area="03 · Learn by Example"
        mode="Predict"
        question="Does protection act before the bus voltage collapses?"
        answer="A sustained overload heats the converter. Predict what happens, check it against the model run, trace the cause, then decide what a real design would need to validate."
      />
      <div className="lab-wrap">
        <BasisBar
          notes={[
            { tag: "Simulation scope", text: DISCLOSURES.sim },
            { tag: "Blocks", text: DISCLOSURES.block },
            { tag: "Drivers", text: DISCLOSURES.illustrative },
            { tag: "Model", text: D_L1 },
            { tag: "Bus collapse", text: D_L2 },
            { tag: "Not modeled", text: D_L3 },
            {
              tag: "Rail legend",
              text: "Dashed nodes are the simulated slice. Rack DC-DC conversion is not modeled; the AI load is lumped. The rail shows one representative architecture, not a universal path.",
            },
          ]}
        />
      </div>

      <div className="lab-wrap" style={{ paddingTop: 24 }}>
        <nav aria-label="Guided steps">
          <ol className="lab-steps" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {STEPS.map((s, i) => (
              <li key={s.name} style={{ display: "contents" }}>
                <button
                  className="lab-step"
                  aria-current={i === step ? "step" : undefined}
                  data-done={i < step}
                  onClick={() => setStep(i)}
                >
                  <span className="i" aria-hidden>{i + 1}</span>
                  <div>
                    <b>{s.name}</b>
                    <span className="s">{s.sub}</span>
                  </div>
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <p className="lab-label" style={{ marginTop: 8 }}>
          Step {step + 1} of 4 · {STEPS[step].name}
        </p>
      </div>

      <section className="lab-wrap lab-section lab-first" style={{ paddingTop: 12 }}>
        {step === 0 && (
          <div className="lab-split r57">
            <div>
              <h2 className="lab-h2">Situation</h2>
              <p className="lab-body" data-static-prose>
                The load demands more than a derated converter can supply. Heat builds up, the allowed power shrinks, and at some point supply can no
                longer meet demand. The question is which happens first: the electrical collapse or the protective trip.
              </p>
              <EvidenceChip kind="assumption" />
            </div>
            <div>
              <h2 className="lab-h2">Before looking: what do you expect?</h2>
              <p className="lab-body" data-static-prose style={{ marginTop: 8 }}>
                Which happens first, the bus voltage collapsing or the thermal protection tripping? Decide, then reveal the expected outcome.
              </p>
              <details className="lab-panel inset" style={{ marginBottom: 14 }}>
                <summary style={{ cursor: "pointer", fontWeight: 600 }}>Show the expected outcome</summary>
                <p className="lab-body" data-static-prose style={{ margin: "8px 0 8px" }}>
                  Expected: the bus voltage collapses first, before thermal protection ever trips. This is an authored expectation, checked against the live
                  response in the next step.
                </p>
                <EvidenceChip kind="assumption" />
              </details>
              <button className="lab-btn primary" onClick={() => setStep(1)}>
                Check against the model
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div style={{ display: "grid", gap: 20 }}>
            {err && (
              <p className="lab-panel" role="alert">
                Model run unavailable: {err}. The backend is required for this step; the other steps do not need it.
              </p>
            )}
            {!data && !err && <p className="lab-body">Running the model…</p>}
            {data && tl && t && th && (
              <>
                <div className="lab-panel raised">
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <p className="lab-label">Model outcome (live run)</p>
                    <EvidenceChip kind="model-output" />
                  </div>
                  <h2 className="lab-h2" style={{ fontSize: 20 }}>{tl.outcome_label}</h2>
                  <p className="lab-body" style={{ marginBottom: 0 }}>{tl.outcome_detail}</p>
                  <p className="lab-body" style={{ margin: "8px 0 0" }}>{tl.recovery_label}</p>
                </div>
                <div className="lab-grid lab-g2">
                  <div className="lab-panel">
                    <LineChart
                      title="DC bus voltage"
                      unit="V"
                      series={[{ name: "V_dc", x: t.time_s, y: t.v_dc_v, color: SVG_COLOR.accent }]}
                      markers={data.events.map((e) => ({ x: e.time_s, label: e.label }))}
                      yMin={0}
                      yMax={900}
                    />
                  </div>
                  <div className="lab-panel">
                    <LineChart
                      title="Converter temperature"
                      unit="°C"
                      series={[{ name: "T", x: t.time_s, y: t.temperature_c, color: SVG_COLOR.textPrimary }]}
                      hlines={[
                        { y: th.thermal_derate_start_c, label: "derating begins", color: SVG_COLOR.warning },
                        { y: th.thermal_trip_c, label: "trip threshold", color: SVG_COLOR.critical },
                      ]}
                    />
                  </div>
                </div>
                <div>
                  <h2 className="lab-h2">Protection timeline</h2>
                  <p className="lab-section-sub" style={{ marginBottom: 10 }}>State of the converter over the run, from the model.</p>
                  <div className="lab-bar" role="img" aria-label="Operating-state timeline">
                    {tl.segments.map((s) => (
                      <div
                        key={s.state + s.start_time_s}
                        style={{ width: `${(s.duration_s / total) * 100}%`, background: STATUS_SVG_COLOR[sstStatus(s.state).role] }}
                      >
                        {s.state}
                      </div>
                    ))}
                  </div>
                  <ol className="lab-mono" style={{ listStyle: "none", padding: 0, margin: "12px 0 0", fontSize: 12, color: "var(--color-text-secondary)", display: "grid", gap: 4 }}>
                    {tl.events.map((e) => (
                      <li key={e.label + e.time_s}>
                        t = {e.time_s.toFixed(3)} s · <span style={{ color: "var(--color-text-primary)" }}>{e.label}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              </>
            )}
            <div>
              <button className="lab-btn primary" onClick={() => setStep(2)}>
                Explain why
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="lab-split r75">
            <div>
              <h2 className="lab-h2" style={{ marginBottom: 16 }}>Cause chain</h2>
              <ol className="lab-chain" data-static-prose>
                <li>
                  <p className="lab-h3">Heat accumulates</p>
                  <p className="lab-body">Sustained demand produces conversion loss, and the loss accumulates as heat in the lumped thermal node.</p>
                  <code className="lab-eq">C_th · dT/dt = P_loss − (T − T_amb) / R_th</code>
                </li>
                <li>
                  <p className="lab-h3">Available power shrinks</p>
                  <p className="lab-body">
                    Above the derating start temperature the available power is derated. Demand exceeds even the fully derated limit, so the converter
                    eventually cannot meet it.
                  </p>
                </li>
                <li>
                  <p className="lab-h3">The bus drains faster than heat builds</p>
                  <p className="lab-body">
                    Once delivery persistently falls short of demand, the DC link drains in a time tiny compared with the thermal time scale.
                  </p>
                  <code className="lab-eq">dE_dc/dt = P_sst − P_load</code>
                </li>
                <li>
                  <p className="lab-h3">Protection is too slow</p>
                  <p className="lab-body" style={{ marginBottom: 0 }}>
                    The trip latches only after temperature stays at or above the trip threshold for the debounce time. In this model the electrical
                    collapse arrives first.
                  </p>
                </li>
              </ol>
              <EvidenceChip kind="assumption" />
            </div>
            <aside className="lab-panel inset">
              <h2 className="lab-h2">Limits of this model</h2>
              <ul className="lab-body" data-static-prose style={{ paddingLeft: 18, margin: "8px 0 14px" }}>
                <li>Protection is thermal only: no bus-voltage or grid protection, and the latched trip has no reset.</li>
                <li>After the collapse, the voltage shown is a numerical floor, not a physical residual voltage.</li>
                <li>The derating curve and thresholds are illustrative choices.</li>
              </ul>
              <p className="lab-label">Limiting quantity</p>
              <p className="lab-body" data-static-prose style={{ marginBottom: 14 }}>
                Derated available power against demand, and the protection response time against the electrical collapse time.
              </p>
              <button className="lab-btn primary" onClick={() => setStep(3)}>
                Apply it
              </button>
            </aside>
          </div>
        )}

        {step === 3 && (
          <div className="lab-split r75">
            <div>
              <h2 className="lab-h2">What would you validate before relying on this behavior?</h2>
              <div style={{ display: "grid", gap: 10, marginTop: 14 }} data-static-prose>
                {[
                  ["Derated capability", "Derated capability against the real demand profile at rated conditions.", "Factory test"],
                  ["Undervoltage protection", "Presence and timing of bus undervoltage protection in the real design.", "Simulation + site test"],
                  ["Coordination", "Protection coordination and clearing times for the real converter and distribution, including fast electrical protection beyond thermal.", "Analysis"],
                ].map(([t1, body, ev]) => (
                  <div key={t1} className="lab-panel" style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <div style={{ flex: "1 1 280px" }}>
                      <p className="lab-h3">{t1}</p>
                      <p className="lab-body" style={{ marginBottom: 0 }}>{body}</p>
                    </div>
                    <span className="lab-chip" style={{ alignSelf: "flex-start" }}>{ev}</span>
                  </div>
                ))}
              </div>
              <p className="lab-section-sub" style={{ marginTop: 10 }}>Illustrative list, not a complete plan for any facility.</p>
            </div>
            <aside className="lab-panel raised">
              <h2 className="lab-h2">Where this connects</h2>
              <p className="lab-body" data-static-prose style={{ marginTop: 8 }}>
                This case asks whether protection must act faster than a thermal function can, and what would need validating on fast protection and
                coordination. It is a lesson about response times in one simplified chain, not a comparison of architectures.
              </p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Link className="lab-btn" href="/design-lab/architecture">Open Architecture Choices</Link>
                <Link className="lab-btn" href="/design-lab/sandbox">Try it in the Sandbox</Link>
              </div>
            </aside>
          </div>
        )}
      </section>
    </>
  );
}
