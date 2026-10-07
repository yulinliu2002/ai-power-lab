/**
 * Status-role classifiers for the KPI tiles.
 *
 * These mirror `dashboard/components/schematic.py`'s `grid_status`,
 * `bus_status`, and `sst_status` exactly (same thresholds, same
 * operating-state map) so the React KPI strip and the Streamlit
 * schematic can never disagree about the same entity's health -- see
 * DESIGN.md section 4. This is presentation-layer classification of
 * values the engine already produced; it does not compute any new
 * engineering quantity.
 */

export type StatusRole = "good" | "warning" | "critical" | "neutral";

const OPERATING_STATE_STATUS: Record<string, StatusRole> = {
  RUNNING: "good",
  DERATED: "warning",
  TRIPPED: "critical",
};

export function gridStatus(voltagePu: number, available: boolean): StatusRole {
  if (!available) return "critical";
  if (voltagePu < 0.95) return "warning";
  return "good";
}

export function busStatus(vDcV: number, vRefV: number): StatusRole {
  const deviation = Math.abs(vDcV - vRefV) / vRefV;
  if (deviation <= 0.05) return "good";
  if (deviation <= 0.15) return "warning";
  return "critical";
}

export function sstStatus(operatingState: string): StatusRole {
  return OPERATING_STATE_STATUS[operatingState] ?? "warning";
}
