"use client";

import { useState } from "react";

import {
  APPLY_QUESTION,
  OBSERVED_TEXT,
  PHASE_TEXT,
  PREDICTION_OPTIONS,
  type ApplyOptionId,
  type CursorReadout,
  type Grounding,
  type ObservedOutcome,
  type PhaseId,
  type PredictionId,
} from "../lib/loadStepLesson";

/**
 * Interactive pieces of the Load Step lesson (SPEC-012 amendment A2).
 * Presentation and local state only: nothing here fetches, simulates or
 * stores anything beyond the learner's current selections.
 */

const BTN_PRIMARY =
  "bg-accent px-4 py-2 text-[13px] font-semibold text-canvas hover:opacity-90 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary";
const BTN_GHOST =
  "border border-hairline-strong px-4 py-2 text-[13px] font-semibold text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary";

function Choices<T extends string>({
  name,
  legend,
  options,
  value,
  onChange,
  disabled,
}: {
  name: string;
  legend: string;
  options: ReadonlyArray<{ id: T; label: string }>;
  value: T | null;
  onChange: (id: T) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset className="flex max-w-3xl flex-col gap-2" disabled={disabled}>
      <legend className="sr-only">{legend}</legend>
      {options.map((o) => (
        <label key={o.id} className="relative block">
          <input
            type="radio"
            name={name}
            value={o.id}
            checked={value === o.id}
            onChange={() => onChange(o.id)}
            data-testid={`${name}-${o.id}`}
            className="peer sr-only"
          />
          <span
            className={`block cursor-pointer border px-3 py-2.5 text-[13.5px] leading-snug peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary ${
              value === o.id
                ? "border-hairline-strong bg-surface-raised text-primary"
                : "border-hairline bg-surface text-secondary hover:text-primary"
            }`}
          >
            {o.label}
          </span>
        </label>
      ))}
    </fieldset>
  );
}

/** Predict: pick, then commit. Committing locks the pick; nothing is stored or scored. */
export function PredictPicker({
  choice,
  committed,
  onChoose,
  onCommit,
  onOpenDiscover,
}: {
  choice: PredictionId | null;
  committed: boolean;
  onChoose: (id: PredictionId) => void;
  onCommit: () => void;
  onOpenDiscover: () => void;
}) {
  return (
    <div className="flex flex-col gap-3" data-testid="predict-picker">
      <Choices
        name="prediction"
        legend="Your prediction for the DC bus voltage after the load step"
        options={PREDICTION_OPTIONS}
        value={choice}
        onChange={onChoose}
        disabled={committed}
      />
      {!committed ? (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" data-testid="commit-prediction" disabled={choice === null} onClick={onCommit} className={BTN_PRIMARY}>
            Commit prediction
          </button>
          <span className="text-[12px] text-secondary">The model result stays hidden until you commit.</span>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3" data-testid="prediction-committed">
          <span className="text-[13px] font-semibold text-primary">Prediction committed.</span>
          <button type="button" onClick={onOpenDiscover} className={BTN_PRIMARY}>
            Check it against the model &rarr;
          </button>
        </div>
      )}
    </div>
  );
}

/** Discover gate: shown until the learner commits a prediction or chooses to look without one. */
export function DiscoverGate({ onGoPredict, onSkip }: { onGoPredict: () => void; onSkip: () => void }) {
  return (
    <div data-testid="discover-gate" className="flex max-w-3xl flex-col gap-3 border border-hairline bg-surface px-4 py-4">
      <p className="text-[14px] leading-relaxed text-primary">
        Make a prediction first. The result is more useful when you have committed to an answer you can check.
      </p>
      <div className="flex flex-wrap gap-3">
        <button type="button" onClick={onGoPredict} className={BTN_PRIMARY}>
          Go to Predict
        </button>
        <button type="button" data-testid="look-without-predicting" onClick={onSkip} className={BTN_GHOST}>
          Look without predicting
        </button>
      </div>
    </div>
  );
}

/** Your prediction vs what the live run did. */
export function PredictionComparison({
  choice,
  observed,
}: {
  choice: PredictionId;
  observed: ObservedOutcome;
}) {
  const picked = PREDICTION_OPTIONS.find((o) => o.id === choice)!;
  const match = choice === observed;
  return (
    <div data-testid="prediction-comparison" className="flex max-w-3xl flex-col gap-1.5 border border-hairline bg-surface px-4 py-3">
      <p className="font-mono text-meta uppercase text-secondary">Your prediction vs the model</p>
      <p className="text-[13.5px] text-primary">
        <span className="font-semibold">You predicted: </span>
        {picked.label}
      </p>
      <p className="text-[13.5px] text-primary" data-testid="prediction-observed">
        <span className="font-semibold">Model run: </span>
        {OBSERVED_TEXT[observed]}
      </p>
      <p className="text-[13px] leading-relaxed text-secondary" data-testid="prediction-verdict">
        <span className="font-semibold text-primary">{match ? "Match. " : "Not a match. "}</span>
        {picked.reasoning}
      </p>
    </div>
  );
}

