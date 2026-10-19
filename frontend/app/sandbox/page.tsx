"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { AreaHeader } from "../components/AreaHeader";
import { BasisPanel } from "../components/BasisPanel";
import { EngineeringInterpretation } from "../components/EngineeringInterpretation";
import { EngineeringTakeaway } from "../components/EngineeringTakeaway";
import {
  BASELINE_EXPERIMENT_PARAMS,
  ExperimentPanel,
  type ExperimentParams,
} from "../components/ExperimentPanel";
import { KpiReadout } from "../components/KpiTile";
import { PowerFlowSchematic } from "../components/PowerFlowSchematic";
import { ProtectionCoordination } from "../components/ProtectionCoordination";
import { ProtectionTimeline } from "../components/ProtectionTimeline";
import { SCENARIO_OPTIONS, ScenarioSelector } from "../components/ScenarioSelector";
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
  type Sample,
} from "../lib/simulationApi";
import { busStatus, sstStatus } from "../lib/statusRoles";
import { SVG_COLOR } from "../lib/theme";
import { computeTransientMetrics, formatEnergyDeficitKj } from "../lib/transientMetrics";

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

  const provenance = !readyData
    ? ""
    : !isLoadStep
      ? `Showing ${SCENARIO_LABEL[activeScenario]} (fixed preset).`
      : displayedParams === null || paramsEqual(displayedParams, BASELINE_EXPERIMENT_PARAMS)
        ? "Showing Load Step with preset defaults."
        : `Showing Load Step with experiment values: AI load step to ${((displayedParams.finalFraction * loadRatedPowerW) / 1e3).toFixed(0)} kW, C_dc = ${displayedParams.capacitanceF.toFixed(3)} F, τ_sst = ${(displayedParams.timeConstantS * 1000).toFixed(0)} ms.`;

  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col gap-5 px-4 py-5 sm:px-6">
      <AreaHeader
        title="Advanced Sandbox"
        role="Free experimentation on one simplified slice of one architecture"
        next={{ href: "/architecture", label: "Architecture Choices: compare the three architectures" }}
      >
        <p className="text-body text-secondary">
          Want a guided walkthrough first?{" "}
          <Link
            href="/learn"
            className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
          >
            Learn by Example
          </Link>
          .
        </p>
      </AreaHeader>

      <BasisPanel title="Scope of this simulation" testId="sandbox-scope" items={[{ tag: "Simulation", text: DISCLOSURES.sim }]} />

      <SignalPathRail architecture="mv-to-800vdc" simulatedSlice note="Simulated slice of one conceptual architecture" />

      <div className="flex flex-col gap-2">
        <StageNav label="Sandbox stages" stages={STAGES} />
        <details className="max-w-3xl border border-hairline bg-surface px-3 py-2" data-testid="model-scope">
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

      {/* Stage 1 */}
      <Stage id="stage-configure" n={1} title="Configure & run" question="What disturbance, and with what parameters?">
        <ScenarioSelector selected={activeScenario} onSelect={selectScenario} disabled={state.status === "loading"} />
        {isLoadStep ? (
          readyData ? (
            <>
              <ExperimentPanel
                draft={draftParams}
                onDraftChange={setDraftParams}
                onRun={() => runExperiment(draftParams)}
                onReset={handleReset}
                isRunning={isRunning}
                initialPLoadKw={initialPLoadKw}
                loadRatedPowerW={loadRatedPowerW}
                error={runError}
              />
              {draftDiffersFromRun && (
                <p data-testid="unrun-values" className="font-mono text-[11px] text-secondary">
                  {UNRUN_VALUES_MARKER}
                </p>
              )}
            </>
          ) : (
            <p className="text-[13px] text-secondary">Parameters appear once the run has loaded.</p>
          )
        ) : (
          <p data-testid="fixed-preset-note" className="text-[13px] text-secondary">
            {FIXED_PRESET_NOTE}
          </p>
        )}
      </Stage>

      {/* Stage 2 */}
      <Stage id="stage-observe" n={2} title="Observe & explain" question="What happened, and why?">
        {state.status === "loading" && <p className="font-mono text-xs text-secondary">LOADING TELEMETRY&hellip;</p>}
        {state.status === "error" && (
          <p className="border border-status-critical bg-surface px-3 py-2 font-mono text-xs text-status-critical">
            API ERROR: {state.message}
          </p>
        )}
        {readyData && (
          <Observe
            data={readyData}
            index={index}
            onIndexChange={setIndex}
            metrics={metrics}
            provenance={provenance}
            stale={draftDiffersFromRun}
          />
        )}
      </Stage>

      {/* Stage 3 */}
      <Stage id="stage-investigate" n={3} title="Investigate & compare" question="How sensitive is this, and how do the scenarios differ?">
        <fieldset className="flex flex-wrap gap-1.5" data-testid="study-chooser">
          <legend className="sr-only">Study</legend>
          <StudyOption id="sweep" label="Vary a parameter" selected={studyMode === "sweep"} onSelect={() => selectStudy("sweep")} />
          <StudyOption id="compare" label="Compare all five scenarios" selected={studyMode === "compare"} onSelect={() => selectStudy("compare")} />
        </fieldset>
        {studyMode === "none" && (
          <p className="text-[13px] text-secondary">
            Choose a study: sweep one parameter around the values set above, or compare all five fixed scenarios.
          </p>
        )}
        {studyMode === "sweep" &&
          (isLoadStep ? (
            <SensitivityStudy draft={draftParams} embedded />
          ) : (
            <p data-testid="sweep-unavailable" className="text-[13px] text-secondary">
              {SWEEP_LOAD_STEP_ONLY} Select Load Step above to use it.
            </p>
          ))}
        {studyMode === "compare" && (
          <>
            {comparisonState.status === "loading" && (
              <p className="font-mono text-xs text-secondary">LOADING COMPARISON&hellip;</p>
            )}
            {comparisonState.status === "error" && (
              <div className="flex flex-wrap items-center gap-3">
                <p className="border border-status-critical bg-surface px-3 py-2 font-mono text-xs text-status-critical">
                  API ERROR: {comparisonState.message}
                </p>
                <button
                  type="button"
                  onClick={fetchComparison}
                  className="border border-hairline bg-surface-raised px-3 py-1.5 text-[12px] font-semibold text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
                >
                  Retry
                </button>
              </div>
            )}
            {comparisonState.status === "ready" && <ScenarioComparison entries={comparisonState.data.scenarios} />}
          </>
        )}
      </Stage>

      {/* Stage 4 */}
      <Stage id="stage-takeaway" n={4} title="Engineering takeaway" question="What can I conclude, and what can't I?">
        {readyData ? (
          <EngineeringTakeaway data={readyData} metrics={metrics} provenance={provenance} />
        ) : (
          <p className="text-[13px] text-secondary">The takeaway appears once a scenario has run.</p>
        )}
      </Stage>
    </main>
  );
}

