"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { EngineeringInterpretation } from "./components/EngineeringInterpretation";
import {
  BASELINE_EXPERIMENT_PARAMS,
  ExperimentPanel,
  type ExperimentParams,
} from "./components/ExperimentPanel";
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
import { busStatus, sstStatus } from "./lib/statusRoles";
import { SVG_COLOR } from "./lib/theme";
import { computeTransientMetrics } from "./lib/transientMetrics";

// The initial AI load fraction (before the step) is fixed in V1 --
// Scenario A always starts at 40% rated load, matching
// `backend/schemas.py: LoadStepRequest.initial_fraction`'s own
// default. Only the final (post-step) load is an experiment variable.
const INITIAL_FRACTION = 0.4;

/**
 * The scrubber's default position for a freshly-loaded run: the
 * voltage minimum, not t=0. A first-time viewer should land on the
 * moment the transient is most visible, not on the flat pre-event
 * steady state -- "preferably t=0 unless there is a better existing
 * convention" (see the experiment-controls task this followed); this
 * is that better convention.
 */
function defaultIndexFor(data: LoadStepResponse): number {
  const metrics = computeTransientMetrics(data);
  if (!metrics) return 0;
  const timeS = data.timeseries.time_s;
  let closest = 0;
  let bestDiff = Infinity;
  for (let i = 0; i < timeS.length; i++) {
    const diff = Math.abs(timeS[i] - metrics.minVdcTimeS);
    if (diff < bestDiff) {
      bestDiff = diff;
      closest = i;
    }
  }
  return closest;
}

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: LoadStepResponse };

export default function Home() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [index, setIndex] = useState(0);
  const [draftParams, setDraftParams] = useState<ExperimentParams>(BASELINE_EXPERIMENT_PARAMS);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const requestedRef = useRef(false);

  // Shared by the initial load and every later RUN EXPERIMENT /
  // RESET click -- one fetch, one returned dataset, one place that
  // replaces `state`. No component below this ever fetches on its
  // own.
  const runExperiment = useCallback((params: ExperimentParams) => {
    setIsRunning(true);
    setRunError(null);
    fetchLoadStep({
      final_fraction: params.finalFraction,
      capacitance_f: params.capacitanceF,
      time_constant_s: params.timeConstantS,
    })
      .then((data) => {
        setState({ status: "ready", data });
        setIndex(defaultIndexFor(data));
      })
      .catch((error: unknown) => {
        setRunError(error instanceof Error ? error.message : "Unknown error");
      })
      .finally(() => {
        setIsRunning(false);
      });
  }, []);

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
        setIndex(defaultIndexFor(data));
      })
      .catch((error: unknown) => {
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      });
  }, []);

  const handleReset = useCallback(() => {
    setDraftParams(BASELINE_EXPERIMENT_PARAMS);
    runExperiment(BASELINE_EXPERIMENT_PARAMS);
  }, [runExperiment]);

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
        <Console
          data={state.data}
          index={index}
          onIndexChange={setIndex}
          draftParams={draftParams}
          onDraftChange={setDraftParams}
          onRun={() => runExperiment(draftParams)}
          onReset={handleReset}
          isRunning={isRunning}
          runError={runError}
        />
      )}
    </main>
  );
}

