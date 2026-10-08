"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { EngineeringInterpretation } from "./components/EngineeringInterpretation";
import { KpiReadout } from "./components/KpiTile";
import { PowerFlowSchematic } from "./components/PowerFlowSchematic";
import { TelemetryChart } from "./components/TelemetryChart";
import { TimeScrubber } from "./components/TimeScrubber";
import { TransientMetricsPanel } from "./components/TransientMetricsPanel";
import {
  fetchLoadStep,
  sampleAt,
  type LoadStepResponse,
  type Sample,
} from "./lib/simulationApi";
import { busStatus, gridStatus, sstStatus } from "./lib/statusRoles";
import { SVG_COLOR } from "./lib/theme";
import { computeTransientMetrics } from "./lib/transientMetrics";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: LoadStepResponse };

export default function Home() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [index, setIndex] = useState(0);
  const requestedRef = useRef(false);

  useEffect(() => {
    // Guards against React Strict Mode's dev-only double effect
    // invocation, which would otherwise dispatch this fetch twice on
    // a single page load -- the ref persists across that synthetic
    // mount/cleanup/remount, unlike a plain local variable.
    if (requestedRef.current) return;
    requestedRef.current = true;

    fetchLoadStep()
      .then((data) => {
        setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      });
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col gap-3 px-6 py-4">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-hairline pb-2">
        <div className="flex items-baseline gap-3">
          <h1 className="text-lg font-bold tracking-tight text-primary">
            AI POWER LAB
          </h1>
          <p className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-secondary">
            SST / 800 VDC CONTROL CENTER
          </p>
        </div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.04em] text-muted">
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

      {state.status === "ready" && (
        <Console data={state.data} index={index} onIndexChange={setIndex} />
      )}
    </main>
  );
}

function Console({
  data,
  index,
  onIndexChange,
}: {
  data: LoadStepResponse;
  index: number;
  onIndexChange: (index: number) => void;
}) {
  // One index selected from the already-loaded run -- no new
  // simulation run, no new API request, no interpolation.
  const sample = sampleAt(data, index);
  const timeS = data.timeseries.time_s;
  const eventMarkers = data.events.map((e) => ({ time: e.time_s, label: e.label }));

  // Fixed analysis over the whole run, computed once per fetched
  // response -- not recomputed on every scrubber move.
  const metrics = useMemo(() => computeTransientMetrics(data), [data]);

  return (
    <div className="flex flex-col gap-3">
      <KpiStrip sample={sample} voltageReferenceV={data.thresholds.voltage_reference_v} />
      <PowerFlowSchematic
        sample={sample}
        ratedPowerW={data.thresholds.rated_power_w}
        voltageReferenceV={data.thresholds.voltage_reference_v}
      />
      <TimeScrubber timeS={timeS} index={index} onChange={onIndexChange} />

      <div className="flex flex-col gap-1.5">
        <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
          TELEMETRY
        </span>
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          <TelemetryChart
            title="DC Bus Voltage vs Time"
            timeS={timeS}
            series={[{ label: "V_dc", values: data.timeseries.v_dc_v, color: SVG_COLOR.accent }]}
            yUnit="V"
            currentTimeS={sample.t_s}
            referenceLines={[
              {
                value: data.thresholds.voltage_reference_v,
                label: `V_ref = ${data.thresholds.voltage_reference_v.toFixed(0)} V`,
              },
            ]}
            eventMarkers={eventMarkers}
          />
          <TelemetryChart
            title="AI Load Power vs SST Delivered Power"
            timeS={timeS}
            series={[
              {
                label: "P_sst",
                values: data.timeseries.p_sst_w.map((w) => w / 1e3),
                color: SVG_COLOR.accent,
              },
              {
                label: "P_load",
                values: data.timeseries.p_load_w.map((w) => w / 1e3),
                color: SVG_COLOR.neutral,
                dashed: true,
              },
            ]}
            yUnit="kW"
            currentTimeS={sample.t_s}
            eventMarkers={eventMarkers}
          />
        </div>
      </div>

      {metrics && (
        <>
          <TransientMetricsPanel
            metrics={metrics}
            voltageReferenceV={data.thresholds.voltage_reference_v}
          />
          <EngineeringInterpretation
            metrics={metrics}
            voltageReferenceV={data.thresholds.voltage_reference_v}
          />
        </>
      )}
    </div>
  );
}

function KpiStrip({
  sample,
  voltageReferenceV,
}: {
  sample: Sample;
  voltageReferenceV: number;
}) {
  const grid = gridStatus(sample.grid_voltage_pu, sample.grid_available);
  const bus = busStatus(sample.v_dc_v, voltageReferenceV);
  const sst = sstStatus(sample.operating_state);

  const gridValue = sample.grid_available ? sample.grid_voltage_pu.toFixed(2) : "LOST";
  const gridUnit = sample.grid_available ? "p.u." : "";

  return (
    <div className="grid grid-cols-2 gap-x-2 border-y border-hairline sm:grid-cols-3 lg:grid-cols-6 lg:gap-x-0 lg:divide-x lg:divide-hairline">
      <KpiReadout label="VDC" value={sample.v_dc_v.toFixed(1)} unit="V" role={bus.role} />
      <KpiReadout
        label="P_SST"
        value={(sample.p_sst_w / 1e3).toFixed(1)}
        unit="kW"
        role={sst.role}
      />
      <KpiReadout
        label="P_LOAD"
        value={(sample.p_load_w / 1e3).toFixed(1)}
        unit="kW"
        role="neutral"
      />
      <KpiReadout
        label="TEMPERATURE"
        value={sample.temperature_c.toFixed(1)}
        unit="°C"
        role={sst.role}
      />
      <KpiReadout
        label="DERATE"
        value={(sample.derate_factor * 100).toFixed(0)}
        unit="%"
        role={sst.role}
      />
      <KpiReadout label="GRID" value={gridValue} unit={gridUnit} role={grid.role} />
    </div>
  );
}
