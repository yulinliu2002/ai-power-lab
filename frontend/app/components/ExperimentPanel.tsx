/**
 * Scenario A experiment controls -- the three variables Engineering
 * Study #1 found govern transient severity: the AI load step itself,
 * DC-link capacitance (energy buffering), and the SST response time
 * constant (power-response dynamics).
 *
 * This panel only ever edits local draft state (see `page.tsx`'s
 * `draftParams`). No slider here triggers a simulation request --
 * only RUN EXPERIMENT does, and the backend/`src/` engine is the only
 * place any of these numbers are turned into a trajectory.
 */
export interface ExperimentParams {
  finalFraction: number;
  capacitanceF: number;
  timeConstantS: number;
}

/**
 * Mirrors `backend/schemas.py: LoadStepRequest`'s own documented
 * defaults (which themselves come from `config/default.yaml`) --
 * kept here only so the draft sliders have a baseline position to
 * start from and reset to, not as a second source of engineering
 * truth.
 */
export const BASELINE_EXPERIMENT_PARAMS: ExperimentParams = {
  finalFraction: 0.8,
  capacitanceF: 0.02,
  timeConstantS: 0.02,
};

export const FINAL_FRACTION_RANGE = { min: 0.5, max: 1.0, step: 0.05 };
export const CAPACITANCE_RANGE = { min: 0.005, max: 0.08, step: 0.005 };
export const TIME_CONSTANT_RANGE = { min: 0.005, max: 0.08, step: 0.005 };

interface ExperimentPanelProps {
  draft: ExperimentParams;
  onDraftChange: (next: ExperimentParams) => void;
  onRun: () => void;
  onReset: () => void;
  isRunning: boolean;
  initialPLoadKw: number;
  loadRatedPowerW: number;
  error?: string | null;
}

export function ExperimentPanel({
  draft,
  onDraftChange,
  onRun,
  onReset,
  isRunning,
  initialPLoadKw,
  loadRatedPowerW,
  error,
}: ExperimentPanelProps) {
  const draftFinalKw = (draft.finalFraction * loadRatedPowerW) / 1e3;

  return (
    <section className="flex flex-col gap-1.5 border border-hairline bg-surface px-4 py-2">
      <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
        EXPERIMENT
      </span>
      <div className="flex flex-wrap items-end gap-4">
        <SliderControl
          label="AI load step (kW, final demand)"
          description="Final AI demand after the step, an illustrative test input. In this model, a larger step opens a larger initial gap between demand and SST output, because SST output follows demand with the response time set below."
          readout={`${initialPLoadKw.toFixed(0)} → ${draftFinalKw.toFixed(0)} kW`}
          value={draft.finalFraction}
          range={FINAL_FRACTION_RANGE}
          disabled={isRunning}
          onChange={(v) => onDraftChange({ ...draft, finalFraction: v })}
        />
        <SliderControl
          label="DC bus capacitance C_dc (F)"
          description="One lumped capacitance for the whole bus. From E = ½·C·V², the same energy drawn from the bus moves V_dc less when C is larger. This value is not a sized or measured bus."
          readout={`C = ${draft.capacitanceF.toFixed(3)} F`}
          value={draft.capacitanceF}
          range={CAPACITANCE_RANGE}
          disabled={isRunning}
          onChange={(v) => onDraftChange({ ...draft, capacitanceF: v })}
        />
        <SliderControl
          label="SST response time τ_sst (ms)"
          description="Time constant of a first-order lag on SST output power. It is a modeling assumption, not a measured or guaranteed hardware bandwidth. A longer τ_sst keeps the gap between demand and SST output open for longer."
          readout={`τ = ${(draft.timeConstantS * 1000).toFixed(0)} ms`}
          value={draft.timeConstantS}
          range={TIME_CONSTANT_RANGE}
          disabled={isRunning}
          onChange={(v) => onDraftChange({ ...draft, timeConstantS: v })}
        />

        <div className="ml-auto flex items-center gap-2 pb-0.5">
          <button
            type="button"
            onClick={onReset}
            disabled={isRunning}
            className="rounded border border-hairline bg-surface-raised px-3 py-1.5 font-sans text-[11px] font-semibold uppercase tracking-[0.04em] text-secondary disabled:cursor-not-allowed disabled:opacity-50"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={onRun}
            disabled={isRunning}
            className="rounded border border-accent bg-accent px-3 py-1.5 font-sans text-[12px] font-semibold text-canvas disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRunning ? "Running…" : "Run Experiment"}
          </button>
        </div>
      </div>
      {error && (
        <span className="font-sans text-[12px] text-status-critical">{error}</span>
      )}
    </section>
  );
}

function SliderControl({
  label,
  description,
  readout,
  value,
  range,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  readout: string;
  value: number;
  range: { min: number; max: number; step: number };
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <div className="flex min-w-[220px] flex-1 flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-sans text-[12px] font-semibold text-primary">{label}</span>
        <span className="font-mono text-[11px] tabular-nums text-secondary">{readout}</span>
      </div>
      <input
        type="range"
        min={range.min}
        max={range.max}
        step={range.step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1 w-full cursor-pointer appearance-none rounded-none bg-hairline accent-accent disabled:cursor-not-allowed"
        aria-label={label}
      />
      <p className="text-[12px] leading-snug text-secondary" data-testid="slider-description">{description}</p>
    </div>
  );
}
