"use client";

import { CASES, CASE_ORDER } from "../lib/learnByExampleData";
import type { ScenarioName } from "../lib/simulationApi";

/**
 * Case selector for /learn: a native radio group (arrow keys, Tab and
 * Space/Enter come from the browser), in the Sandbox's fixed scenario order.
 * Presentation only; the existing `ScenarioSelector` was not reused because
 * it paints primary text on the accent fill (a contrast gap noted in
 * DESIGN.md §18) and offers no arrow-key navigation, and SPEC-012 R4 prefers
 * composition to editing a shared Sandbox component.
 */
export function CaseSelector({
  selected,
  onSelect,
}: {
  selected: ScenarioName;
  onSelect: (id: ScenarioName) => void;
}) {
  return (
    <fieldset className="flex flex-wrap gap-1.5">
      <legend className="sr-only">Case</legend>
      {CASE_ORDER.map((id) => {
        const isSelected = id === selected;
        return (
          <label key={id} className="relative">
            <input
              type="radio"
              name="learn-case"
              value={id}
              checked={isSelected}
              data-testid={`case-option-${id}`}
              onChange={() => onSelect(id)}
              className="peer sr-only"
            />
            <span
              className={`block cursor-pointer border px-2.5 py-1 font-sans text-[11px] font-semibold peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary ${
                isSelected
                  ? "border-primary bg-surface-raised text-primary"
                  : "border-hairline bg-surface text-secondary hover:text-primary"
              }`}
            >
              {CASES[id].title}
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}
