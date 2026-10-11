import { useId } from "react";

import type { Sample } from "../lib/simulationApi";
import { gridStatus, sstStatus } from "../lib/statusRoles";
import { SVG_COLOR } from "../lib/theme";

interface PowerFlowSchematicProps {
  sample: Sample;
  ratedPowerW: number;
  voltageReferenceV: number;
  /** `thresholds.capacitance_f` from the fetched run -- the only input
   * the bus energy readout needs beyond `sample.v_dc_v`. */
  capacitanceF: number;
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

// --- Topology geometry -------------------------------------------------
// Pixso Concept 03 (frames 01/02): GRID -> SST -> 800 VDC BUS -> AI COMPUTE
// drawn as a sparse line topology (circle / diamond / hatched bus segment /
// circle), not bordered cards. Constants below reproduce that composition's
// proportions at a scale that fits this panel's width.
const PAD_X = 20;
const ICON_CY = 46;
const GRID_R = 18;
const SST_HALF = 24;
const LOAD_R = 16;
const BUS_W = 240;
const BUS_H = 38;
const GAP_GRID_SST = 60;
const GAP_SST_BUS = 50;
const GAP_BUS_LOAD = 46;

const GRID_CX = PAD_X + GRID_R;
const GRID_RIGHT_X = GRID_CX + GRID_R;
const SST_LEFT_X = GRID_RIGHT_X + GAP_GRID_SST;
const SST_CX = SST_LEFT_X + SST_HALF;
const SST_RIGHT_X = SST_CX + SST_HALF;
const BUS_X1 = SST_RIGHT_X + GAP_SST_BUS;
const BUS_X2 = BUS_X1 + BUS_W;
const LOAD_LEFT_X = BUS_X2 + GAP_BUS_LOAD;
const LOAD_CX = LOAD_LEFT_X + LOAD_R;

const BUS_Y = ICON_CY - BUS_H / 2;
const BUS_Y2 = BUS_Y + BUS_H;

const TITLE_Y = 12;
const CAPTION_Y = ICON_CY + SST_HALF + 16;

const BUS_CAPTION_Y = BUS_Y2 + 15;
const V_ROW_Y = BUS_CAPTION_Y + 17;
const E_ROW_Y = V_ROW_Y + 18;

const VIEW_W = LOAD_CX + LOAD_R + PAD_X;
const VIEW_H = Math.max(E_ROW_Y + 10, CAPTION_Y + 18);

const TRACK_X1 = BUS_X1 + 18;
const TRACK_X2 = BUS_X2 - 86;

/**
 * Describes the instantaneous power mismatch -- pure arithmetic on two
 * already-returned samples, not a new modeled quantity. Below ~0.5% of
 * rated power is "balanced" (solid connector, no annotation), matching
 * Concept 03 frame 01; a real mismatch draws the dashed connector and
 * inequality annotation of frame 02.
 */
function mismatchLabel(deficitW: number, ratedPowerW: number): string | null {
  const threshold = Math.max(ratedPowerW, 1) * 0.005;
  if (Math.abs(deficitW) < threshold) return null;
  return deficitW > 0 ? "P_load > P_sst" : "P_load < P_sst";
}

/**
 * The Simulator's power-flow diagram, translating Pixso Concept 03's
 * topology/state language: a sparse line topology (not bordered cards),
 * the P2 bus-segment hatch texture as the DC bus's topology-integrated
 * energy cue, and the P4 twin V/E potential-axis readout underneath it.
 *
 * Cyan is the nominal/structural color throughout; amber marks only the
 * two things Concept 03 marks amber -- the E (stored-energy) channel
 * itself, and a real P_load > P_sst deficit (plus, reusing that same
 * stress amber, a sagged grid or a DERATED SST). The one addition beyond
 * Concept 03's three frames (which never depict a fault) is a critical
 * (red) stroke on the GRID or SST glyph when that stage is actually
 * faulted (grid lost, or SST `TRIPPED`) -- without it this component
 * would have no way left to show a real protection event, since the
 * per-stage status borders it previously carried are gone.
 *
 * E_dc is computed here as E_dc = 1/2 * C_dc * V_dc^2 from the engine's
 * own `capacitance_f` and `v_dc_v` -- the same closed-form relation
 * `EngineeringInterpretation.tsx` already states in prose. This is
 * algebra on two values the engine already returned, not a re-simulation
 * of any dynamics (no trajectory, trip logic, or control behavior is
 * computed here).
 */
export function PowerFlowSchematic({
  sample,
  ratedPowerW,
  voltageReferenceV,
  capacitanceF,
}: PowerFlowSchematicProps) {
  const clipId = useId();

  const grid = gridStatus(sample.grid_voltage_pu, sample.grid_available);
  const sst = sstStatus(sample.operating_state);
  const deficitW = sample.p_load_w - sample.p_sst_w;
  const label = mismatchLabel(deficitW, ratedPowerW);
  const hasDeficit = label === "P_load > P_sst";

  const vFrac = clamp01(sample.v_dc_v / voltageReferenceV);
  const eRefJ = 0.5 * capacitanceF * voltageReferenceV ** 2;
  const eDcJ = 0.5 * capacitanceF * sample.v_dc_v ** 2;
  const eFrac = clamp01(eRefJ > 0 ? eDcJ / eRefJ : 0);

  const gridColor =
    grid.role === "critical"
      ? SVG_COLOR.critical
      : grid.role === "warning"
        ? SVG_COLOR.schematicAmber
        : SVG_COLOR.schematicCyan;
  const sstColor =
    sst.role === "critical"
      ? SVG_COLOR.critical
      : sst.role === "warning"
        ? SVG_COLOR.schematicAmber
        : SVG_COLOR.schematicCyan;
  const busLineColor = hasDeficit ? SVG_COLOR.schematicAmber : SVG_COLOR.schematicCyan;

  return (
    <section className="flex flex-col gap-1.5 border border-hairline bg-surface px-4 py-2">
      <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
        POWER FLOW
      </span>
      <div className="mx-auto w-full" style={{ maxWidth: VIEW_W }}>
        <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} width="100%">
          <text
            x={(BUS_X1 + BUS_X2) / 2}
            y={TITLE_Y}
            textAnchor="middle"
            fontFamily="var(--font-sans)"
            fontSize={12.5}
            fontWeight={500}
            fill={SVG_COLOR.textPrimary}
          >
            800 VDC DISTRIBUTION
          </text>

          <Connector
            x1={GRID_RIGHT_X}
            x2={SST_LEFT_X}
            y={ICON_CY}
            color={gridColor}
            dashed={grid.role === "critical"}
          />
          <Connector x1={SST_RIGHT_X} x2={BUS_X1} y={ICON_CY} color={busLineColor} dashed={hasDeficit} />
          <Connector x1={BUS_X2} x2={LOAD_LEFT_X} y={ICON_CY} color={busLineColor} />

          {label && (
            <text
              x={(SST_RIGHT_X + BUS_X1) / 2}
              y={ICON_CY - 10}
              textAnchor="middle"
              fontFamily="var(--font-sans)"
              fontSize={11}
              fontWeight={500}
              fill={busLineColor}
            >
              {label}
            </text>
          )}

          <GridGlyph cx={GRID_CX} cy={ICON_CY} r={GRID_R} color={gridColor} />
          <text
            x={GRID_CX}
            y={CAPTION_Y}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize={10}
            fontWeight={500}
            letterSpacing="0.06em"
            fill={SVG_COLOR.textSecondary}
          >
            UTILITY GRID
          </text>

          <SstGlyph cx={SST_CX} cy={ICON_CY} half={SST_HALF} color={sstColor} />
          <text
            x={SST_CX}
            y={CAPTION_Y}
            textAnchor="middle"
            fontFamily="var(--font-sans)"
            fontSize={12.5}
            fontWeight={500}
            fill={SVG_COLOR.textPrimary}
          >
            SST
          </text>
          <text
            x={SST_CX}
            y={CAPTION_Y + 13}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize={8.5}
            letterSpacing="0.04em"
            fill={SVG_COLOR.muted}
          >
            SOLID-STATE TRANSFORMER
          </text>

          <BusSegment
            clipId={clipId}
            x={BUS_X1}
            y={BUS_Y}
            w={BUS_W}
            h={BUS_H}
            hatchColor={busLineColor}
          />
          <text
            x={(BUS_X1 + BUS_X2) / 2}
            y={BUS_CAPTION_Y}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize={9.5}
            fill={SVG_COLOR.muted}
          >
            {`Vdc reference — ${voltageReferenceV.toFixed(1)} V`}
          </text>

          <PotentialAxis
            label="V"
            x1={TRACK_X1}
            x2={TRACK_X2}
            y={V_ROW_Y}
            frac={vFrac}
            color={SVG_COLOR.schematicCyan}
            readout={`Vdc  ${sample.v_dc_v.toFixed(1)} V`}
          />
          <PotentialAxis
            label="E"
            x1={TRACK_X1}
            x2={TRACK_X2}
            y={E_ROW_Y}
            frac={eFrac}
            color={SVG_COLOR.schematicAmber}
            readout={`Edc  ${(eDcJ / 1e3).toFixed(2)} kJ`}
          />

          <LoadGlyph cx={LOAD_CX} cy={ICON_CY} r={LOAD_R} color={SVG_COLOR.schematicCyan} />
          <text
            x={LOAD_CX}
            y={CAPTION_Y}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize={10}
            fontWeight={500}
            letterSpacing="0.06em"
            fill={SVG_COLOR.textSecondary}
          >
            AI COMPUTE
          </text>
          <text
            x={LOAD_CX}
            y={CAPTION_Y + 16}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize={13}
            fontWeight={500}
            fill={SVG_COLOR.textPrimary}
          >
            {`${(sample.p_load_w / 1e3).toFixed(0)} kW`}
          </text>
        </svg>
      </div>
    </section>
  );
}

