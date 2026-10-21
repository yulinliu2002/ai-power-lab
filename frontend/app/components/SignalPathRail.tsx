import { ARCHITECTURES, type ArchitectureId, type CategoryId } from "../lib/infrastructureMapData";
import { ARCHITECTURE_CHOICE_NAMES } from "../lib/architectureChoicesData";

/**
 * Signal-path rail (DESIGN.md section 12, SPEC-014 F5). Draws the
 * *selected architecture's own* main power path from the System Map data
 * (ids and labels unchanged), never one universal chain. An SST node
 * exists only in the Conceptual MV-to-800 VDC via SST architecture.
 *
 * When `simulatedSlice` is set (the Sandbox), the rail is meant to be
 * pinned to that architecture; the stages the model simulates carry a
 * dashed border and a visible legend names the stages that are not
 * modeled. The list gives the node sequence to assistive technology;
 * below `sm` the labels collapse to a dot track (labels stay readable by
 * screen readers).
 */
const SIMULATED_CATEGORIES: readonly CategoryId[] = ["power_conversion", "distribution", "compute"];

export function SignalPathRail({
  architecture,
  simulatedSlice = false,
  note,
}: {
  architecture: ArchitectureId;
  simulatedSlice?: boolean;
  note?: string;
}) {
  const arch = ARCHITECTURES.find((a) => a.id === architecture)!;
  const main = arch.nodes.filter((n) => n.lane === "main");
  const name = ARCHITECTURE_CHOICE_NAMES[architecture];
  const accessibleName = `Power path for ${name}: ${main.map((n) => n.label).join(", then ")}.${
    simulatedSlice
      ? " Dashed stages are the simulated slice; rack DC-DC conversion is not modeled. This is not evidence about other architectures."
      : " One representative architecture, not a universal path."
  }`;

  return (
    <div
      role="group"
      aria-label={accessibleName}
      data-testid="signal-path-rail"
      className="flex flex-col gap-1.5 border border-hairline bg-surface-inset px-3 py-2"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <span className="text-[12px] font-semibold text-primary">{name}</span>
        {note && <span className="text-[12px] text-secondary">{note}</span>}
      </div>
      <ol className="flex items-center">
        {main.map((n, i) => {
          const dashed = simulatedSlice && SIMULATED_CATEGORIES.includes(n.categoryId);
          return (
            <li key={n.id} className="flex min-w-0 flex-1 items-center last:flex-none" data-node={n.id}>
              <span
                className={`flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-[12px] text-secondary ${
                  dashed ? "border-dashed border-hairline-strong" : "border-transparent"
                }`}
              >
                <i
                  aria-hidden="true"
                  className="inline-block h-[7px] w-[7px] shrink-0 rounded-full border-[1.5px] border-accent bg-surface-inset"
                />
                <span className="max-sm:sr-only whitespace-nowrap">{n.label}</span>
              </span>
              {i < main.length - 1 && <span aria-hidden="true" className="mx-1 h-px min-w-2 flex-1 bg-accent opacity-45" />}
            </li>
          );
        })}
      </ol>
      {simulatedSlice && (
        <p className="text-[12px] leading-snug text-secondary" data-testid="rail-legend">
          Dashed stages are simulated (the SST, the 800 VDC distribution bus and a lumped AI load).
          Stages the model does not represent, such as rack DC-DC conversion between the bus and the
          servers, are not modeled.
        </p>
      )}
    </div>
  );
}
