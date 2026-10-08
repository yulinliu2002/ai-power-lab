import type { Sample } from "../lib/simulationApi";
import { busStatus, gridStatus, sstStatus } from "../lib/statusRoles";
import { SVG_COLOR, STATUS_SVG_COLOR } from "../lib/theme";

interface PowerFlowSchematicProps {
  sample: Sample;
  ratedPowerW: number;
  voltageReferenceV: number;
}

const BOX_W = 150;
const BOX_H = 68;
const GAP = 40;
const Y = 10;
const BOTTOM_MARGIN = 10;
const XS = [16, 16 + BOX_W + GAP, 16 + 2 * (BOX_W + GAP), 16 + 3 * (BOX_W + GAP)];
const VIEW_W = XS[3] + BOX_W + 16;
const VIEW_H = Y + BOX_H + BOTTOM_MARGIN;

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

/**
 * The Simulator's power-flow diagram -- a compact one-line schematic:
 * MV GRID -> SST -> 800 VDC BUS -> AI COMPUTE LOAD.
 *
 * Ported from `dashboard/components/schematic.py`'s behavior, not its
 * markup: stage border color is that stage's real status, flow-line
 * width/animation speed is the real power magnitude normalized to
 * rated power, and the AI load is always `neutral` -- it is an
 * exogenous demand, never a protected/controlled entity. Every value
 * shown is read directly from the selected `Sample`.
 *
 * The SVG is rendered at its own intrinsic size (capped at `VIEW_W`
 * px, centered) rather than stretched to fill the panel -- this is a
 * topology diagram with four fixed-size nodes, not a chart that
 * should grow to fill available width.
 */
export function PowerFlowSchematic({
  sample,
  ratedPowerW,
  voltageReferenceV,
}: PowerFlowSchematicProps) {
  const grid = gridStatus(sample.grid_voltage_pu, sample.grid_available);
  const sst = sstStatus(sample.operating_state);
  const bus = busStatus(sample.v_dc_v, voltageReferenceV);

  const rated = Math.max(ratedPowerW, 1);
  const sstFrac = clamp01(sample.p_sst_w / rated);
  const loadFrac = clamp01(sample.p_load_w / rated);

  const midY = Y + BOX_H / 2;

  return (
    <section className="flex flex-col gap-1.5 border border-hairline bg-surface px-4 py-2">
      <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
        POWER FLOW
      </span>
      <div className="mx-auto w-full" style={{ maxWidth: VIEW_W }}>
        <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} width="100%">
          <FlowSegment
            x1={XS[0] + BOX_W}
            x2={XS[1]}
            y={midY}
            frac={sstFrac}
            dim={!sample.grid_available}
          />
          <FlowSegment x1={XS[1] + BOX_W} x2={XS[2]} y={midY} frac={sstFrac} />
          <FlowSegment x1={XS[2] + BOX_W} x2={XS[3]} y={midY} frac={loadFrac} />

          <StageBox
            x={XS[0]}
            title="MV GRID"
            color={STATUS_SVG_COLOR[grid.role]}
            statusLabel={grid.label}
            primaryLine={`${sample.grid_voltage_pu.toFixed(2)} p.u.`}
          />
          <StageBox
            x={XS[1]}
            title="SST"
            color={STATUS_SVG_COLOR[sst.role]}
            statusLabel={sst.label}
            primaryLine={`P ${(sample.p_sst_w / 1e3).toFixed(1)} kW`}
            secondaryLine={`${sample.temperature_c.toFixed(1)}°C · ${(sample.derate_factor * 100).toFixed(0)}% derate`}
          />
          <StageBox
            x={XS[2]}
            title="800 VDC BUS"
            color={STATUS_SVG_COLOR[bus.role]}
            statusLabel={bus.label}
            primaryLine={`${sample.v_dc_v.toFixed(1)} V`}
            secondaryLine={`ref ${voltageReferenceV.toFixed(0)} V`}
          />
          <StageBox
            x={XS[3]}
            title="AI COMPUTE LOAD"
            color={SVG_COLOR.accent}
            statusLabel="DEMAND"
            primaryLine={`P ${(sample.p_load_w / 1e3).toFixed(1)} kW`}
          />
        </svg>
      </div>
    </section>
  );
}

function FlowSegment({
  x1,
  x2,
  y,
  frac,
  dim = false,
}: {
  x1: number;
  x2: number;
  y: number;
  frac: number;
  dim?: boolean;
}) {
  const inactive = dim || frac < 0.01;
  const stroke = inactive ? SVG_COLOR.hairline : SVG_COLOR.accent;
  const width = inactive ? 1.5 : 2 + 5 * clamp01(frac);
  const duration = Math.max(0.25, 1.4 - 1.1 * clamp01(frac));

  return (
    <line
      x1={x1}
      y1={y}
      x2={x2}
      y2={y}
      stroke={stroke}
      strokeWidth={width}
      strokeDasharray="6 6"
      strokeLinecap="round"
      className={inactive ? undefined : "flow-line"}
      style={inactive ? undefined : { animationDuration: `${duration.toFixed(2)}s` }}
    />
  );
}

function StageBox({
  x,
  title,
  color,
  statusLabel,
  primaryLine,
  secondaryLine,
}: {
  x: number;
  title: string;
  color: string;
  statusLabel: string;
  primaryLine: string;
  secondaryLine?: string;
}) {
  return (
    <g>
      <rect
        x={x}
        y={Y}
        width={BOX_W}
        height={BOX_H}
        rx={4}
        fill={SVG_COLOR.surfaceRaised}
        stroke={color}
        strokeWidth={2}
      />
      <text
        x={x + BOX_W / 2}
        y={Y + 13}
        textAnchor="middle"
        fontSize={10.5}
        fontWeight={600}
        letterSpacing="0.02em"
        fill={SVG_COLOR.textSecondary}
      >
        {title}
      </text>
      <circle cx={x + 14} cy={Y + 25} r={3.5} fill={color} />
      <text x={x + 22} y={Y + 28} fontSize={9.5} fontWeight={600} fill={color}>
        {statusLabel}
      </text>
      <text
        x={x + BOX_W / 2}
        y={Y + 47}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontSize={14}
        fill={SVG_COLOR.textPrimary}
      >
        {primaryLine}
      </text>
      {secondaryLine && (
        <text
          x={x + BOX_W / 2}
          y={Y + 60}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize={9.5}
          fill={SVG_COLOR.textSecondary}
        >
          {secondaryLine}
        </text>
      )}
    </g>
  );
}
