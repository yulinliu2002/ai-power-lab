"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  BOUNDARIES,
  DISCLOSURES,
  DRIVERS,
  EVIDENCE_LABEL_TEXT,
  REFERENCES,
  SOURCE_KIND_TEXT,
  type ReferenceId,
} from "../lib/architectureChoicesData";
import { CASES, LEARN_DISCLOSURES, type Case } from "../lib/learnByExampleData";
import {
  API_BASE_URL,
  fetchScenario,
  fetchScenarioComparison,
  type ScenarioComparisonEntry,
  type ScenarioName,
  type ScenarioRunResponse,
  type LoadStepResponse,
} from "../lib/simulationApi";
import {
  groundingFor,
  indexAtOrAfter,
  observedOutcome,
  phaseAt,
  readoutAt,
  type PredictionId,
} from "../lib/loadStepLesson";
import { SVG_COLOR } from "../lib/theme";
import { computeTransientMetrics, formatEnergyDeficitKj } from "../lib/transientMetrics";
import { CaseSelector } from "./CaseSelector";
import { EngineeringInterpretation } from "./EngineeringInterpretation";
import { EvidenceTag } from "./EvidenceTag";
import { LEARN_STEPS, LearnStepper, type LearnStepId } from "./LearnStepper";
import {
  ApplyQuestionPanel,
  CursorPanel,
  DiscoverGate,
  GroundingPanel,
  PredictPicker,
  PredictionComparison,
} from "./LoadStepLesson";
import { ProtectionCoordination } from "./ProtectionCoordination";
import { ProtectionTimeline } from "./ProtectionTimeline";
import { TelemetryChart } from "./TelemetryChart";
import { TransientMetricsPanel } from "./TransientMetricsPanel";

/**
 * Learn by Example (SPEC-012). Five guided cases over the five existing
 * Sandbox scenarios. Authored prose is static and number-free (it sits in
 * `data-static-prose` nodes, scanned by the verification script); every model
 * value comes from the two live requests below. No new endpoint, no parameter
 * override, no computation beyond the existing `computeTransientMetrics`.
 *
 * Request A (per-scenario run) and request B (comparison) have independent
 * loading/error states (R13); each case view is keyed by the selected case
 * and cancels its in-flight request on unmount, so a slow earlier response
 * cannot overwrite the selected case.
 *
 * Four-step shell (SPEC-012 amendment A1): the eight parts are grouped as
 * Predict = 1-2, Discover = 3 + 6a, Explain = 4-5, Apply = 6b, 7, 8. Only the
 * current step's parts are mounted, but both requests live in `CaseView`, so
 * switching steps never refetches and every step is reachable at any time.
 */

type Remote<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

// Composition-level contrast fix (SPEC-012 R4/R14): reused Sandbox components
// paint essential detail text in `text-muted`; inside this wrapper that class
// resolves to `text-secondary` without editing any shared component.
const CONTRAST_WRAP = "flex flex-col gap-3 [&_.text-muted]:text-secondary";

