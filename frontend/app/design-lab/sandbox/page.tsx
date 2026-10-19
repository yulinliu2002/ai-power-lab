"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { DISCLOSURES } from "../../lib/architectureChoicesData";

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
  /** Parameters the displayed run was made with; null = API baseline defaults. */
  const [shown, setShown] = useState<{ f: number; c: number; t: number } | null>(null);
  /** Request generation: only the latest request may update the display. */
  const gen = useRef(0);

  const run = useCallback(async () => {
    const mine = ++gen.current;
    const snap = { f: finalFraction, c: capF, t: tau };
    setBusy(true);
    setErr(null);
    try {
      const res = await fetchLoadStep({ final_fraction: snap.f, capacitance_f: snap.c, time_constant_s: snap.t });
      if (mine !== gen.current) return;
      setData(res);
      setShown(snap);
    } catch (e) {
      if (mine !== gen.current) return;
      setErr((e as Error).message);
    } finally {
      if (mine === gen.current) setBusy(false);
    }
  }, [finalFraction, capF, tau]);

  const reset = useCallback(async () => {
    const mine = ++gen.current;
    setFinal(0.8);
    setCap(0.02);
    setTau(0.02);
    setBusy(true);
    setErr(null);
    try {
      const res = await fetchLoadStep();
      if (mine !== gen.current) return;
      setData(res);
      setShown(null);
    } catch (e) {
      if (mine !== gen.current) return;
      setErr((e as Error).message);
    } finally {
      if (mine === gen.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    // Baseline run on mount (API defaults), guarded like any other request.
    const mine = ++gen.current;
    fetchLoadStep()
      .then((res) => {
        if (mine === gen.current) setData(res);
      })
      .catch((e: Error) => {
        if (mine === gen.current) setErr(e.message);
      });
  }, []);

  const stale =
    shown !== null
      ? shown.f !== finalFraction || shown.c !== capF || shown.t !== tau
      : finalFraction !== 0.8 || capF !== 0.02 || tau !== 0.02;

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
            { tag: "Simulation scope", text: DISCLOSURES.sim },
            { tag: "Rail legend", text: "Dashed nodes are the simulated slice. Rack DC-DC conversion is not modeled; the AI load is lumped. The rail shows one representative architecture, not a universal path." },
            { tag: "Assumptions", text: "Parameters and ranges are educational assumptions. Results are model outputs, not predictions for real equipment." },
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
            <button className="lab-btn" onClick={reset} disabled={busy} style={{ width: "100%", marginTop: 8 }}>
              Reset to baseline
            </button>
            {err && <p role="alert" className="lab-section-sub" style={{ marginTop: 10 }}>Run failed: {err}</p>}
          </aside>

          <div>
            {data && (
              <p className="lab-section-sub" role="status" style={{ marginBottom: 10 }}>
                {shown
                  ? `Showing the run for ${(shown.f * 100).toFixed(0)} % post-step load, ${(shown.c * 1000).toFixed(0)} mF, ${(shown.t * 1000).toFixed(0)} ms.`
                  : "Showing the baseline run (API defaults)."}
                {stale && <b style={{ color: "var(--color-text-primary)", fontWeight: 600 }}> The parameters have changed since this run; run again to update.</b>}
              </p>
            )}
            <div className="lab-kpis">
              <Kpi label="Minimum bus voltage" value={m ? m.minVdcV.toFixed(1) : "—"} unit="V" />
              <Kpi label="Largest deviation" value={m ? m.maxDeviationPercent.toFixed(1) : "—"} unit="% of V_ref" />
              <Kpi label="Energy drawn from link" value={m ? formatEnergyDeficitKj(m) : "—"} unit="kJ" />
              <Kpi label="Settles within ±1% (before the run ends)" value={m ? (m.recoveryElapsedS === null ? "Not settled" : (m.recoveryElapsedS * 1000).toFixed(0)) : "—"} unit={m && m.recoveryElapsedS !== null ? "ms" : ""} />
            </div>
            {data && t && (
              <div className="lab-grid lab-g2">
                <div className="lab-panel">
                  <LineChart
                    title="DC bus voltage"
                    unit="V"
                    series={[{ name: "V_dc", x: t.time_s, y: t.v_dc_v, color: SVG_COLOR.accent }]}
                    markers={data.events.map((e) => ({ x: e.time_s, label: e.label }))}
                    hlines={[{ y: data.thresholds.voltage_reference_v, label: "V_ref", color: SVG_COLOR.textSecondary }]}
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
