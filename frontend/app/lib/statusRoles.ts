/**
 * Status-role classifiers for the KPI tiles and the power-flow
 * schematic.
 *
 * These mirror `dashboard/components/schematic.py`'s `grid_status`,
 * `bus_status`, and `sst_status` exactly (same thresholds, same
 * operating-state map, same status labels) so the KPI strip and the
 * schematic -- both reading these same three functions -- can never
 * disagree about the same entity's health. See DESIGN.md section 4.
 * This is presentation-layer classification of values the engine
 * already produced; it does not compute any new engineering quantity.
 */

export type StatusRole = "good" | "warning" | "critical" | "neutral";

export interface StatusResult {
  role: StatusRole;
  label: string;
}

const OPERATING_STATE_STATUS: Record<string, StatusRole> = {
  RUNNING: "good",
  DERATED: "warning",
  TRIPPED: "critical",
};

export function gridStatus(voltagePu: number, available: boolean): StatusResult {
  if (!available) return { role: "critical", label: "LOST" };
  if (voltagePu < 0.95) return { role: "warning", label: "SAGGED" };
  return { role: "good", label: "NOMINAL" };
}

export function busStatus(vDcV: number, vRefV: number): StatusResult {
  const deviation = Math.abs(vDcV - vRefV) / vRefV;
  if (deviation <= 0.05) return { role: "good", label: "IN REGULATION" };
  if (deviation <= 0.15) return { role: "warning", label: "DROOPING" };
  return { role: "critical", label: "OUT OF REGULATION" };
}

export function sstStatus(operatingState: string): StatusResult {
  return {
    role: OPERATING_STATE_STATUS[operatingState] ?? "warning",
    label: operatingState,
  };
}
