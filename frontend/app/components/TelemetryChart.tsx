import { SVG_COLOR } from "../lib/theme";

export interface ChartSeries {
  label: string;
  values: number[];
  color: string;
  dashed?: boolean;
}

export interface ReferenceLine {
  value: number;
  label: string;
}

export interface EventMarker {
  time: number;
  label: string;
}

interface TelemetryChartProps {
  title: string;
  timeS: number[];
  series: ChartSeries[];
  yUnit: string;
  currentTimeS: number;
  referenceLines?: ReferenceLine[];
  eventMarkers?: EventMarker[];
}

const W = 600;
const H = 150;
const MARGIN = { top: 14, right: 12, bottom: 20, left: 44 };
const PLOT_W = W - MARGIN.left - MARGIN.right;
const PLOT_H = H - MARGIN.top - MARGIN.bottom;

/**
 * A restrained engineering line chart: no new dependency, built the
 * same way as PowerFlowSchematic -- plain inline SVG driven entirely
 * by real values already in memory. Reused by both telemetry panels
 * so later charts share one visual language.
 *
 * The whole run is always drawn; `currentTimeS` only moves a vertical
 * "you are here" marker -- it never truncates or recomputes the
 * series (see DESIGN.md section 15: show the real data, never
 * illustrate it).
 */
export function TelemetryChart({
  title,
  timeS,
  series,
  yUnit,
  currentTimeS,
  referenceLines = [],
  eventMarkers = [],
}: TelemetryChartProps) {
  const xMin = timeS[0];
  const xMax = timeS[timeS.length - 1];

  const allValues = series.flatMap((s) => s.values).concat(referenceLines.map((r) => r.value));
  const dataMin = Math.min(...allValues);
  const dataMax = Math.max(...allValues);
  const span = dataMax - dataMin || 1;
  const yMin = dataMin - span * 0.1;
  const yMax = dataMax + span * 0.1;

  const scaleX = (t: number) => MARGIN.left + ((t - xMin) / (xMax - xMin)) * PLOT_W;
  const scaleY = (v: number) => MARGIN.top + (1 - (v - yMin) / (yMax - yMin)) * PLOT_H;

  const yTicks = [yMin + (yMax - yMin) * 0.0, yMin + (yMax - yMin) * 0.5, yMax];
  const xTicks = [xMin, (xMin + xMax) / 2, xMax];

  return (
    <section className="flex flex-col gap-1.5 border border-hairline bg-surface px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
          {title}
        </span>
        <div className="flex gap-3">
          {series.map((s) => (
            <span key={s.label} className="flex items-center gap-1.5 font-mono text-[10.5px] text-secondary">
              <span
                className="inline-block h-[2px] w-3"
                style={{ backgroundColor: s.color, opacity: s.dashed ? 0.7 : 1 }}
              />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ minWidth: 280 }}>
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
              {v.toFixed(v > 100 ? 0 : 2)}
            </text>
          </g>
        ))}
        <text
          x={MARGIN.left}
          y={H - 4}
          fontFamily="var(--font-mono)"
          fontSize={9.5}
          fill={SVG_COLOR.textSecondary}
        >
          {yUnit}
        </text>

        {xTicks.map((t) => (
          <text
            key={t}
            x={scaleX(t)}
            y={H - 4}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize={9.5}
            fill={SVG_COLOR.textSecondary}
          >
            {t.toFixed(3)}s
          </text>
        ))}

        {referenceLines.map((r) => (
          <g key={r.label}>
            <line
              x1={MARGIN.left}
              x2={W - MARGIN.right}
              y1={scaleY(r.value)}
              y2={scaleY(r.value)}
              stroke={SVG_COLOR.textSecondary}
              strokeWidth={1}
              strokeDasharray="5 4"
            />
            <text
              x={W - MARGIN.right}
              y={scaleY(r.value) - 4}
              textAnchor="end"
              fontFamily="var(--font-mono)"
              fontSize={9.5}
              fill={SVG_COLOR.textSecondary}
            >
              {r.label}
            </text>
          </g>
        ))}

        {eventMarkers.map((ev) => (
          <g key={ev.label}>
            <line
              x1={scaleX(ev.time)}
              x2={scaleX(ev.time)}
              y1={MARGIN.top}
              y2={H - MARGIN.bottom}
              stroke={SVG_COLOR.textSecondary}
              strokeWidth={1}
              strokeDasharray="2 3"
              opacity={0.7}
            />
            <text
              x={scaleX(ev.time) + 4}
              y={MARGIN.top + 10}
              fontFamily="var(--font-sans)"
              fontSize={9.5}
              fill={SVG_COLOR.textSecondary}
            >
              {ev.label}
            </text>
          </g>
        ))}

        {series.map((s) => (
          <polyline
            key={s.label}
            points={timeS.map((t, i) => `${scaleX(t)},${scaleY(s.values[i])}`).join(" ")}
            fill="none"
            stroke={s.color}
            strokeWidth={1.5}
            strokeDasharray={s.dashed ? "5 4" : undefined}
          />
        ))}

        <line
          x1={scaleX(currentTimeS)}
          x2={scaleX(currentTimeS)}
          y1={MARGIN.top}
          y2={H - MARGIN.bottom}
          stroke={SVG_COLOR.textPrimary}
          strokeWidth={1.5}
        />
      </svg>
    </section>
  );
}
