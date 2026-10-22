"use client";

/**
 * Four-step control for /learn (SPEC-012 amendment A1). Presentation only:
 * it names the step, reports which one is current, and calls `onSelect`.
 * Every step is reachable at any time (no gating, no saved state); the
 * mapping of case parts to steps lives in `LearnByExample`.
 */
export const LEARN_STEPS = [
  { id: "predict", label: "Predict", hint: "Commit to an answer" },
  { id: "discover", label: "Discover", hint: "Check the model" },
  { id: "explain", label: "Explain", hint: "Trace the cause" },
  { id: "apply", label: "Apply", hint: "What to validate" },
] as const;

export type LearnStepId = (typeof LEARN_STEPS)[number]["id"];

export function LearnStepper({
  current,
  onSelect,
}: {
  current: LearnStepId;
  onSelect: (id: LearnStepId) => void;
}) {
  return (
    <nav aria-label="Learn steps" data-testid="learn-stepper">
      <ol className="grid grid-cols-2 border border-hairline-strong bg-surface sm:grid-cols-4">
        {LEARN_STEPS.map((s, i) => {
          const on = s.id === current;
          return (
            <li key={s.id} className="min-w-0 border-hairline [&:nth-child(n+3)]:border-t sm:[&:nth-child(n+3)]:border-t-0 sm:[&:nth-child(n+2)]:border-l [&:nth-child(even)]:border-l">
              <button
                type="button"
                aria-current={on ? "step" : undefined}
                data-testid={`step-tab-${s.id}`}
                onClick={() => onSelect(s.id)}
                className={`flex w-full items-center gap-3 px-4 py-3 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-secondary ${
                  on ? "bg-surface-raised text-primary" : "text-secondary hover:text-primary"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border font-mono text-meta ${
                    on ? "border-primary bg-primary text-canvas" : "border-hairline-strong"
                  }`}
                >
                  {i + 1}
                </span>
                <span className="flex min-w-0 flex-col">
                  <span className="text-[14px] font-semibold leading-tight">{s.label}</span>
                  <span className="text-[12px] leading-tight">{s.hint}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
