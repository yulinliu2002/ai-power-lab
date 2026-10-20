import { ScrollRegion } from "./ScrollRegion";
import { SVG_COLOR } from "../lib/theme";

export interface SweepChartPoint {
  /** Swept-parameter value, already in display units (e.g. ms, not s). */
  x: number;
  /** Result value, already in display units (e.g. percent). */
  y: number;
  isGrid: boolean;
  isCurrent: boolean;
}

interface SweepChartProps {
  title: string;
  /** Shown once, under the x-axis ticks -- includes the parameter name
   * and its unit, so individual tick labels can stay unit-free and
   * short (e.g. "0.043" instead of "0.043 F" six times over). */
  xAxisLabel: string;
  /** Appended to every y tick (e.g. "12.0%") -- a parameter sweep has
   * no natural per-tick unit column the way a time series does, so the
   * unit travels with each number instead of sitting in a corner label. */
  yUnit: string;
  points: SweepChartPoint[];
  /** Formats one x tick's number only -- no unit suffix (see xAxisLabel). */
  xTickFormat: (x: number) => string;
}

const W = 600;
const H = 240;
const MARGIN = { top: 18, right: 26, bottom: 50, left: 44 };
/** Caps the chart's rendered CSS width so it never stretches to the
 * full width of a wide content column -- at the W:H aspect ratio
 * above, an uncapped stretch to ~1200px (this app's content width)
 * renders at ~480px tall; capping at 760px keeps it at ~300px,
 * matching DESIGN.md's compact-chart guidance, and keeps the 9.5-10px
 * viewBox font sizes close to their intended on-screen size instead
 * of being scaled up with the rest of the chart. */
const MAX_CSS_WIDTH_PX = 760;
/** Horizontal clearance the "CURRENT" label needs so it isn't clipped
 * against the plot's right edge -- see the per-point layout below.
 * The longer "GRID · CURRENT" label (current value coincides with a
 * grid point) needs more. */
const CURRENT_LABEL_CLEARANCE_PX = 56;
const GRID_CURRENT_LABEL_CLEARANCE_PX = 92;
const PLOT_W = W - MARGIN.left - MARGIN.right;
const PLOT_H = H - MARGIN.top - MARGIN.bottom;

/** Minimum pixel gap between adjacent x ticks before the label row
 * below them starts staggering to avoid overlapping text -- the swept
 * grid is evenly spaced, but the one extra CURRENT point can land
 * arbitrarily close to a grid point. */
const TICK_COLLISION_PX = 36;

/**
 * A dedicated XY chart for a parameter sweep: one point per simulated
 * run, x = the swept parameter (not time), y = that run's result.
 * Built as its own component rather than reusing `TelemetryChart`
 * because every one of that component's assumptions is wrong here --
 * there is no time axis, no continuous trace between samples (nothing
 * is known about what happens *between* two swept values, so no line
 * is ever drawn connecting them -- same honesty rule as DESIGN.md
 * §15: show the real data, never illustrate it), and no multi-series
 * legend.
 *
 * The y axis always starts at 0: every result this chart plots so far
 * (max |ΔV_dc| / V_ref) is a non-negative magnitude, and padding the
 * bottom with headroom would visually imply values can go negative.
 */
