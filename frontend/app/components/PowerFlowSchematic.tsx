import type { Sample } from "../lib/simulationApi";
import { busStatus, gridStatus, sstStatus } from "../lib/statusRoles";
import { SVG_COLOR, STATUS_SVG_COLOR } from "../lib/theme";

interface PowerFlowSchematicProps {
  sample: Sample;
  ratedPowerW: number;
  voltageReferenceV: number;
}

const BOX_W = 190;
const BOX_H = 118;
const Y = 20;
const XS = [20, 280, 540, 800];
const VIEW_W = XS[3] + BOX_W + 20;
const VIEW_H = Y + BOX_H + 20;

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

/**
 * The Simulator's hero visualization -- a one-line power-flow diagram:
 * MV GRID -> SST -> 800 VDC BUS -> AI COMPUTE LOAD.
 *
 * Ported from `dashboard/components/schematic.py`'s behavior, not its
 * markup: stage border color is that stage's real status, flow-line
 * width/animation speed is the real power magnitude normalized to
 * rated power, and the AI load is always `neutral` -- it is an
 * exogenous demand, never a protected/controlled entity. Every value
 * shown is read directly from the selected `Sample`.
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
    <section className="flex flex-col gap-2 border border-hairline bg-surface px-4 py-3">
      <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
        POWER FLOW
      </span>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          width="100%"
          style={{ minWidth: 720 }}
        >
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
            lines={[`${sample.grid_voltage_pu.toFixed(2)} p.u.`]}
          />
          <StageBox
            x={XS[1]}
            title="SST"
            color={STATUS_SVG_COLOR[sst.role]}
            statusLabel={sst.label}
            lines={[
              `P ${(sample.p_sst_w / 1e3).toFixed(1)} kW`,
              `T ${sample.temperature_c.toFixed(1)} °C · derate ${(sample.derate_factor * 100).toFixed(0)}%`,
            ]}
          />
          <StageBox
            x={XS[2]}
            title="800 VDC BUS"
            color={STATUS_SVG_COLOR[bus.role]}
            statusLabel={bus.label}
            lines={[
              `${sample.v_dc_v.toFixed(1)} V`,
              `ref ${voltageReferenceV.toFixed(0)} V`,
            ]}
          />
          <StageBox
            x={XS[3]}
            title="AI COMPUTE LOAD"
            color={SVG_COLOR.accent}
            statusLabel="DEMAND"
            lines={[`P ${(sample.p_load_w / 1e3).toFixed(1)} kW`]}
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
  lines,
}: {
  x: number;
  title: string;
  color: string;
  statusLabel: string;
  lines: string[];
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
        y={Y + 24}
        textAnchor="middle"
        fontSize={12.5}
        fontWeight={600}
        letterSpacing="0.03em"
        fill={SVG_COLOR.textSecondary}
      >
        {title}
      </text>
      <circle cx={x + 16} cy={Y + 42} r={4.5} fill={color} />
      <text x={x + 26} y={Y + 46} fontSize={11} fontWeight={600} fill={color}>
        {statusLabel}
      </text>
      {lines.map((line, i) => (
        <text
          key={line}
          x={x + BOX_W / 2}
          y={Y + 70 + i * 20}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize={14}
          fill={SVG_COLOR.textPrimary}
        >
          {line}
        </text>
      ))}
    </g>
  );
}
