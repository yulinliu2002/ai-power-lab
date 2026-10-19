"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchProtectionScenario, type ProtectionScenarioResponse } from "../../lib/simulationApi";
import { sstStatus } from "../../lib/statusRoles";
import { STATUS_SVG_COLOR, SVG_COLOR } from "../../lib/theme";
import { AreaHeader, BasisBar, EvidenceChip, LineChart } from "../ui";

/**
 * Learn by Example — interaction signature: PREDICT.
 * One guided case, one step at a time: Predict -> Discover -> Explain ->
 * Apply. All traces, event times and outcome strings in Discover are read
 * verbatim from the live API run (thermal_trip); the frontend computes
 * nothing. The explain/apply prose is authored teaching content.
 */
const STEPS = [
  { name: "Predict", sub: "Commit to an answer" },
  { name: "Discover", sub: "Check the model" },
  { name: "Explain", sub: "Trace the cause" },
  { name: "Apply", sub: "What to validate" },
] as const;

const OPTIONS = [
  { k: "A", id: "PROTECTION_TRIP", text: "The thermal protection trips first, and the bus voltage holds until then." },
  { k: "B", id: "BUS_COLLAPSE_UNPROTECTED", text: "The bus voltage collapses first, before thermal protection ever trips." },
  { k: "C", id: "RIDE_THROUGH", text: "Neither: the converter derates enough to ride through." },
] as const;

