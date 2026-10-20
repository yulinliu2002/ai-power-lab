"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { EngineeringInterpretation } from "../components/EngineeringInterpretation";
import { EngineeringTakeaway } from "../components/EngineeringTakeaway";
import {
  BASELINE_EXPERIMENT_PARAMS,
  CAPACITANCE_RANGE,
  FINAL_FRACTION_RANGE,
  TIME_CONSTANT_RANGE,
  type ExperimentParams,
} from "../components/ExperimentPanel";
import { PowerFlowSchematic } from "../components/PowerFlowSchematic";
import { ProtectionCoordination } from "../components/ProtectionCoordination";
import { ProtectionTimeline } from "../components/ProtectionTimeline";
import { SCENARIO_OPTIONS } from "../components/ScenarioSelector";
import { ScenarioComparison } from "../components/ScenarioComparison";
import { SensitivityStudy } from "../components/SensitivityStudy";
import { SignalPathRail } from "../components/SignalPathRail";
import { StageNav } from "../components/StageNav";
import { TelemetryChart } from "../components/TelemetryChart";
import { TimeScrubber } from "../components/TimeScrubber";
import { TransientMetricsPanel } from "../components/TransientMetricsPanel";
import { DISCLOSURES } from "../lib/architectureChoicesData";
import {
  FIXED_PRESET_NOTE,
  MODEL_DOES_NOT_REPRESENT,
  NOT_VALIDATED_STATEMENT,
  POWER_BALANCE_CAPTION,
  POWER_BALANCE_CAPTION_LOAD_STEP,
  PROTECTION_COVERAGE_STATEMENT,
  STALE_RUN_MARKER,
  SWEEP_LOAD_STEP_ONLY,
  UNRUN_VALUES_MARKER,
  VDC_CHART_CAPTION,
} from "../lib/sandboxTakeawayData";
import {
  fetchLoadStep,
  fetchScenario,
  fetchScenarioComparison,
  sampleAt,
  type LoadStepResponse,
  type ScenarioComparisonResponse,
  type ScenarioName,
  type ScenarioRunResponse,
} from "../lib/simulationApi";
import { busStatus, sstStatus } from "../lib/statusRoles";
import { SVG_COLOR } from "../lib/theme";
import { computeTransientMetrics, formatEnergyDeficitKj } from "../lib/transientMetrics";

/**
 * Advanced Sandbox (SPEC-014 Scope A) in the "instrument console" composition:
 * a control rail (Stage 1) beside the observe stage (Stage 2) where the live
 * state and the principal transient dominate; investigate (Stage 3) and the
 * takeaway (Stage 4) follow. All state logic, request guards and behaviors are
 * unchanged from the four-stage restructure; this layer is composition only.
 * Every large live value reads the displayed run at the scrubber's sample.
 */
// The initial AI load fraction (before the step) is fixed in V1 --
// Scenario A always starts at 40% rated load, matching
// `backend/schemas.py: LoadStepRequest.initial_fraction`'s own
// default. Only the final (post-step) load is an experiment variable.
const INITIAL_FRACTION = 0.4;

const STAGES = [
  { id: "stage-configure", n: 1, label: "Configure & run" },
  { id: "stage-observe", n: 2, label: "Observe & explain" },
  { id: "stage-investigate", n: 3, label: "Investigate & compare" },
  { id: "stage-takeaway", n: 4, label: "Engineering takeaway" },
] as const;

/**
 * The scrubber's default position for a freshly-loaded run: the
 * voltage minimum, not t=0. A first-time viewer should land on the
 * moment the transient is most visible, not on the flat pre-event
 * steady state.
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
  | { status: "ready"; data: ScenarioRunResponse };

type ComparisonState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ScenarioComparisonResponse };

/** Stage 3 study choice. "none" until the learner picks one. */
type StudyMode = "none" | "sweep" | "compare";

const SCENARIO_LABEL: Record<ScenarioName, string> = Object.fromEntries(
  SCENARIO_OPTIONS.map((option) => [option.key, option.label]),
) as Record<ScenarioName, string>;

function paramsEqual(a: ExperimentParams, b: ExperimentParams): boolean {
  return (
    a.finalFraction === b.finalFraction &&
    a.capacitanceF === b.capacitanceF &&
    a.timeConstantS === b.timeConstantS
  );
}