/** Time cursor controls for the synchronized charts: slider, jump buttons, live readout and phase note. */
export function CursorPanel({
  index,
  last,
  onIndex,
  readout,
  phase,
  jumps,
}: {
  index: number;
  last: number;
  onIndex: (i: number) => void;
  readout: CursorReadout;
  phase: PhaseId;
  jumps: ReadonlyArray<{ label: string; index: number }>;
}) {
  const p = PHASE_TEXT[phase];
  return (
    <section aria-label="Time cursor" data-testid="cursor-panel" className="flex flex-col gap-2 border border-hairline bg-surface px-3 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono text-meta uppercase text-secondary">Time cursor</span>
        <input
          type="range"
          aria-label="Time cursor, both charts"
          data-testid="cursor-slider"
          min={0}
          max={last}
          step={1}
          onKeyDown={(e) => {
            // Arrow keys move about 1/300 of the run so the cursor visibly travels; Shift+Arrow moves one sample.
            if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && !e.shiftKey) {
              e.preventDefault();
              const d = Math.max(1, Math.floor(last / 300)) * (e.key === "ArrowRight" ? 1 : -1);
              onIndex(Math.min(last, Math.max(0, index + d)));
            }
          }}
          value={index}
          onChange={(e) => onIndex(Number(e.target.value))}
          className="h-1 min-w-[160px] flex-1 cursor-pointer appearance-none rounded-none bg-hairline accent-accent"
        />
        <span className="font-mono text-[12px] tabular-nums text-primary" data-testid="cursor-time">
          t = {readout.timeS.toFixed(3)} s
        </span>
      </div>
      <p className="text-[12px] text-secondary">Arrow keys move the cursor in coarse steps; Shift+Arrow moves one sample. Both charts follow it.</p>
      <div className="flex flex-wrap gap-2">
        {jumps.map((j) => (
          <button key={j.label} type="button" data-testid={`jump-${j.label}`} onClick={() => onIndex(j.index)} className="border border-hairline px-2.5 py-1 text-[12px] font-semibold text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
            Jump to {j.label}
          </button>
        ))}
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-[12px] tabular-nums text-secondary sm:grid-cols-4" data-testid="cursor-readout">
        <div><dt className="text-meta uppercase">V_dc</dt><dd className="text-primary">{readout.vdcV.toFixed(1)} V</dd></div>
        <div><dt className="text-meta uppercase">P_load</dt><dd className="text-primary">{readout.pLoadKw.toFixed(1)} kW</dd></div>
        <div><dt className="text-meta uppercase">P_sst</dt><dd className="text-primary">{readout.pSstKw.toFixed(1)} kW</dd></div>
        <div><dt className="text-meta uppercase">P_sst − P_load</dt><dd className="text-primary">{readout.mismatchKw.toFixed(1)} kW</dd></div>
      </dl>
      <p className="max-w-3xl text-[13px] leading-relaxed text-secondary" data-testid="cursor-phase" aria-live="polite">
        <span className="font-semibold text-primary">{p.title}. </span>
        {p.body}
      </p>
    </section>
  );
}

/** Explain: measured counterparts of the cause chain, from the same live run. */
export function GroundingPanel({ g }: { g: Grounding }) {
  const rows: ReadonlyArray<[string, string]> = [
    ["1. Demand steps; delivery lags", `Demand goes from ${g.demandBeforeKw.toFixed(1)} kW to ${g.demandAfterKw.toFixed(1)} kW; the largest shortfall of delivery below demand is ${g.peakShortfallKw.toFixed(1)} kW at t = ${g.peakShortfallTimeS.toFixed(3)} s.`],
    ["2. The bus pays the difference", `It gives up ${g.energyGivenUpKj.toFixed(2)} kJ (E = ½ C V²) and the voltage reaches ${g.minVdcV.toFixed(1)} V.`],
    ["3. The controller raises the target", `While below reference, the power target peaks ${g.peakTargetAboveDemandKw.toFixed(1)} kW above demand at t = ${g.peakTargetAboveDemandTimeS.toFixed(3)} s.`],
    ["4. The surplus refills the bus", g.recoveryElapsedS === null ? "The voltage does not return to the recovery band before the run ends." : `The voltage is back inside the recovery band ${g.recoveryElapsedS.toFixed(3)} s after the step and stays there.`],
  ];
  return (
    <section aria-label="Cause chain measured in this run" data-testid="grounding-panel" className="flex max-w-3xl flex-col gap-2 border border-hairline bg-surface px-4 py-3">
      <h5 className="font-mono text-meta uppercase text-secondary">The same chain, measured in this run (model output)</h5>
      <dl className="flex flex-col gap-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex flex-col gap-0.5">
            <dt className="text-[13px] font-semibold text-primary">{k}</dt>
            <dd className="text-[13px] leading-relaxed text-secondary">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Apply: an engineering-judgment question. Local selection only; no scoring and no stored state. */
export function ApplyQuestionPanel() {
  const [choice, setChoice] = useState<ApplyOptionId | null>(null);
  const [checked, setChecked] = useState(false);
  const picked = APPLY_QUESTION.options.find((o) => o.id === choice);
  return (
    <div data-testid="apply-question" className="flex flex-col gap-3">
      <p className="max-w-3xl text-[14px] leading-relaxed text-primary" data-testid="apply-prompt">{APPLY_QUESTION.prompt}</p>
      <Choices
        name="apply"
        legend="How you would respond"
        options={APPLY_QUESTION.options}
        value={choice}
        onChange={(id) => {
          setChoice(id);
          setChecked(false);
        }}
      />
      <div>
        <button type="button" data-testid="check-reasoning" disabled={choice === null} onClick={() => setChecked(true)} className={BTN_PRIMARY}>
          Check my reasoning
        </button>
      </div>
      {checked && picked && (
        <p role="status" data-testid="apply-feedback" className="max-w-3xl border border-hairline bg-surface px-4 py-3 text-[13px] leading-relaxed text-secondary">
          <span className="font-semibold text-primary">{picked.defensible ? "Defensible. " : "Not defensible. "}</span>
          {picked.feedback}
        </p>
      )}
    </div>
  );
}
