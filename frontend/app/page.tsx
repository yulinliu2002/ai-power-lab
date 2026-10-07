"use client";

import { useEffect, useState } from "react";

import { KpiTile } from "./components/KpiTile";
import { fetchLoadStep, type LoadStepResponse } from "./lib/simulationApi";
import { busStatus, gridStatus, sstStatus } from "./lib/statusRoles";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: LoadStepResponse };

export default function Home() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchLoadStep()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown error",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="flex flex-1 flex-col gap-6 px-6 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight text-primary">
          AI POWER LAB
        </h1>
        <p className="font-mono text-xs uppercase tracking-[0.08em] text-secondary">
          SST / 800 VDC CONTROL CENTER
        </p>
        <p className="mt-2 text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
          Scenario A &mdash; AI Load Step
        </p>
      </header>

      {state.status === "loading" && (
        <p className="font-mono text-xs text-muted">LOADING TELEMETRY&hellip;</p>
      )}

      {state.status === "error" && (
        <p className="border border-status-critical bg-surface px-3 py-2 font-mono text-xs text-status-critical">
          API ERROR: {state.message}
        </p>
      )}

      {state.status === "ready" && <KpiStrip data={state.data} />}
    </main>
  );
}

function KpiStrip({ data }: { data: LoadStepResponse }) {
  // One static sample, t=0 -- no time interaction yet (V2 slice #1).
  const t = data.timeseries;
  const i = 0;

  const grid = gridStatus(t.grid_voltage_pu[i], t.grid_available[i]);
  const bus = busStatus(t.v_dc_v[i], data.thresholds.voltage_reference_v);
  const sst = sstStatus(t.operating_state[i]);

  const gridValue = t.grid_available[i] ? t.grid_voltage_pu[i].toFixed(2) : "LOST";
  const gridUnit = t.grid_available[i] ? "p.u." : "";

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      <KpiTile label="VDC" value={t.v_dc_v[i].toFixed(1)} unit="V" role={bus} />
      <KpiTile label="P_SST" value={(t.p_sst_w[i] / 1e3).toFixed(1)} unit="kW" role={sst} />
      <KpiTile label="P_LOAD" value={(t.p_load_w[i] / 1e3).toFixed(1)} unit="kW" role="neutral" />
      <KpiTile label="TEMPERATURE" value={t.temperature_c[i].toFixed(1)} unit="°C" role={sst} />
      <KpiTile label="DERATE" value={(t.derate_factor[i] * 100).toFixed(0)} unit="%" role={sst} />
      <KpiTile label="GRID" value={gridValue} unit={gridUnit} role={grid} />
    </div>
  );
}