/** A structural line between two stages, with a small static direction
 * chevron -- Concept 03's connectors are plain hairlines, not an
 * animated power-magnitude encoding. */
function Connector({
  x1,
  x2,
  y,
  color,
  dashed = false,
}: {
  x1: number;
  x2: number;
  y: number;
  color: string;
  dashed?: boolean;
}) {
  if (x2 <= x1) return null;
  const midX = (x1 + x2) / 2;
  return (
    <g>
      <line
        x1={x1}
        y1={y}
        x2={x2}
        y2={y}
        stroke={color}
        strokeWidth={1.5}
        strokeDasharray={dashed ? "4 4" : undefined}
      />
      <polygon points={`${midX - 4},${y - 3.5} ${midX - 4},${y + 3.5} ${midX + 4},${y}`} fill={color} />
    </g>
  );
}

function GridGlyph({ cx, cy, r, color }: { cx: number; cy: number; r: number; color: string }) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={1.5} />
      <path
        d={`M ${cx - r * 0.5} ${cy} Q ${cx - r * 0.2} ${cy - r * 0.45} ${cx} ${cy} Q ${cx + r * 0.2} ${cy + r * 0.45} ${cx + r * 0.5} ${cy}`}
        fill="none"
        stroke={color}
        strokeWidth={1.3}
      />
    </g>
  );
}