function Stage({
  id,
  n,
  title,
  question,
  children,
}: {
  id: string;
  n: number;
  title: string;
  question: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="flex flex-col gap-3 border-t border-hairline pt-4">
      <div className="flex flex-col gap-0.5">
        <h2 id={`${id}-h`} data-stage-heading tabIndex={-1} className="text-heading text-primary focus:outline-none">
          <span className="mr-2 font-mono text-meta text-secondary">{n}</span>
          {title}
        </h2>
        <p className="text-[13px] text-secondary">{question}</p>
      </div>
      {children}
    </section>
  );
}

function StudyOption({
  id,
  label,
  selected,
  onSelect,
}: {
  id: "sweep" | "compare";
  label: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <label className="relative">
      <input
        type="radio"
        name="study"
        checked={selected}
        onChange={onSelect}
        data-testid={`study-option-${id}`}
        className="peer sr-only"
      />
      <span
        className={`block cursor-pointer border px-3 py-1.5 text-[12px] font-semibold peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary ${
          selected
            ? "border-hairline-strong bg-surface-raised text-primary"
            : "border-hairline bg-surface text-secondary hover:text-primary"
        }`}
      >
        {label}
      </span>
    </label>
  );
}

function Observe({
  data,
  index,
  onIndexChange,
  metrics,
  provenance,
  stale,
}: {
  data: ScenarioRunResponse;
  index: number;
  onIndexChange: (index: number) => void;
  metrics: ReturnType<typeof computeTransientMetrics>;
  provenance: string;
  stale: boolean;
}) {
  const isLoadStep = data.scenario === "load_step";

  // One index selected from the already-loaded run -- no new
  // simulation run, no new API request, no interpolation.
  const sample = sampleAt(data, index);
  const timeS = data.timeseries.time_s;
  const eventMarkers = data.events.map((e) => ({ time: e.time_s, label: e.label }));
  const event = data.events[0];

  // The initial (pre-step) P_load sample is always real engine
  // output, never a hardcoded "160" -- and since INITIAL_FRACTION is
  // fixed, dividing it back out gives the load's rated power without
  // the frontend ever hardcoding that config value either.
  const initialPLoadKw = data.timeseries.p_load_w[0] / 1e3;
  const finalPLoadKw = data.timeseries.p_load_w[data.timeseries.p_load_w.length - 1] / 1e3;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <p className="text-[13px] text-secondary" data-testid="run-provenance">
          {provenance}
        </p>
        {stale && (
          <p data-testid="run-stale" className="font-mono text-[11px] text-secondary">
            {STALE_RUN_MARKER}
          </p>
        )}
      </div>

      {isLoadStep && event && (
        <EventBanner initialKw={initialPLoadKw} finalKw={finalPLoadKw} stepTimeS={event.time_s} />
      )}

      <div className="flex flex-col gap-3" data-testid="state-at-time">
        <TimeScrubber timeS={timeS} index={index} onChange={onIndexChange} />
        <KpiStrip sample={sample} voltageReferenceV={data.thresholds.voltage_reference_v} />
        <PowerFlowSchematic
          live={{
            sample,
            ratedPowerW: data.thresholds.rated_power_w,
            voltageReferenceV: data.thresholds.voltage_reference_v,
            capacitanceF: data.thresholds.capacitance_f,
          }}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <h3 className="text-heading text-primary">Synchronized transient</h3>
        <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-1.5">
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
            <ChartHelp testId="chart-help-vdc">{VDC_CHART_CAPTION}</ChartHelp>
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
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
                      label: `shaded area ≈ ${formatEnergyDeficitKj(metrics)} kJ drawn from the DC bus (energy, not power)`,
                    }
                  : undefined
              }
            />
            <ChartHelp testId="chart-help-power">
              {POWER_BALANCE_CAPTION}
              {isLoadStep ? ` ${POWER_BALANCE_CAPTION_LOAD_STEP}` : ""}
            </ChartHelp>
          </div>
        </div>
      </div>

      {metrics && (
        <EngineeringInterpretation metrics={metrics} voltageReferenceV={data.thresholds.voltage_reference_v} />
      )}

      <div className="flex flex-col gap-2" data-testid="protection-group">
        <h3 className="text-heading text-primary">Protection</h3>
        <ProtectionTimeline timeline={data.protection_timeline} />
        <ProtectionCoordination timeline={data.protection_timeline} />
      </div>

      {metrics && (
        <TransientMetricsPanel metrics={metrics} voltageReferenceV={data.thresholds.voltage_reference_v} />
      )}
    </div>
  );
}

function ChartHelp({ children, testId }: { children: ReactNode; testId: string }) {
  return (
    <details data-testid={testId} className="text-[12px] text-secondary">
      <summary className="cursor-pointer font-mono text-meta uppercase hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
        How to read this chart
      </summary>
      <p className="mt-1 max-w-3xl leading-relaxed">{children}</p>
    </details>
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
        <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.04em] text-secondary">
          THE EVENT
        </span>
        <span className="font-mono text-[18px] font-semibold tabular-nums text-primary">
          {initialKw.toFixed(0)} <span className="text-secondary">&rarr;</span> {finalKw.toFixed(0)}{" "}
          <span className="text-[12px] font-normal text-secondary">kW</span>
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
