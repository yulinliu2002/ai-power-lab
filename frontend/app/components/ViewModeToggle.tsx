export type ViewMode = "single" | "compare";

/**
 * Two-way mode toggle, adjacent to `ScenarioSelector` (SPEC-010 §8/§12)
 * -- a real, keyboard-operable `role="radiogroup"`, same pattern as the
 * existing scenario selector. Selecting "Compare All" does not change
 * `activeScenario`; it only changes which section renders below.
 */
interface ViewModeToggleProps {
  mode: ViewMode;
  onSelect: (mode: ViewMode) => void;
  disabled?: boolean;
}

const MODE_OPTIONS: { key: ViewMode; label: string }[] = [
  { key: "single", label: "Single Scenario" },
  { key: "compare", label: "Compare All" },
];

export function ViewModeToggle({ mode, onSelect, disabled = false }: ViewModeToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label="View mode"
      data-testid="view-mode-toggle"
      className="flex flex-wrap gap-1.5"
    >
      {MODE_OPTIONS.map((option) => {
        const isSelected = option.key === mode;
        return (
          <button
            key={option.key}
            type="button"
            role="radio"
            aria-checked={isSelected}
            data-testid={`view-mode-option-${option.key}`}
            disabled={disabled}
            onClick={() => onSelect(option.key)}
            className={`rounded border px-2 py-1 font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] disabled:cursor-not-allowed disabled:opacity-50 ${
              isSelected
                ? "border-accent bg-accent text-primary"
                : "border-hairline bg-surface-raised text-secondary"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