/** Diamond with a diagonal slash -- Concept 03's solid-state switch glyph
 * for the SST stage. */
function SstGlyph({ cx, cy, half, color }: { cx: number; cy: number; half: number; color: string }) {
  const points = `${cx},${cy - half} ${cx + half},${cy} ${cx},${cy + half} ${cx - half},${cy}`;
  return (
    <g>
      <polygon points={points} fill="none" stroke={color} strokeWidth={1.5} />
      <line
        x1={cx - half * 0.4}
        y1={cy + half * 0.4}
        x2={cx + half * 0.4}
        y2={cy - half * 0.4}
        stroke={color}
        strokeWidth={1.3}
      />
    </g>
  );
}

function LoadGlyph({ cx, cy, r, color }: { cx: number; cy: number; r: number; color: string }) {
  const arm = r * 0.5;
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={1.5} />
      <line x1={cx - arm} y1={cy} x2={cx + arm} y2={cy} stroke={color} strokeWidth={1.3} />
      <line x1={cx} y1={cy - arm} x2={cx} y2={cy + arm} stroke={color} strokeWidth={1.3} />
    </g>
  );
}

/**
 * The P2 bus-segment texture: a bounded rectangle with a faint constant
 * cyan fill and evenly spaced diagonal hatch lines whose color is the
 * only thing that changes with state (cyan nominal, amber while
 * P_load > P_sst) -- matching Concept 03 frames 01/02 exactly. Line
 * count/geometry are an educational-assumption approximation of the
 * Pixso vector hatch (exact path data isn't exposed via the MCP read),
 * not a literal export.
 */
