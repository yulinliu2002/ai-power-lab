import type { ScenarioName } from "../lib/simulationApi";

/**
 * Five named, fixed-preset scenario options (SPEC-008 §12) -- a real
 * `role="radiogroup"` of individually-focusable `<button>`s, never a
 * slider and never a `div onClick`-only control. Each option is
 * independently reachable via Tab and activated with Enter/Space
 * (native `<button>` behavior), satisfying AC-008/AC-023's
 * keyboard-operability requirement without any custom key handling.
 */
export const SCENARIO_OPTIONS: { key: ScenarioName; label: string }[] = [
  { key: "load_step", label: "Load Step" },
  { key: "sustained_high_load", label: "Sustained High Load" },
  { key: "thermal_trip", label: "Thermal Trip" },
  { key: "grid_sag", label: "Grid Sag" },
  { key: "grid_loss", label: "Grid Loss" },
];

interface ScenarioSelectorProps {
  selected: ScenarioName;
  onSelect: (scenario: ScenarioName) => void;
  disabled?: boolean;
}

export function ScenarioSelector({ selected, onSelect, disabled = false }: ScenarioSelectorProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Scenario"
      data-testid="scenario-select"
      className="flex flex-wrap gap-1.5"
    >
      {SCENARIO_OPTIONS.map((option) => {
        const isSelected = option.key === selected;
        return (
          <button
            key={option.key}
            type="button"
            role="radio"
            aria-checked={isSelected}
            data-testid={`scenario-option-${option.key}`}
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