export default function LearnLab() {
  const [step, setStep] = useState(0);
  const [pick, setPick] = useState<string | null>(null);
  const [data, setData] = useState<ProtectionScenarioResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchProtectionScenario("thermal_trip").then(setData).catch((e: Error) => setErr(e.message));
  }, []);

  const tl = data?.protection_timeline;
  const th = data?.thresholds;
  const t = data?.timeseries;
  const total = tl ? tl.segments[tl.segments.length - 1].end_time_s : 1;
  const correct = tl && pick ? OPTIONS.find((o) => o.id === tl.outcome)?.k : null;

  return (
    <>
      <AreaHeader
        area="03 · Learn by Example"
        mode="Predict"
        question="Does protection act before the bus voltage collapses?"
        answer="A sustained overload heats the converter. Commit to a prediction, check it against the model run, then trace the cause and decide what a real design would need to validate."
      />
      <div className="lab-wrap">
        <BasisBar
          notes={[
            { tag: "Simulated slice", text: "The case runs on the Advanced Sandbox's simplified average-value model of the Conceptual MV-to-800 VDC via SST slice. It does not validate, size or benchmark any facility or other architecture." },
            { tag: "Assumptions", text: "Thresholds and the derating curve are illustrative educational assumptions, not data. The model has thermal protection only: no bus-voltage or grid protection, and a latched trip has no reset." },
            { tag: "Numerical floor", text: "After a collapse the bus voltage shown is the integrator's numerical floor, not a physically meaningful residual voltage." },
          ]}
        />
      </div>

      <div className="lab-wrap" style={{ paddingTop: 24 }}>
        <div className="lab-steps" role="tablist" aria-label="Guided steps">
          {STEPS.map((s, i) => (
            <button
              key={s.name}
              className="lab-step"
              aria-current={i === step ? "step" : undefined}
              data-done={i < step}
              disabled={i > 0 && !pick}
              onClick={() => setStep(i)}
            >
              <span className="i">{i + 1}</span>
              <div>
                <b>{s.name}</b>
                <span className="s">{s.sub}</span>
              </div>
            </button>
          ))}
        </div>
        <p className="lab-label" style={{ marginTop: 8 }}>
          Step {step + 1} of 4 · {STEPS[step].name}
        </p>
      </div>

      <section className="lab-wrap lab-section lab-first" style={{ paddingTop: 12 }}>
        {err && <p className="lab-panel" role="alert">Model run unavailable: {err}. Start the API (see README) to load the live run.</p>}

        {step === 0 && (
          <div className="lab-split r57">
            <div>
              <h2 className="lab-h2">Situation</h2>
              <p className="lab-body">
                The load demands more than a derated converter can supply. Heat builds up, the allowed power shrinks, and at some point supply can no
                longer meet demand. The question is which happens first: the electrical collapse or the protective trip.
              </p>
              <EvidenceChip kind="assumption" />
            </div>
            <div>
              <h2 className="lab-h2">Before looking: what do you expect?</h2>
              <div style={{ display: "grid", gap: 8, margin: "12px 0 16px" }}>
                {OPTIONS.map((o) => (
                  <button key={o.k} className="lab-option" aria-pressed={pick === o.id} onClick={() => setPick(o.id)}>
                    <span className="k">{o.k}</span>
                    <span>{o.text}</span>
                  </button>
                ))}
              </div>
              <button className="lab-btn primary" disabled={!pick || !data} onClick={() => setStep(1)}>
                Check against the model
              </button>
            </div>
          </div>
        )}

        {step === 1 && data && tl && th && t && (
          <div style={{ display: "grid", gap: 20 }}>
            <div className="lab-panel raised" style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 320px" }}>
                <p className="lab-label">Model outcome (live run)</p>
                <h2 className="lab-h2" style={{ fontSize: 20 }}>{tl.outcome_label}</h2>
                <p className="lab-body" style={{ marginBottom: 0 }}>{tl.outcome_detail}</p>
              </div>
              <div style={{ flex: "0 1 260px" }}>
                <p className="lab-label">Your prediction</p>
                <p style={{ margin: 0, fontWeight: 600 }}>
                  Option {pick ? OPTIONS.find((o) => o.id === pick)?.k : "–"} ·{" "}
                  {pick === tl.outcome ? "matches the model" : `model shows option ${correct ?? "?"}`}
                </p>
                <p className="lab-section-sub" style={{ marginTop: 4 }}>
                  Either way, what matters is the reason. That comes next.
                </p>
              </div>
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
            <div>
              <button className="lab-btn primary" onClick={() => setStep(2)}>
                Explain why
              </button>
            </div>
          </div>
        )}
        {step === 1 && !data && !err && <p className="lab-body">Running the model…</p>}

        {step === 2 && th && (
          <div className="lab-split r75">
            <div>
              <h2 className="lab-h2" style={{ marginBottom: 16 }}>Cause chain</h2>
              <ol className="lab-chain">
                <li>
                  <p className="lab-h3">Heat accumulates</p>
                  <p className="lab-body">Sustained demand produces conversion loss, and the loss accumulates as heat in the lumped thermal node.</p>
                  <code className="lab-eq">C_th · dT/dt = P_loss − (T − T_amb) / R_th</code>
                </li>
                <li>
                  <p className="lab-h3">Available power shrinks</p>
                  <p className="lab-body">
                    Above {th.thermal_derate_start_c} °C the available power is derated. Demand exceeds even the fully derated limit, so the converter
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
                    The trip latches only after temperature stays at or above {th.thermal_trip_c} °C for {th.thermal_trip_time_s} s. In this model the
                    electrical collapse arrives first.
                  </p>
                </li>
              </ol>
              <EvidenceChip kind="assumption" />
            </div>
            <aside className="lab-panel inset">
              <h2 className="lab-h2">Limits of this model</h2>
              <ul className="lab-body" style={{ paddingLeft: 18, margin: "8px 0 14px" }}>
                <li>Protection is thermal only: no bus-voltage or grid protection, and the latched trip has no reset.</li>
                <li>After the collapse, the voltage shown is a numerical floor, not a physical residual voltage.</li>
                <li>The derating curve and thresholds are illustrative choices.</li>
              </ul>
              <p className="lab-label">Limiting quantity</p>
              <p className="lab-body" style={{ marginBottom: 14 }}>
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
              <div style={{ display: "grid", gap: 10, marginTop: 14 }}>
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
              <p className="lab-body" style={{ marginTop: 8 }}>
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