export default function SandboxPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [activeScenario, setActiveScenario] = useState<ScenarioName>("load_step");
  const [index, setIndex] = useState(0);
  const [draftParams, setDraftParams] = useState<ExperimentParams>(BASELINE_EXPERIMENT_PARAMS);
  // The parameters that produced the displayed Load Step run; null means
  // the preset-default run (initial load, scenario switch, or Reset).
  const [displayedParams, setDisplayedParams] = useState<ExperimentParams | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const requestedRef = useRef(false);

  // Stage 3. Compare All is a separate lane from the single run: it never
  // touches `activeScenario`/`state`, so the single-run view is always
  // exactly what it was. It is fetched on every entry into the Compare
  // study, with its own request-generation guard so a rapid re-entry can
  // never let an earlier, slower fetch overwrite a later one's result.
  const [studyMode, setStudyMode] = useState<StudyMode>("none");
  const [comparisonState, setComparisonState] = useState<ComparisonState>({ status: "idle" });
  const comparisonRequestGenerationRef = useRef(0);

  // Monotonically increasing request generation. Every fetch-starting
  // action (initial load, a scenario selection, an experiment run)
  // takes the next number and only applies its result if it is still
  // the most recent request when it resolves -- so a slow RUN
  // EXPERIMENT response can never land after (and overwrite) a
  // scenario switched to in the meantime, or vice versa (SPEC-008
  // AC-009: no stale value is ever shown, regardless of which request
  // started it or finishes last).
  const requestGenerationRef = useRef(0);

  // Shared by RUN EXPERIMENT and RESET -- one fetch, one returned dataset,
  // one place that replaces `state`. Only reachable while Load Step is
  // selected (the parameter controls are Load-Step-only).
  const runExperiment = useCallback((params: ExperimentParams, asPreset = false) => {
    const generation = ++requestGenerationRef.current;
    setIsRunning(true);
    setRunError(null);
    fetchLoadStep({
      final_fraction: params.finalFraction,
      capacitance_f: params.capacitanceF,
      time_constant_s: params.timeConstantS,
    })
      .then((data) => {
        if (requestGenerationRef.current !== generation) return;
        setState({ status: "ready", data });
        setDisplayedParams(asPreset ? null : params);
        setIndex(defaultIndexFor(data));
      })
      .catch((error: unknown) => {
        if (requestGenerationRef.current !== generation) return;
        setRunError(error instanceof Error ? error.message : "Unknown error");
      })
      .finally(() => {
        if (requestGenerationRef.current === generation) setIsRunning(false);
      });
  }, []);

  // Selecting any scenario option (SPEC-008 AC-009): clears to the
  // same "loading" placeholder the initial mount uses, so no stale
  // KPI/schematic/chart/Timeline value from the previous scenario is
  // ever visible underneath the new fetch, then dispatches to the
  // matching endpoint.
  const selectScenario = useCallback((scenario: ScenarioName) => {
    const generation = ++requestGenerationRef.current;
    setActiveScenario(scenario);
    setState({ status: "loading" });
    setDisplayedParams(null);
    // Supersedes any in-flight RUN EXPERIMENT request (its own stale
    // generation check will now skip applying its result) -- also
    // clear its "Running…" state directly, since that request's own
    // `finally` will no longer run it.
    setIsRunning(false);
    setRunError(null);
    fetchScenario(scenario)
      .then((data) => {
        if (requestGenerationRef.current !== generation) return;
        setState({ status: "ready", data });
        setIndex(scenario === "load_step" ? defaultIndexFor(data as LoadStepResponse) : 0);
      })
      .catch((error: unknown) => {
        if (requestGenerationRef.current !== generation) return;
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      });
  }, []);

  useEffect(() => {
    // Guards against React Strict Mode's dev-only double effect
    // invocation, which would otherwise dispatch this fetch twice on
    // a single page load -- the ref persists across that synthetic
    // mount/cleanup/remount, unlike a plain local variable.
    if (requestedRef.current) return;
    requestedRef.current = true;

    const generation = ++requestGenerationRef.current;
    fetchLoadStep()
      .then((data) => {
        if (requestGenerationRef.current !== generation) return;
        setState({ status: "ready", data });
        setIndex(defaultIndexFor(data));
      })
      .catch((error: unknown) => {
        if (requestGenerationRef.current !== generation) return;
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      });
  }, []);

  const handleReset = useCallback(() => {
    setDraftParams(BASELINE_EXPERIMENT_PARAMS);
    runExperiment(BASELINE_EXPERIMENT_PARAMS, true);
  }, [runExperiment]);

  const fetchComparison = useCallback(() => {
    const generation = ++comparisonRequestGenerationRef.current;
    setComparisonState({ status: "loading" });
    fetchScenarioComparison()
      .then((data) => {
        if (comparisonRequestGenerationRef.current !== generation) return;
        setComparisonState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (comparisonRequestGenerationRef.current !== generation) return;
        setComparisonState({
          status: "error",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      });
  }, []);

  const selectStudy = useCallback(
    (mode: StudyMode) => {
      // A fetch on every *entry* into the Compare study (not on a repeat
      // click while it is already selected).
      if (mode === "compare" && studyMode !== "compare") fetchComparison();
      setStudyMode(mode);
    },
    [studyMode, fetchComparison],
  );

  const readyData = state.status === "ready" ? state.data : null;
  const isLoadStep = activeScenario === "load_step";

  // Fixed analysis over the whole run, computed once per fetched
  // response -- not recomputed on every scrubber move. Load-Step-only
  // (SPEC-008 §12): `computeTransientMetrics` anchors to `events[0]`,
  // which is absent or protection-derived (not a load event) for
  // Scenarios B-E, so it is never called for them.
  const metrics = useMemo(
    () => (readyData && readyData.scenario === "load_step" ? computeTransientMetrics(readyData as LoadStepResponse) : null),
    [readyData],
  );

  const loadRatedPowerW = readyData ? readyData.timeseries.p_load_w[0] / INITIAL_FRACTION : 0;
  const initialPLoadKw = readyData ? readyData.timeseries.p_load_w[0] / 1e3 : 0;
  const shownParams = displayedParams ?? BASELINE_EXPERIMENT_PARAMS;
  const draftDiffersFromRun = isLoadStep && !paramsEqual(draftParams, shownParams);

  const describeParams = (p: ExperimentParams) =>
    `AI load step to ${((p.finalFraction * loadRatedPowerW) / 1e3).toFixed(0)} kW, C_dc = ${p.capacitanceF.toFixed(3)} F, τ_sst = ${(p.timeConstantS * 1000).toFixed(0)} ms`;
  const provenance = !readyData
    ? ""
    : !isLoadStep
      ? `Showing ${SCENARIO_LABEL[activeScenario]} (fixed preset).`
      : displayedParams === null
        ? `Showing Load Step with preset defaults: ${describeParams(BASELINE_EXPERIMENT_PARAMS)}.`
        : `Showing Load Step with experiment values: ${describeParams(displayedParams)}.`;

  return (
    <main className="ic-page">
      <header className="ic-head">
        <div>
          <p className="ic-eyebrow">Free experimentation on one simplified slice of one architecture</p>
          <h1 className="ic-h1">Advanced Sandbox</h1>
          <p className="ic-lede">
            Pick a disturbance, set the parameters, run it, and watch the power system respond. For a guided
            walkthrough first, see{" "}
            <Link href="/learn" className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
              Learn by Example
            </Link>
            .
          </p>
          <p className="ic-small" style={{ marginTop: 10 }}>
            Next:{" "}
            <Link href="/architecture" className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
              Architecture Choices: compare the three architectures
            </Link>
          </p>
        </div>
        <div style={{ borderLeft: "2px solid var(--color-text-primary)", paddingLeft: 18 }} data-testid="sandbox-scope">
          <p className="ic-eyebrow" style={{ marginBottom: 6 }}>Scope of this simulation</p>
          <p className="ic-small" style={{ color: "var(--color-text-primary)", fontSize: 13.5 }}>{DISCLOSURES.sim}</p>
        </div>
      </header>

      <SignalPathRail architecture="mv-to-800vdc" simulatedSlice note="Simulated slice of one conceptual architecture" />

      <div style={{ display: "grid", gap: 8, marginTop: 14 }}>
        <StageNav label="Sandbox stages" stages={STAGES} />
        <details className="max-w-3xl" data-testid="model-scope">
          <summary className="cursor-pointer font-mono text-meta uppercase text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
            Model scope and limits
          </summary>
          <ul className="mt-2 flex flex-col gap-1.5 text-[13px] leading-relaxed text-secondary">
            <li>{DISCLOSURES.sim}</li>
            <li>{MODEL_DOES_NOT_REPRESENT}</li>
            <li>{PROTECTION_COVERAGE_STATEMENT}</li>
            <li>{NOT_VALIDATED_STATEMENT}</li>
          </ul>
        </details>
      </div>

      <div className="ic-console">
        <aside id="stage-configure" className="ic-ctrl" aria-labelledby="stage-configure-h">
          <div>
            <h2 id="stage-configure-h" data-stage-heading tabIndex={-1} className="ic-eyebrow focus:outline-none">
              1 · Configure &amp; run
            </h2>
            <p className="ic-small" style={{ marginBottom: 8 }}>What disturbance, and with what parameters?</p>
            <div className="ic-scen" role="radiogroup" aria-label="Scenario" data-testid="scenario-select">
              {SCENARIO_OPTIONS.map((o) => (
                <button
                  key={o.key}
                  type="button"
                  role="radio"
                  aria-checked={o.key === activeScenario}
                  disabled={state.status === "loading"}
                  data-testid={`scenario-option-${o.key}`}
                  onClick={() => selectScenario(o.key)}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
          {isLoadStep ? (
            readyData ? (
              <>
                <Slider
                  label="AI load step (kW, final demand)"
                  short="AI load step"
                  unit="kW"
                  readout={`${initialPLoadKw.toFixed(0)} → ${((draftParams.finalFraction * loadRatedPowerW) / 1e3).toFixed(0)}`}
                  value={draftParams.finalFraction}
                  range={FINAL_FRACTION_RANGE}
                  disabled={isRunning}
                  onChange={(v) => setDraftParams({ ...draftParams, finalFraction: v })}
                  help="Final AI demand after the step, an illustrative test input. In this model, a larger step opens a larger initial gap between demand and SST output, because SST output follows demand with the response time set below."
                />
                <Slider
                  label="DC bus capacitance C_dc (F)"
                  short="DC bus capacitance C_dc"
                  unit="F"
                  readout={draftParams.capacitanceF.toFixed(3)}
                  value={draftParams.capacitanceF}
                  range={CAPACITANCE_RANGE}
                  disabled={isRunning}
                  onChange={(v) => setDraftParams({ ...draftParams, capacitanceF: v })}
                  help="One lumped capacitance for the whole bus. From E = ½·C·V², the same energy drawn from the bus moves V_dc less when C is larger. This value is not a sized or measured bus."
                />
                <Slider
                  label="SST response time τ_sst (ms)"
                  short="SST response time τ_sst"
                  unit="ms"
                  readout={(draftParams.timeConstantS * 1000).toFixed(0)}
                  value={draftParams.timeConstantS}
                  range={TIME_CONSTANT_RANGE}
                  disabled={isRunning}
                  onChange={(v) => setDraftParams({ ...draftParams, timeConstantS: v })}
                  help="Time constant of a first-order lag on SST output power. It is a modeling assumption, not a measured or guaranteed hardware bandwidth. A longer τ_sst keeps the gap between demand and SST output open for longer."
                />
                <div style={{ display: "grid", gap: 8 }}>
                  <button type="button" className="ic-run" disabled={isRunning} onClick={() => runExperiment(draftParams)}>
                    {isRunning ? "Running…" : "Run Experiment"}
                  </button>
                  <button type="button" className="ic-ghost" disabled={isRunning} onClick={handleReset}>
                    Reset to preset
                  </button>
                  {draftDiffersFromRun && (
                    <p data-testid="unrun-values" className="ic-small ic-mono">{UNRUN_VALUES_MARKER}</p>
                  )}
                  {runError && <p className="ic-small" style={{ color: "var(--color-status-critical)" }}>{runError}</p>}
                </div>
              </>
            ) : (
              <p className="ic-small">Parameters appear once the run has loaded.</p>
            )
          ) : (
            <p data-testid="fixed-preset-note" className="ic-small">{FIXED_PRESET_NOTE}</p>
          )}
        </aside>

        <section id="stage-observe" className="ic-stage" aria-labelledby="stage-observe-h">
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 8 }}>
            <h2 id="stage-observe-h" data-stage-heading tabIndex={-1} className="ic-eyebrow focus:outline-none" style={{ margin: 0 }}>
              2 · Observe &amp; explain
            </h2>
            {readyData && (
              <div className="ic-small" style={{ textAlign: "right" }}>
                <span data-testid="run-provenance">{provenance}</span>
                {draftDiffersFromRun && <span data-testid="run-stale"> {STALE_RUN_MARKER}</span>}
              </div>
            )}
          </div>
          {state.status === "loading" && <p className="ic-small ic-mono">LOADING TELEMETRY…</p>}
          {state.status === "error" && (
            <p className="ic-small" style={{ color: "var(--color-status-critical)" }}>API ERROR: {state.message}</p>
          )}
          {readyData && <Observe data={readyData} index={index} setIndex={setIndex} metrics={metrics} />}
        </section>
      </div>

      {readyData && (
        <section className="ic-section ic-bare" aria-label="Protection">
          <h2 className="ic-h2"><b>Protection</b> timeline, outcome and coordination</h2>
          <div className="ic-two" data-testid="protection-group" style={{ marginTop: 14 }}>
            <ProtectionTimeline timeline={readyData.protection_timeline} />
            <ProtectionCoordination timeline={readyData.protection_timeline} />
          </div>
        </section>
      )}

      <section id="stage-investigate" className="ic-section" aria-labelledby="stage-investigate-h">
        <h2 id="stage-investigate-h" data-stage-heading tabIndex={-1} className="ic-h2 focus:outline-none">
          <b>3 · Investigate &amp; compare</b> how sensitive is this, and how do the scenarios differ?
        </h2>
        <fieldset className="ic-seg" data-testid="study-chooser" style={{ marginTop: 14 }}>
          <legend className="sr-only">Study</legend>
          <StudyOption id="sweep" label="Vary a parameter" selected={studyMode === "sweep"} disabled={!isLoadStep} onSelect={() => selectStudy("sweep")} />
          <StudyOption id="compare" label="Compare all five scenarios" selected={studyMode === "compare"} onSelect={() => selectStudy("compare")} />
        </fieldset>
        {!isLoadStep && studyMode !== "sweep" && (
          <p data-testid="sweep-disabled-reason" className="ic-small" style={{ marginBottom: 8 }}>
            {SWEEP_LOAD_STEP_ONLY} Select Load Step above to use it.
          </p>
        )}
        {studyMode === "none" && (
          <p className="ic-small">Choose a study: sweep one parameter around the values set above, or compare all five fixed scenarios.</p>
        )}
        {isLoadStep && (
          <div hidden={studyMode !== "sweep"}>
            <SensitivityStudy draft={draftParams} embedded />
          </div>
        )}
        {studyMode === "sweep" && !isLoadStep && (
          <p data-testid="sweep-unavailable" className="ic-small">{SWEEP_LOAD_STEP_ONLY} Select Load Step above to use it.</p>
        )}
        {studyMode === "compare" && (
          <>
            {comparisonState.status === "loading" && <p className="ic-small ic-mono">LOADING COMPARISON&hellip;</p>}
            {comparisonState.status === "error" && (
              <div className="flex flex-wrap items-center gap-3">
                <p className="ic-small" style={{ color: "var(--color-status-critical)" }}>API ERROR: {comparisonState.message}</p>
                <button type="button" onClick={fetchComparison} className="ic-ghost" style={{ width: "auto" }}>
                  Retry
                </button>
              </div>
            )}
            {comparisonState.status === "ready" && <ScenarioComparison entries={comparisonState.data.scenarios} />}
          </>
        )}
      </section>

      <section id="stage-takeaway" className="ic-section" aria-labelledby="stage-takeaway-h">
        <h2 id="stage-takeaway-h" data-stage-heading tabIndex={-1} className="ic-h2 focus:outline-none" style={{ marginBottom: 14 }}>
          <b>4 · Engineering takeaway</b> what can I conclude, and what can&rsquo;t I?
        </h2>
        {readyData ? (
          <EngineeringTakeaway data={readyData} metrics={metrics} provenance={provenance} />
        ) : (
          <p className="ic-small">The takeaway appears once a scenario has run.</p>
        )}
      </section>
    </main>
  );
}

function Slider({
  label, short, unit, readout, value, range, disabled, onChange, help,
}: {
  label: string; short: string; unit: string; readout: string; value: number;
  range: { min: number; max: number; step: number }; disabled: boolean; onChange: (v: number) => void; help: string;
}) {
  return (
    <div className="ic-slider">
      <div className="ic-slider-row">
        <span>{short}</span>
        <span className="v">{readout}<span className="u"> {unit}</span></span>
      </div>
      <input
        type="range"
        aria-label={label}
        min={range.min}
        max={range.max}
        step={range.step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <details>
        <summary>What does this do?</summary>
        <p className="ic-small" data-testid="slider-description" style={{ marginTop: 6 }}>{help}</p>
      </details>
    </div>
  );
}

function StudyOption({ id, label, selected, disabled = false, onSelect }: { id: "sweep" | "compare"; label: string; selected: boolean; disabled?: boolean; onSelect: () => void }) {
  return (
    <label className="relative">
      <input type="radio" name="study" checked={selected} disabled={disabled} onChange={onSelect} data-testid={`study-option-${id}`} className="peer sr-only" />
      <span className="ic-segbtn peer-focus-visible:outline-2 peer-focus-visible:outline-offset-[-2px] peer-focus-visible:outline-secondary peer-disabled:cursor-not-allowed peer-disabled:opacity-60" data-on={selected}>
        {label}
      </span>
    </label>
  );
}

const ROLE_COLOR: Record<string, string> = {
  good: "var(--color-status-good)",
  warning: "var(--color-status-warning)",
  critical: "var(--color-status-critical)",
  neutral: "var(--color-status-neutral)",
};

function Observe({ data, index, setIndex, metrics }: { data: ScenarioRunResponse; index: number; setIndex: (i: number) => void; metrics: ReturnType<typeof computeTransientMetrics> }) {
  // One index selected from the already-loaded run -- no new simulation
  // run, no API request, no interpolation. Every live value below reads it.
  const sample = sampleAt(data, index);
  const timeS = data.timeseries.time_s;
  const eventMarkers = data.events.map((e) => ({ time: e.time_s, label: e.label }));
  const vref = data.thresholds.voltage_reference_v;
  const bus = busStatus(sample.v_dc_v, vref);
  const sst = sstStatus(sample.operating_state);
  const gap = sample.p_load_w - sample.p_sst_w;
  const isLoadStep = data.scenario === "load_step";
  const event = data.events[0];
  const initialPLoadKw = data.timeseries.p_load_w[0] / 1e3;
  const finalPLoadKw = data.timeseries.p_load_w[data.timeseries.p_load_w.length - 1] / 1e3;
  const vFinal = data.timeseries.v_dc_v[data.timeseries.v_dc_v.length - 1];

  return (
    <>
      {isLoadStep && event && (
        <div className="ic-event" data-testid="event-banner">
          <span className="ic-eyebrow" style={{ margin: 0 }}>The event</span>
          <span className="ic-mono" style={{ fontSize: 20, fontWeight: 600 }}>
            {initialPLoadKw.toFixed(0)} <span className="text-secondary">&rarr;</span> {finalPLoadKw.toFixed(0)}{" "}
            <span style={{ fontSize: 12, fontWeight: 400 }} className="text-secondary">kW</span>
          </span>
          <span className="ic-small ic-mono">at t = {event.time_s.toFixed(3)} s</span>
          <p className="ic-small" style={{ maxWidth: "48ch" }}>
            AI compute demand jumps almost instantly &mdash; far faster than this model&rsquo;s SST (solid-state
            transformer) response time constant lets delivered power follow.
          </p>
        </div>
      )}

      <div data-testid="state-at-time" className="flex flex-col gap-6">
        <div className="ic-metrics">
          <div>
            <p className="ic-eyebrow" style={{ margin: "0 0 6px" }}>Current · at the scrubber time</p>
            <div className="ic-hero-num">
              {sample.v_dc_v.toFixed(1)}
              <small>V</small>
            </div>
            <div className="ic-hero-cap">
              <span className="ic-dot" style={{ background: ROLE_COLOR[bus.role] }} />
              DC bus voltage V_dc at t = {sample.t_s.toFixed(4)} s
            </div>
            <dl className="ic-refvals" data-testid="reference-values">
              <div>
                <dt>Reference</dt>
                <dd>{vref.toFixed(0)} V</dd>
              </div>
              {metrics && (
                <div>
                  <dt>Minimum in run</dt>
                  <dd>{metrics.minVdcV.toFixed(1)} V at {metrics.minVdcTimeS.toFixed(3)} s</dd>
                </div>
              )}
              <div>
                <dt>Final (end of run)</dt>
                <dd>{vFinal.toFixed(1)} V</dd>
              </div>
            </dl>
          </div>
          <div className="ic-minis">
            <div>
              <div className="l">Current P_load · AI demand</div>
              <div className="n">{(sample.p_load_w / 1e3).toFixed(1)}<small>kW</small></div>
            </div>
            <div>
              <div className="l" style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span className="ic-dot" style={{ background: ROLE_COLOR[sst.role] }} />
                Current P_sst · delivered
              </div>
              <div className="n">{(sample.p_sst_w / 1e3).toFixed(1)}<small>kW</small></div>
            </div>
            <div>
              <div className="l">Current ΔP · {gap >= 0 ? "power deficit, bus is supplying this" : "power surplus, bus is recharging"}</div>
              <div className="n">{(Math.abs(gap) / 1e3).toFixed(1)}<small>kW</small></div>
            </div>
          </div>
        </div>

        <div className="ic-bare ic-schematic">
          <PowerFlowSchematic
            live={{
              sample,
              ratedPowerW: data.thresholds.rated_power_w,
              voltageReferenceV: vref,
              capacitanceF: data.thresholds.capacitance_f,
            }}
          />
        </div>

        <div className="ic-hero-chart">
          <TelemetryChart
            title="DC Bus Voltage — V_dc(t)"
            timeS={timeS}
            series={[{ label: "V_dc", values: data.timeseries.v_dc_v, color: SVG_COLOR.accent }]}
            yUnit="V"
            currentTimeS={sample.t_s}
            referenceLines={[{ value: vref, label: `V_ref = ${vref.toFixed(0)} V` }]}
            eventMarkers={eventMarkers}
            markerPoint={metrics ? { time: metrics.minVdcTimeS, value: metrics.minVdcV, label: `min ${metrics.minVdcV.toFixed(0)} V` } : undefined}
          />
          <TimeScrubber timeS={timeS} index={index} onChange={setIndex} />
          <details data-testid="chart-help-vdc" className="ic-small" style={{ padding: "8px 4px" }}>
            <summary style={{ cursor: "pointer" }}>How to read this chart</summary>
            <p style={{ marginTop: 6 }}>{VDC_CHART_CAPTION}</p>
          </details>
        </div>
      </div>

      <div className="ic-split">
        <div className="ic-hero-chart">
          <TelemetryChart
            title="Power Balance — P_load vs P_sst"
            timeS={timeS}
            series={[
              { label: "P_sst", values: data.timeseries.p_sst_w.map((w) => w / 1e3), color: SVG_COLOR.accent },
              { label: "P_load", values: data.timeseries.p_load_w.map((w) => w / 1e3), color: SVG_COLOR.neutral, dashed: true },
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
                    label: `shaded area ≈ ${formatEnergyDeficitKj(metrics)} kJ drawn from the DC bus (energy, not power)`,
                  }
                : undefined
            }
          />
          <details data-testid="chart-help-power" className="ic-small" style={{ padding: "8px 4px" }}>
            <summary style={{ cursor: "pointer" }}>How to read this chart</summary>
            <p style={{ marginTop: 6 }}>
              {POWER_BALANCE_CAPTION}
              {isLoadStep ? ` ${POWER_BALANCE_CAPTION_LOAD_STEP}` : ""}
            </p>
          </details>
        </div>
        {metrics && (
          <div className="ic-explain">
            <EngineeringInterpretation metrics={metrics} voltageReferenceV={vref} />
          </div>
        )}
      </div>

      {metrics && (
        <>
          <TransientMetricsPanel metrics={metrics} voltageReferenceV={vref} comfortable variant="console" />
        </>
      )}
    </>
  );
}