function Console({
  data,
  index,
  onIndexChange,
  draftParams,
  onDraftChange,
  onRun,
  onReset,
  isRunning,
  runError,
}: {
  data: LoadStepResponse;
  index: number;
  onIndexChange: (index: number) => void;
  draftParams: ExperimentParams;
  onDraftChange: (params: ExperimentParams) => void;
  onRun: () => void;
  onReset: () => void;
  isRunning: boolean;
  runError: string | null;
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // One index selected from the already-loaded run -- no new
  // simulation run, no new API request, no interpolation.
  const sample = sampleAt(data, index);
  const timeS = data.timeseries.time_s;
  const eventMarkers = data.events.map((e) => ({ time: e.time_s, label: e.label }));
  const event = data.events[0];

  // Fixed analysis over the whole run, computed once per fetched
  // response -- not recomputed on every scrubber move.
  const metrics = useMemo(() => computeTransientMetrics(data), [data]);

  // The initial (pre-step) P_load sample is always real engine
  // output, never a hardcoded "160" -- and since INITIAL_FRACTION is
  // fixed, dividing it back out gives the load's rated power without
  // the frontend ever hardcoding that config value either.
  const initialPLoadKw = data.timeseries.p_load_w[0] / 1e3;
  const finalPLoadKw = data.timeseries.p_load_w[data.timeseries.p_load_w.length - 1] / 1e3;
  const loadRatedPowerW = data.timeseries.p_load_w[0] / INITIAL_FRACTION;

  return (
    <div className="flex flex-col gap-3">
      {event && (
        <EventBanner initialKw={initialPLoadKw} finalKw={finalPLoadKw} stepTimeS={event.time_s} />
      )}

      <KpiStrip sample={sample} voltageReferenceV={data.thresholds.voltage_reference_v} />

      <PowerFlowSchematic
        sample={sample}
        ratedPowerW={data.thresholds.rated_power_w}
        voltageReferenceV={data.thresholds.voltage_reference_v}
      />

      {metrics && (
        <EngineeringInterpretation
          metrics={metrics}
          voltageReferenceV={data.thresholds.voltage_reference_v}
        />
      )}

      <TimeScrubber timeS={timeS} index={index} onChange={onIndexChange} />

      <div className="flex flex-col gap-1.5">
        <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
          SYNCHRONIZED TRANSIENT
        </span>
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          <TelemetryChart
            title="DC Bus Voltage — V_dc(t)"
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
            markerPoint={
              metrics
                ? {
                    time: metrics.minVdcTimeS,
                    value: metrics.minVdcV,
                    label: `min ${metrics.minVdcV.toFixed(0)} V`,
                  }
                : undefined
            }
          />
          <TelemetryChart
            title="Power Balance — P_load vs P_sst"
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
            deficitFill={
              metrics
                ? {
                    aboveLabel: "P_load",
                    baselineLabel: "P_sst",
                    windowEndS: metrics.minVdcTimeS,
                    label: `shaded area ≈ ${metrics.energyDeficitKj.toFixed(1)} kJ drawn from the DC bus (energy, not power)`,
                  }
                : undefined
            }
          />
        </div>
      </div>

      {metrics && (
        <TransientMetricsPanel
          metrics={metrics}
          voltageReferenceV={data.thresholds.voltage_reference_v}
        />
      )}

      <div className="flex flex-col gap-1.5 border-t border-hairline pt-2">
        <button
          type="button"
          onClick={() => setAdvancedOpen((open) => !open)}
          className="flex items-center gap-1.5 self-start font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-muted"
        >
          <span className="font-mono text-[12px] leading-none">{advancedOpen ? "−" : "+"}</span>
          Advanced Experiment
        </button>
        {advancedOpen && (
          <ExperimentPanel
            draft={draftParams}
            onDraftChange={onDraftChange}
            onRun={onRun}
            onReset={onReset}
            isRunning={isRunning}
            initialPLoadKw={initialPLoadKw}
            loadRatedPowerW={loadRatedPowerW}
            error={runError}
          />
        )}
      </div>
    </div>
  );
}

/**
 * States the one thing that happens in Scenario A in plain, concrete
 * terms before any chart or number -- the "what changed" a first-time
 * reader needs before anything else makes sense. Every figure is a
 * real sample from the fetched run (first/last P_load, the engine's
 * own event marker), never a hardcoded "160 -> 320".
 */
function EventBanner({
  initialKw,
  finalKw,
  stepTimeS,
}: {
  initialKw: number;
  finalKw: number;
  stepTimeS: number;
}) {
  return (
    <section className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-hairline pb-2">
      <div className="flex items-baseline gap-3">
        <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-muted">
          THE EVENT
        </span>
        <span className="font-mono text-[18px] font-semibold tabular-nums text-primary">
          {initialKw.toFixed(0)} <span className="text-muted">&rarr;</span> {finalKw.toFixed(0)}{" "}
          <span className="text-[12px] font-normal text-muted">kW</span>
        </span>
        <span className="font-mono text-[11px] tabular-nums text-secondary">
          at t = {stepTimeS.toFixed(3)} s
        </span>
      </div>
      <p className="max-w-md text-[11.5px] leading-snug text-secondary">
        AI compute demand jumps almost instantly &mdash; far faster than this model&rsquo;s SST
        (solid-state transformer) response time constant lets delivered power follow.
      </p>
    </section>
  );
}

function KpiStrip({
  sample,
  voltageReferenceV,
}: {
  sample: Sample;
  voltageReferenceV: number;
}) {
  const bus = busStatus(sample.v_dc_v, voltageReferenceV);
  const sst = sstStatus(sample.operating_state);
  const mismatchW = sample.p_load_w - sample.p_sst_w;

  return (
    <div className="grid grid-cols-2 gap-x-2 border-y border-hairline sm:grid-cols-4 sm:gap-x-0 sm:divide-x sm:divide-hairline">
      <KpiReadout
        label="V_DC"
        caption="DC bus voltage"
        value={sample.v_dc_v.toFixed(1)}
        unit="V"
        role={bus.role}
      />
      <KpiReadout
        label="P_LOAD"
        caption="AI demand"
        value={(sample.p_load_w / 1e3).toFixed(1)}
        unit="kW"
        role="neutral"
      />
      <KpiReadout
        label="P_SST"
        caption="SST delivered power"
        value={(sample.p_sst_w / 1e3).toFixed(1)}
        unit="kW"
        role={sst.role}
      />
      <KpiReadout
        label="ΔP"
        caption={mismatchW >= 0 ? "power deficit — bus is supplying this" : "power surplus — bus is recharging"}
        value={(Math.abs(mismatchW) / 1e3).toFixed(1)}
        unit="kW"
        role="neutral"
      />
    </div>
  );
}