export function SweepChart({ title, xAxisLabel, yUnit, points, xTickFormat }: SweepChartProps) {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMax = Math.max(...ys) * 1.15 || 1;
  const yMin = 0;

  const scaleX = (x: number) =>
    xMax === xMin ? MARGIN.left + PLOT_W / 2 : MARGIN.left + ((x - xMin) / (xMax - xMin)) * PLOT_W;
  const scaleY = (y: number) => MARGIN.top + (1 - (y - yMin) / (yMax - yMin)) * PLOT_H;

  const yTicks = [yMin, yMin + (yMax - yMin) * 0.5, yMax];

  // Stagger x-tick labels that would otherwise collide, alternating a
  // second row beneath the first -- see TICK_COLLISION_PX. A reduce
  // over a fresh local accumulator, not a reassigned outer `let`, so
  // this stays a pure per-render computation.
  const ticks = points
    .slice()
    .sort((a, b) => a.x - b.x)
    .reduce<Array<{ point: SweepChartPoint; px: number; staggered: boolean }>>((acc, p) => {
      const px = scaleX(p.x);
      const prev = acc[acc.length - 1];
      const staggered = prev !== undefined && px - prev.px < TICK_COLLISION_PX ? !prev.staggered : false;
      acc.push({ point: p, px, staggered });
      return acc;
    }, []);

  const current = points.find((p) => p.isCurrent);

  return (
    <section className="flex flex-col gap-1.5 border border-hairline bg-surface px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-sans text-[13px] font-semibold text-primary">
          {title}
        </span>
        <div className="flex items-center gap-3 font-mono text-[10.5px] text-secondary">
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-[7px] w-[7px] rounded-full border-[1.5px]"
              style={{ borderColor: SVG_COLOR.accent }}
            />
            Grid point
          </span>
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-[8px] w-[8px] rounded-full"
              style={{ backgroundColor: SVG_COLOR.accent }}
            />
            Current value
          </span>
        </div>
      </div>

      <ScrollRegion label={`${title} chart`}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          style={{ minWidth: W, maxWidth: MAX_CSS_WIDTH_PX }}
        >
          {yTicks.map((v) => (
            <g key={v}>
              <line
                x1={MARGIN.left}
                x2={W - MARGIN.right}
                y1={scaleY(v)}
                y2={scaleY(v)}
                stroke={SVG_COLOR.hairline}
                strokeWidth={1}
              />
              <text
                x={MARGIN.left - 6}
                y={scaleY(v) + 3}
                textAnchor="end"
                fontFamily="var(--font-mono)"
                fontSize={9.5}
                fill={SVG_COLOR.textSecondary}
              >
                {`${v.toFixed(1)}${yUnit}`}
              </text>
            </g>
          ))}

          {/* Baseline (y = 0) drawn slightly heavier -- this is the
           * "no deviation at all" reference, not an arbitrary grid line. */}
          <line
            x1={MARGIN.left}
            x2={W - MARGIN.right}
            y1={scaleY(0)}
            y2={scaleY(0)}
            stroke={SVG_COLOR.textSecondary}
            strokeWidth={1}
          />

          {current && (
            <line
              x1={scaleX(current.x)}
              x2={scaleX(current.x)}
              y1={MARGIN.top}
              y2={scaleY(0)}
              stroke={SVG_COLOR.accent}
              strokeWidth={1}
              strokeDasharray="3 3"
              opacity={0.5}
            />
          )}

          {ticks.map(({ point, px, staggered }, i) => (
            <text
              key={i}
              x={px}
              y={H - MARGIN.bottom + 14 + (staggered ? 13 : 0)}
              textAnchor="middle"
              fontFamily="var(--font-mono)"
              fontSize={9.5}
              fontWeight={point.isCurrent ? 700 : 400}
              fill={point.isCurrent ? SVG_COLOR.accent : SVG_COLOR.textSecondary}
            >
              {xTickFormat(point.x)}
            </text>
          ))}

          <text
            x={MARGIN.left + PLOT_W / 2}
            y={H - 8}
            textAnchor="middle"
            fontFamily="var(--font-sans)"
            fontSize={10}
            fontWeight={600}
            letterSpacing="0.02em"
            fill={SVG_COLOR.textSecondary}
          >
            {xAxisLabel.toUpperCase()}
          </text>

          {points.map((p, i) => {
            if (!p.isCurrent) {
              return (
                <circle
                  key={i}
                  cx={scaleX(p.x)}
                  cy={scaleY(p.y)}
                  r={4}
                  fill={SVG_COLOR.surface}
                  stroke={SVG_COLOR.accent}
                  strokeWidth={1.5}
                />
              );
            }
            const cx = scaleX(p.x);
            const cy = scaleY(p.y);
            // Flip the label to the point's left/below when it would
            // otherwise clip against the plot's right/top edge -- the
            // CURRENT point can land anywhere along the swept range,
            // including right at either end.
            const label = p.isGrid ? "GRID · CURRENT" : "CURRENT";
            const clearance = p.isGrid ? GRID_CURRENT_LABEL_CLEARANCE_PX : CURRENT_LABEL_CLEARANCE_PX;
            const nearRight = cx > W - MARGIN.right - clearance;
            const nearTop = cy < MARGIN.top + 14;
            return (
              <g key={i}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={5.5}
                  fill={SVG_COLOR.accent}
                  stroke={SVG_COLOR.textPrimary}
                  strokeWidth={1.25}
                />
                <text
                  x={cx + (nearRight ? -8 : 8)}
                  y={nearTop ? cy + 16 : cy - 8}
                  textAnchor={nearRight ? "end" : "start"}
                  fontFamily="var(--font-mono)"
                  fontSize={9.5}
                  fontWeight={700}
                  fill={SVG_COLOR.textPrimary}
                >
                  {label}
                </text>
              </g>
            );
          })}
        </svg>
      </ScrollRegion>
    </section>
  );
}
