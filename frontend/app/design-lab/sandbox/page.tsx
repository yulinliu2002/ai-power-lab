"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchLoadStep, type LoadStepResponse } from "../../lib/simulationApi";
import { computeTransientMetrics, formatEnergyDeficitKj } from "../../lib/transientMetrics";
import { SVG_COLOR } from "../../lib/theme";
import { AreaHeader, BasisBar, LineChart } from "../ui";

/**
 * Advanced Sandbox — interaction signature: EXPERIMENT.
 * Workbench layout: parameters on a left rail, instruments on the
 * right. Runs Scenario A through the real API; metrics come from the
 * existing computeTransientMetrics (no new math in this prototype).
 */
export default function SandboxLab() {
  const [finalFraction, setFinal] = useState(0.8);
  const [capF, setCap] = useState(0.02);
  const [tau, setTau] = useState(0.02);
  const [data, setData] = useState<LoadStepResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      setData(await fetchLoadStep({ final_fraction: finalFraction, capacitance_f: capF, time_constant_s: tau }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [finalFraction, capF, tau]);

  useEffect(() => {
    // Baseline run on mount (API defaults).
    fetchLoadStep().then(setData).catch((e: Error) => setErr(e.message));
  }, []);

  const m = data ? computeTransientMetrics(data) : null;
  const t = data?.timeseries;

  return (
    <>
      <AreaHeader
        area="Supporting tool · Advanced Sandbox"
        mode="Experiment"
        question="What does one load step do to the 800 VDC bus?"
        answer="Change a parameter, run the simplified model, and read the transient. A free-form study tool; the guided cases live in Learn by Example."
      />
      <div className="lab-wrap">
        <BasisBar
          notes={[
            "Simplified average-value model of the Conceptual MV-to-800 VDC via SST slice. It is not a switching-level model and is not calibrated to any commercial product.",
            "Parameters and ranges are educational assumptions. Results are model outputs, not predictions for real equipment.",
          ]}
        />
      </div>

      <section className="lab-wrap lab-section lab-first">
        <div className="lab-bench">
          <aside className="lab-panel" aria-label="Experiment parameters">
            <h2 className="lab-h2" style={{ marginBottom: 14 }}>Parameters</h2>
            <div className="lab-field">
              <label htmlFor="ff">
                Post-step load <span className="lab-mono">{(finalFraction * 100).toFixed(0)} %</span>
              </label>
              <input id="ff" type="range" min={0.4} max={1} step={0.05} value={finalFraction} onChange={(e) => setFinal(+e.target.value)} />
            </div>
            <div className="lab-field">
              <label htmlFor="cf">
                DC-link capacitance <span className="lab-mono">{(capF * 1000).toFixed(0)} mF</span>
              </label>
              <input id="cf" type="range" min={0.005} max={0.08} step={0.005} value={capF} onChange={(e) => setCap(+e.target.value)} />
            </div>
            <div className="lab-field">
              <label htmlFor="tc">
                SST response time constant <span className="lab-mono">{(tau * 1000).toFixed(0)} ms</span>
              </label>
              <input id="tc" type="range" min={0.005} max={0.08} step={0.005} value={tau} onChange={(e) => setTau(+e.target.value)} />
            </div>
            <button className="lab-btn primary" onClick={run} disabled={busy} style={{ width: "100%" }}>
              {busy ? "Running…" : "Run experiment"}
            </button>
            {err && <p role="alert" className="lab-section-sub" style={{ marginTop: 10 }}>Run failed: {err}</p>}
          </aside>

          <div>
            <div className="lab-kpis">
              <Kpi label="Minimum bus voltage" value={m ? m.minVdcV.toFixed(1) : "—"} unit="V" />
              <Kpi label="Largest deviation" value={m ? m.maxDeviationPercent.toFixed(1) : "—"} unit="% of V_ref" />
              <Kpi label="Energy drawn from link" value={m ? formatEnergyDeficitKj(m) : "—"} unit="kJ" />
              <Kpi label="Settles within ±1%" value={m ? (m.recoveryElapsedS === null ? "never" : (m.recoveryElapsedS * 1000).toFixed(0)) : "—"} unit={m && m.recoveryElapsedS !== null ? "ms" : ""} />
            </div>
            {data && t && (
              <div className="lab-grid lab-g2">
                <div className="lab-panel">
                  <LineChart
                    title="DC bus voltage"
                    unit="V"
                    series={[{ name: "V_dc", x: t.time_s, y: t.v_dc_v, color: SVG_COLOR.accent }]}
                    markers={data.events.map((e) => ({ x: e.time_s, label: e.label }))}
                    hlines={[{ y: data.thresholds.voltage_reference_v, label: "V_ref", color: SVG_COLOR.muted }]}
                  />
                </div>
                <div className="lab-panel">
                  <LineChart
                    title="Power balance"
                    unit="kW"
                    series={[
                      { name: "P_sst", x: t.time_s, y: t.p_sst_w.map((v) => v / 1000), color: SVG_COLOR.accent },
                      { name: "P_load", x: t.time_s, y: t.p_load_w.map((v) => v / 1000), color: SVG_COLOR.textPrimary },
                    ]}
                    markers={data.events.map((e) => ({ x: e.time_s, label: e.label }))}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  );
}

function Kpi({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="lab-kpi">
      <div className="l">{label}</div>
      <div>
        <span className="lab-value">{value}</span>
        {unit && <span className="lab-unit">{unit}</span>}
      </div>
    </div>
  );
}