export function LearnByExample() {
  const [selected, setSelected] = useState<ScenarioName>("load_step");
  const [comparison, setComparison] = useState<Remote<ScenarioComparisonEntry[]>>({
    status: "loading",
  });

  useEffect(() => {
    let live = true;
    fetchScenarioComparison()
      .then((r) => live && setComparison({ status: "ready", data: r.scenarios }))
      .catch((e: unknown) => {
        if (live)
          setComparison({ status: "error", message: e instanceof Error ? e.message : "request failed" });
      });
    return () => {
      live = false;
    };
  }, []);

  const citedRefs = useMemo(() => {
    const ids = new Set<ReferenceId>();
    for (const k of Object.values(CASES)) {
      for (const it of k.notModeled) it.refs?.forEach((r) => ids.add(r));
    }
    return [...ids];
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <CaseSelector selected={selected} onSelect={setSelected} />

      {/* Keyed by case: switching unmounts the previous case, whose effect
          cleanup cancels its in-flight request, so a slow earlier response can
          never overwrite the selected case (SPEC-012 R13, rapid switching). */}
      <CaseView key={selected} selected={selected} comparison={comparison} />

      <section id="references" className="flex flex-col gap-2 border-t border-hairline pt-4">
        <h2 className="font-sans text-[13px] font-semibold uppercase tracking-[0.04em] text-secondary">
          References
        </h2>
        <p className="max-w-3xl text-[11.5px] leading-relaxed text-secondary">
          Each reference states what was actually inspected. Consortium documents are attributed, not
          endorsed.
        </p>
        <ul className="flex flex-col gap-1.5">
          {citedRefs.map((id) => {
            const r = REFERENCES[id];
            return (
              <li key={id} className="text-[12px] leading-relaxed text-secondary">
                <span className="font-mono text-[11px] text-primary">{r.id}</span>{" "}
                <span className="font-mono text-[10.5px] uppercase tracking-[0.04em]">
                  [{SOURCE_KIND_TEXT[r.kind]}]
                </span>{" "}
                &mdash;{" "}
                {r.url ? (
                  <a
                    href={r.url}
                    rel="noreferrer"
                    className="underline underline-offset-2 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
                  >
                    {r.citation}
                  </a>
                ) : (
                  r.citation
                )}
                <span className="block text-[11px]">Inspection: {r.inspection}</span>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

function CaseView({
  selected,
  comparison,
}: {
  selected: ScenarioName;
  comparison: Remote<ScenarioComparisonEntry[]>;
}) {
  const [run, setRun] = useState<Remote<ScenarioRunResponse>>({ status: "loading" });

  useEffect(() => {
    let live = true;
    fetchScenario(selected)
      .then((data) => live && setRun({ status: "ready", data }))
      .catch((e: unknown) => {
        if (live) setRun({ status: "error", message: e instanceof Error ? e.message : "request failed" });
      });
    return () => {
      live = false;
    };
  }, [selected]);

  const c = CASES[selected];
  const entry =
    comparison.status === "ready"
      ? (comparison.data.find((e) => e.scenario === selected) ?? null)
      : null;

  const [step, setStep] = useState<LearnStepId>("predict");
  // Load Step lesson only (SPEC-012 A2): the learner's pick, whether it is committed, and an explicit opt-out.
  const isLesson = selected === "load_step";
  const [pick, setPick] = useState<PredictionId | null>(null);
  const [committed, setCommitted] = useState(false);
  const [skipped, setSkipped] = useState(false);
  const lessonMetrics = useMemo(
    () => (isLesson && run.status === "ready" ? computeTransientMetrics(run.data as LoadStepResponse) : null),
    [isLesson, run],
  );
  const stepHeading = useRef<HTMLHeadingElement>(null);
  const userMoved = useRef(false);
  useEffect(() => {
    // Keyboard and screen-reader users land on the new step's heading; the first render is left alone.
    // Focus is allowed to scroll: Back/Next sit below long content, and the heading must come into view.
    if (userMoved.current) stepHeading.current?.focus();
  }, [step, skipped]);
  const go = (id: LearnStepId) => {
    userMoved.current = true;
    // Re-activating the current step changes no state, so the effect would not run: focus its heading directly.
    if (id === step) stepHeading.current?.focus();
    else setStep(id);
  };
  const stepIndex = LEARN_STEPS.findIndex((s) => s.id === step);
  const prev = LEARN_STEPS[stepIndex - 1];
  const next = LEARN_STEPS[stepIndex + 1];

  return (
    <article data-testid={`case-${selected}`} className="flex flex-col gap-5">
      <header className="flex flex-col gap-1.5">
        <h2 className="text-heading text-primary">{c.title}</h2>
        <p className="font-mono text-meta uppercase text-secondary">
          Informs{" "}
          {c.drivers
            .map((d) => `${d.toUpperCase()} ${DRIVERS.find((x) => x.id === d)?.title ?? ""}`)
            .join(" · ")}
        </p>
      </header>

      <LearnStepper current={step} onSelect={go} />

      <div data-testid={`step-${step}`} className="flex flex-col gap-6">
        <h3
          ref={stepHeading}
          tabIndex={-1}
          className="font-mono text-meta uppercase text-secondary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
        >
          Step {stepIndex + 1} of {LEARN_STEPS.length} &middot; {LEARN_STEPS[stepIndex].label}
        </h3>

        {step === "predict" && (
          <>
            <Section title="Situation" testId="part-situation">
              <StaticProse>
                <Para text={c.situation.text} />
                <EvidenceTag evidence={c.situation.evidence} basis={c.situation.basis} refs={c.situation.refs} />
              </StaticProse>
            </Section>

            <Section title="Predict" testId="part-predict">
              <StaticProse>
                <p className="max-w-3xl text-[14px] leading-relaxed text-primary">{c.predict.question}</p>
                {isLesson ? (
                  committed && (
                    <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary" data-testid="predict-reveal">
                      {c.predict.reveal}
                    </p>
                  )
                ) : (
                  <details className="max-w-3xl">
                    <summary className="cursor-pointer font-sans text-[12px] font-semibold uppercase tracking-[0.04em] text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
                      Show the expected outcome
                    </summary>
                    <p className="pt-1.5 text-[12.5px] leading-relaxed text-secondary">{c.predict.reveal}</p>
                  </details>
                )}
                <EvidenceTag evidence={c.predict.evidence} basis={c.predict.basis} refs={c.predict.refs} />
              </StaticProse>
              {isLesson && (
                <PredictPicker
                  choice={pick}
                  committed={committed}
                  onChoose={setPick}
                  onCommit={() => setCommitted(true)}
                  onOpenDiscover={() => go("discover")}
                />
              )}
            </Section>
          </>
        )}

        {step === "discover" && isLesson && !committed && !skipped && (
          <DiscoverGate onGoPredict={() => go("predict")} onSkip={() => {
            userMoved.current = true;
            setSkipped(true);
          }} />
        )}

        {step === "discover" && !(isLesson && !committed && !skipped) && (
          <>
            <Section title="Observe (live model output)" testId="part-observe">
              <ObserveBlock c={c} run={run} entry={entry} comparison={comparison} comparisonPrediction={committed ? pick : null} />
            </Section>

            <Section title="Modeled outcome" testId="part-modeled">
              <div
                data-testid="panel-modeled"
                className="flex flex-col gap-2 border border-hairline bg-surface px-3 py-3"
              >
                <p className="font-sans text-[12px] font-semibold uppercase tracking-[0.04em] text-secondary">
                  Modeled outcome (simplified model, not a prediction for real equipment)
                </p>
                <ModeledOutcome run={run} entry={entry} comparison={comparison} />
                {c.busCollapseCase && (
                  <p className="text-[12px] leading-relaxed text-secondary" data-testid="d-l2">
                    {LEARN_DISCLOSURES.d2}
                  </p>
                )}
              </div>
            </Section>
          </>
        )}

        {step === "explain" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
            <Section title="Explain" testId="part-explain">
              <StaticProse>
                <ol className="flex max-w-3xl list-decimal flex-col gap-3 pl-5 text-[13.5px] leading-relaxed text-secondary">
                  {c.explain.steps.map((s, i) => (
                    <li key={i} className="pl-1">
                      <span>{s.text}</span>
                      {s.equation && (
                        <code data-equation className="mt-1 block font-mono text-[12px] text-primary">
                          {s.equation}
                        </code>
                      )}
                    </li>
                  ))}
                </ol>
                <p className="max-w-3xl text-[13.5px] leading-relaxed text-primary">
                  <span className="font-semibold">Limiting quantity: </span>
                  {c.explain.limitingQuantity}
                </p>
                <EvidenceTag evidence={c.explain.evidence} basis={c.explain.basis} refs={c.explain.refs} />
              </StaticProse>
              {isLesson && run.status === "ready" && lessonMetrics && (
                <GroundingPanel g={groundingFor(run.data as LoadStepResponse, lessonMetrics)} />
              )}
              {isLesson && run.status === "error" && (
                <RemoteMessage what="The measured cause chain" message={run.message} />
              )}
            </Section>

            <Section title="Limits of this model" testId="part-limits">
              <StaticProse>
                <ul className="flex max-w-3xl flex-col gap-2">
                  {c.limits.map((l, i) => (
                    <li key={i} className="flex flex-col gap-1">
                      <Para text={l.text} />
                      <EvidenceTag evidence={l.evidence} basis={l.basis} refs={l.refs} />
                    </li>
                  ))}
                </ul>
              </StaticProse>
              <div className={CONTRAST_WRAP} data-testid="part-coverage">
                <LiveCoverage run={run} />
              </div>
            </Section>
          </div>
        )}

        {step === "apply" && (
          <>
            {isLesson && (
              <Section title="Apply: engineering judgment" testId="part-apply-question">
                <ApplyQuestionPanel />
              </Section>
            )}
            <Section title="Real-world behavior this engine does not represent" testId="part-not-modeled">
              <div
                data-testid="panel-not-modeled"
                className="flex flex-col gap-2 border border-dashed border-secondary bg-surface-raised px-3 py-3"
              >
                <StaticProse>
                  <ul className="flex flex-col gap-3">
                    {c.notModeled.map((n) => (
                      <li key={n.name} className="flex flex-col gap-1">
                        <span className="text-[12px] font-semibold text-primary">{n.name}</span>
                        <Para text={n.text} />
                        <EvidenceTag evidence={n.evidence} basis={n.basis} refs={n.refs} />
                      </li>
                    ))}
                  </ul>
                </StaticProse>
              </div>
            </Section>

            <Section title="Decision link" testId="part-decision">
              <StaticProse>
                <Para text={c.decision.text} />
                <p className="font-mono text-meta uppercase text-secondary">
                  {c.decision.drivers.map((d) => d.toUpperCase()).join(" · ")} &middot;{" "}
                  {BOUNDARIES.find((b) => b.id === c.decision.boundary)?.title} boundary
                </p>
                <EvidenceTag evidence={c.decision.evidence} basis={c.decision.basis} refs={c.decision.refs} />
              </StaticProse>
              <Link
                href="/architecture"
                className="self-start border border-hairline px-3 py-1.5 font-mono text-[12px] font-semibold uppercase tracking-[0.04em] text-secondary hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
              >
                Open Architecture Choices &rarr;
              </Link>
            </Section>

            <Section title="Validation reasoning" testId="part-validation">
              <StaticProse>
                <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">
                  What would have to be shown before relying on this behavior for a real design.
                </p>
                <ul className="flex max-w-3xl flex-col gap-2">
                  {c.validation.map((v) => (
                    <li key={v.verifies} className="flex flex-col gap-0.5 text-[13px] leading-relaxed text-secondary">
                      <span>{v.verifies}</span>
                      <span className="font-mono text-meta uppercase text-secondary">
                        Evidence: {v.kinds.join(" + ")}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="font-mono text-meta text-secondary">
                  {EVIDENCE_LABEL_TEXT.assumption} &mdash; an illustrative list, not a complete plan for any facility.
                </p>
              </StaticProse>
            </Section>
          </>
        )}

        <div className="flex flex-wrap items-center gap-3 border-t border-hairline pt-4">
          {prev && (
            <button
              type="button"
              data-testid="step-prev"
              onClick={() => go(prev.id)}
              className="border border-hairline-strong px-4 py-2 text-[13px] font-semibold text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
            >
              &larr; Back: {prev.label}
            </button>
          )}
          {next && (
            <button
              type="button"
              data-testid="step-next"
              onClick={() => go(next.id)}
              className="bg-accent px-4 py-2 text-[13px] font-semibold text-canvas hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
            >
              Next: {next.label} &rarr;
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

function Section({
  title,
  testId,
  children,
}: {
  title: string;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <section data-testid={testId} className="flex flex-col gap-2 border-t border-hairline pt-4">
      <h4 className="font-sans text-[13px] font-semibold uppercase tracking-[0.04em] text-secondary">
        {title}
      </h4>
      {children}
    </section>
  );
}

/** Authored static prose: scanned by the SPEC-012 AC-4 script (no digits). */
function StaticProse({ children }: { children: React.ReactNode }) {
  return (
    <div data-static-prose className="flex flex-col gap-2">
      {children}
    </div>
  );
}

function Para({ text }: { text: string }) {
  return <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">{text}</p>;
}

function RemoteMessage({ what, message }: { what: string; message: string }) {
  return (
    <p
      role="status"
      data-testid="remote-error"
      className="max-w-3xl border border-hairline bg-surface px-3 py-2 text-[12px] leading-relaxed text-secondary"
    >
      {what} is unavailable: the simulation backend ({API_BASE_URL}) could not be reached or returned an
      error ({message}). Start the backend to see model output; the explanations on this page do not
      depend on it.
    </p>
  );
}

function Loading({ what }: { what: string }) {
  return (
    <p role="status" className="text-[12px] text-secondary">
      Loading {what}&hellip;
    </p>
  );
}

function ObserveBlock({
  c,
  run,
  entry,
  comparison,
  comparisonPrediction,
}: {
  c: Case;
  run: Remote<ScenarioRunResponse>;
  entry: ScenarioComparisonEntry | null;
  comparison: Remote<ScenarioComparisonEntry[]>;
  /** Load Step lesson: the committed prediction to compare with the run, else null. */
  comparisonPrediction: PredictionId | null;
}) {
  return (
    <div className={CONTRAST_WRAP} data-testid="observe-live">
      <p className="max-w-3xl text-[11.5px] leading-relaxed text-secondary">
        {DISCLOSURES.sim}
      </p>
      {run.status === "loading" && <Loading what="the model run" />}
      {run.status === "error" && <RemoteMessage what="The model run" message={run.message} />}
      {run.status === "ready" && <RunView c={c} data={run.data} prediction={comparisonPrediction} />}

      <div data-testid="stress-block" className="flex flex-col gap-1 border border-hairline bg-surface px-3 py-2">
        <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
          Dominant stress (model)
        </span>
        {comparison.status === "loading" && <Loading what="the stress profile" />}
        {comparison.status === "error" && (
          <RemoteMessage what="The stress profile" message={comparison.message} />
        )}
        {entry && (
          <>
            <span className="text-[12px] font-bold text-primary">{entry.stress_profile.dominant_stress_label}</span>
            <p className="text-[11.5px] leading-snug text-secondary">{entry.stress_profile.dominant_stress_detail}</p>
          </>
        )}
      </div>
    </div>
  );
}

function RunView({ c, data, prediction }: { c: Case; data: ScenarioRunResponse; prediction: PredictionId | null }) {
  const isLoadStep = data.scenario === "load_step";
  const metrics = useMemo(
    () => (isLoadStep ? computeTransientMetrics(data as LoadStepResponse) : null),
    [data, isLoadStep],
  );
  const timeS = data.timeseries.time_s;
  const vRef = data.thresholds.voltage_reference_v;
  // Load Step lesson (SPEC-012 A2): one time cursor shared by both charts. It only selects an already-returned sample.
  const [cursor, setCursor] = useState<number | null>(null);
  const eventIndex = metrics ? indexAtOrAfter(timeS, metrics.eventTimeS) : 0;
  const cursorIndex = cursor ?? eventIndex;
  const cursorTimeS = metrics ? timeS[cursorIndex] : undefined;
  const eventMarkers = [
    ...data.events.map((e) => ({ time: e.time_s, label: e.label })),
    ...(metrics && metrics.recoveryTimeS !== null ? [{ time: metrics.recoveryTimeS, label: "settled" }] : []),
  ];

  return (
    <div className="flex flex-col gap-3">
      {/* The interpretation's prose points at the Power Balance chart "below",
          so it sits above the charts (SPEC-012 R5). */}
      {metrics && prediction && <PredictionComparison choice={prediction} observed={observedOutcome(metrics, vRef)} />}
      {metrics && <EngineeringInterpretation metrics={metrics} voltageReferenceV={vRef} />}
      {metrics && (
        <CursorPanel
          index={cursorIndex}
          last={timeS.length - 1}
          onIndex={setCursor}
          readout={readoutAt(data as LoadStepResponse, cursorIndex)}
          phase={phaseAt(data as LoadStepResponse, metrics, cursorIndex)}
          jumps={[
            { label: "step", index: eventIndex },
            { label: "minimum", index: indexAtOrAfter(timeS, metrics.minVdcTimeS) },
            ...(metrics.recoveryTimeS !== null ? [{ label: "settled", index: indexAtOrAfter(timeS, metrics.recoveryTimeS) }] : []),
          ]}
        />
      )}
      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        <TelemetryChart
          title="DC Bus Voltage — V_dc(t)"
          timeS={timeS}
          series={[{ label: "V_dc", values: data.timeseries.v_dc_v, color: SVG_COLOR.accent }]}
          yUnit="V"
          currentTimeS={cursorTimeS}
          referenceLines={[{ value: vRef, label: `V_ref = ${vRef.toFixed(0)} V` }]}
          eventMarkers={eventMarkers}
          markerPoint={
            metrics
              ? { time: metrics.minVdcTimeS, value: metrics.minVdcV, label: `min ${metrics.minVdcV.toFixed(0)} V` }
              : undefined
          }
        />
        <TelemetryChart
          title="Power Balance — P_load vs P_sst"
          timeS={timeS}
          series={[
            { label: "P_sst", values: data.timeseries.p_sst_w.map((w) => w / 1e3), color: SVG_COLOR.accent },
            { label: "P_load", values: data.timeseries.p_load_w.map((w) => w / 1e3), color: SVG_COLOR.neutral, dashed: true },
          ]}
          yUnit="kW"
          currentTimeS={cursorTimeS}
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
      </div>
      <ProtectionTimeline timeline={data.protection_timeline} />
      {metrics && <TransientMetricsPanel metrics={metrics} voltageReferenceV={vRef} />}
      {c.busCollapseCase && (
        <p className="max-w-3xl text-[11.5px] leading-relaxed text-secondary">{LEARN_DISCLOSURES.d2}</p>
      )}
    </div>
  );
}

function LiveCoverage({ run }: { run: Remote<ScenarioRunResponse> }) {
  if (run.status === "loading") return <Loading what="protection coordination and coverage" />;
  if (run.status === "error")
    return (
      <p role="status" data-testid="coverage-unavailable" className="text-[12px] text-secondary">
        Coverage unavailable: the simulation backend is required (it is not reachable right now).
      </p>
    );
  return <ProtectionCoordination timeline={run.data.protection_timeline} />;
}

function ModeledOutcome({
  run,
  entry,
  comparison,
}: {
  run: Remote<ScenarioRunResponse>;
  entry: ScenarioComparisonEntry | null;
  comparison: Remote<ScenarioComparisonEntry[]>;
}) {
  return (
    <div className={CONTRAST_WRAP} data-testid="modeled-live">
      {run.status === "loading" && <Loading what="the model outcome" />}
      {run.status === "error" && <RemoteMessage what="The modeled outcome" message={run.message} />}
      {run.status === "ready" && (
        <div className="flex flex-col gap-1">
          <span className="text-[12px] font-bold text-primary">{run.data.protection_timeline.outcome_label}</span>
          <p className="text-[11.5px] leading-snug text-secondary">{run.data.protection_timeline.outcome_detail}</p>
          <p className="font-mono text-[10.5px] text-secondary">RECOVERY: {run.data.protection_timeline.recovery_label}</p>
        </div>
      )}
      {entry && (
        <p className="font-mono text-[10.5px] text-secondary">
          States reached: {entry.stress_profile.protection_states_reached.join(", ")}
        </p>
      )}
      {comparison.status === "error" && run.status === "ready" && (
        <p className="text-[11.5px] text-secondary">States reached are unavailable without the comparison request.</p>
      )}
    </div>
  );
}