function BusSegment({
  clipId,
  x,
  y,
  w,
  h,
  hatchColor,
}: {
  clipId: string;
  x: number;
  y: number;
  w: number;
  h: number;
  hatchColor: string;
}) {
  const inset = 3;
  const innerX1 = x + inset;
  const innerX2 = x + w - inset;
  const innerY1 = y + inset;
  const innerY2 = y + h - inset;
  const rise = innerY2 - innerY1;
  const spacing = 16;
  const lines: number[] = [];
  for (let lx = innerX1 - rise; lx < innerX2; lx += spacing) {
    lines.push(lx);
  }

  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={3} fill="none" stroke={SVG_COLOR.schematicCyan} strokeWidth={1.5} />
      <rect x={innerX1} y={innerY1} width={innerX2 - innerX1} height={rise} fill={SVG_COLOR.schematicCyan} opacity={0.05} />
      <clipPath id={clipId}>
        <rect x={innerX1} y={innerY1} width={innerX2 - innerX1} height={rise} />
      </clipPath>
      <g clipPath={`url(#${clipId})`}>
        {lines.map((lx) => (
          <line
            key={lx}
            x1={lx}
            y1={innerY2}
            x2={lx + rise}
            y2={innerY1}
            stroke={hatchColor}
            strokeWidth={1.1}
            opacity={0.8}
          />
        ))}
      </g>
    </g>
  );
}

/**
 * One row of the P4 Twin Potential Axes: a hairline track spanning the
 * bus width, a fixed end-tick marking the reference (V_ref or the
 * V_ref-derived E_ref, always the track's right end since frac <= 1),
 * a colored indicator tick at the real value's fraction of that
 * reference, and a mono readout. V and E each keep one fixed channel
 * color (cyan / amber) regardless of state -- only the indicator's
 * position moves.
 */
function PotentialAxis({
  label,
  x1,
  x2,
  y,
  frac,
  color,
  readout,
}: {
  label: string;
  x1: number;
  x2: number;
  y: number;
  frac: number;
  color: string;
  readout: string;
}) {
  const indicatorX = x1 + frac * (x2 - x1);
  return (
    <g>
      <text
        x={x1 - 10}
        y={y + 3.5}
        textAnchor="end"
        fontFamily="var(--font-mono)"
        fontSize={10}
        fontWeight={500}
        fill={SVG_COLOR.textSecondary}
      >
        {label}
      </text>
      <line x1={x1} y1={y} x2={x2} y2={y} stroke={SVG_COLOR.hairline} strokeWidth={1} />
      <line x1={x2} y1={y - 6} x2={x2} y2={y + 6} stroke={SVG_COLOR.muted} strokeWidth={1} opacity={0.5} />
      <line x1={indicatorX} y1={y - 9} x2={indicatorX} y2={y + 9} stroke={color} strokeWidth={3} />
      <text
        x={x2 + 10}
        y={y + 4}
        fontFamily="var(--font-mono)"
        fontSize={11.5}
        fontWeight={500}
        fill={color}
      >
        {readout}
      </text>
    </g>
  );
}
