"use client";

import type { ReactNode } from "react";

import { decimateMinMax } from "./decimate";

/* ---------- page header: one question, one answer, one mode ---------- */

export function AreaHeader({
  mode,
  area,
  question,
  answer,
}: {
  mode: string;
  area: string;
  question: string;
  answer: ReactNode;
}) {
  return (
    <div className="lab-wrap lab-head">
      <div className="lab-mode">
        {area} <b>{mode}</b>
      </div>
      <h1 className="lab-h1">{question}</h1>
      <p className="lab-lede">{answer}</p>
    </div>
  );
}

/* ---------- basis & limits: disclosures stay verbatim, one click away ---------- */

export type BasisNote = string | { tag: string; text: string };

export function BasisBar({
  notes,
  labels,
  heading = "Basis & limits",
}: {
  notes: readonly BasisNote[];
  labels?: ReactNode;
  heading?: string;
}) {
  return (
    <section className="lab-basis" aria-label={heading}>
      <div className="lab-basis-head">
        <strong>{heading}</strong>
        <span className="s">Applies to everything on this page.</span>
        {labels}
      </div>
      <ul className="lab-basis-grid">
        {notes.map((n, i) => {
          const note = typeof n === "string" ? { tag: i === 0 ? "Scope" : "Note", text: n } : n;
          return (
            <li key={note.text}>
              <b>{note.tag}</b>
              <span>{note.text}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/* ---------- evidence chip: neutral color, glyph + text carry meaning ---------- */

export type Evidence = "public-fact" | "assumption" | "model-output" | "emerging";

/** Canonical labels: identical to EVIDENCE_LABEL_TEXT in architectureChoicesData.ts. */
const EVIDENCE_TEXT: Record<Evidence, string> = {
  "public-fact": "Public fact",
  assumption: "Illustrative assumption",
  "model-output": "Model output (simplified)",
  emerging: "Emerging / uncertain",
};

function Glyph({ kind }: { kind: Evidence }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.6 } as const;
  return (
    <svg viewBox="0 0 10 10" aria-hidden>
      {kind === "public-fact" && <rect x="1" y="1" width="8" height="8" {...common} fill="currentColor" />}
      {kind === "assumption" && <circle cx="5" cy="5" r="3.6" {...common} />}
      {kind === "model-output" && <path d="M5 .8 9.2 5 5 9.2.8 5Z" {...common} fill="currentColor" />}
      {kind === "emerging" && <path d="M5 1 9.2 9H.8Z" {...common} />}
    </svg>
  );
}

/** `short` only abbreviates the visible text in dense grids; the full canonical label stays in the accessible name. */
export function EvidenceChip({ kind, short }: { kind: Evidence; short?: boolean }) {
  return (
    <span className="lab-chip" title={EVIDENCE_TEXT[kind]}>
      <Glyph kind={kind} />
      {short ? (
        <>
          <span aria-hidden>{EVIDENCE_TEXT[kind].split(" ")[0]}</span>
          <span className="lab-sr">{EVIDENCE_TEXT[kind]}</span>
        </>
      ) : (
        EVIDENCE_TEXT[kind]
      )}
    </span>
  );
}

export function EvidenceLegend() {
  return (
    <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
      {(Object.keys(EVIDENCE_TEXT) as Evidence[]).map((k) => (
        <EvidenceChip key={k} kind={k} />
      ))}
    </span>
  );
}

/* ---------- line chart: real series only, decimated for drawing ---------- */

export interface Series {
  name: string;
  x: readonly number[];
  y: readonly number[];
  color: string;
}
export interface Marker {
  x: number;
  label: string;
  color?: string;
}
export interface HLine {
  y: number;
  label: string;
  color: string;
}

export function LineChart({
  title,
  unit,
  series,
  markers = [],
  hlines = [],
  xUnit = "s",
  yMin,
  yMax,
  xTicks = 5,
}: {
  title: string;
  unit: string;
  series: Series[];
  markers?: Marker[];
  hlines?: HLine[];
  xUnit?: string;
  yMin?: number;
  yMax?: number;
  xTicks?: number;
}) {
  const W = 480;
  const H = 250;
  const m = { l: 46, r: 12, t: 16, b: 28 };
  const all = series.flatMap((s) => [...s.y]);
  const lo = yMin ?? Math.min(...all, ...hlines.map((h) => h.y));
  const hi = yMax ?? Math.max(...all, ...hlines.map((h) => h.y));
  const pad = (hi - lo || 1) * 0.06;
  const y0 = yMin ?? lo - pad;
  const y1 = yMax ?? hi + pad;
  const x0 = Math.min(...series.map((s) => s.x[0]));
  const x1 = Math.max(...series.map((s) => s.x[s.x.length - 1]));
  const sx = (v: number) => m.l + ((v - x0) / (x1 - x0 || 1)) * (W - m.l - m.r);
  const sy = (v: number) => H - m.b - ((v - y0) / (y1 - y0 || 1)) * (H - m.t - m.b);
  const fmt = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));
  const yt = [0, 1, 2, 3, 4].map((i) => y0 + ((y1 - y0) * i) / 4);
  const xt = Array.from({ length: xTicks }, (_, i) => x0 + ((x1 - x0) * i) / (xTicks - 1));

  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 6, flexWrap: "wrap" }}>
        <span className="lab-h3" style={{ margin: 0 }}>
          {title} <span className="lab-unit">[{unit}]</span>
        </span>
        <span style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--color-text-secondary)" }}>
          {series.map((s) => (
            <span key={s.name} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <i style={{ width: 14, height: 2, background: s.color, display: "inline-block" }} />
              {s.name}
            </span>
          ))}
        </span>
      </figcaption>
      <div className="lab-chart-scroll" tabIndex={0} role="group" aria-label={`${title} chart (scrolls sideways on narrow screens)`}>
      <svg className="lab-chart" viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`${title} chart`}>
        {yt.map((v) => (
          <g key={v}>
            <line x1={m.l} x2={W - m.r} y1={sy(v)} y2={sy(v)} stroke="var(--color-hairline)" strokeWidth="1" />
            <text x={m.l - 8} y={sy(v) + 3} textAnchor="end">
              {fmt(v)}
            </text>
          </g>
        ))}
        {xt.map((v) => (
          <text key={v} x={sx(v)} y={H - 8} textAnchor="middle">
            {v.toFixed(v < 10 && x1 < 5 ? 2 : 0)}
            {v === x1 ? ` ${xUnit}` : ""}
          </text>
        ))}
        {hlines.map((h) => (
          <g key={h.label}>
            <line x1={m.l} x2={W - m.r} y1={sy(h.y)} y2={sy(h.y)} stroke={h.color} strokeDasharray="4 4" strokeWidth="1" />
            <text x={W - m.r - 4} y={sy(h.y) - 4} textAnchor="end" style={{ fill: h.color }}>
              {h.label}
            </text>
          </g>
        ))}
        {markers.map((mk) => (
          <g key={mk.label + mk.x}>
            <line x1={sx(mk.x)} x2={sx(mk.x)} y1={m.t} y2={H - m.b} stroke={mk.color ?? "var(--lab-hairline-strong)"} strokeDasharray="2 3" strokeWidth="1" />
            <text x={sx(mk.x) + 4} y={m.t + 9}>
              {mk.label}
            </text>
          </g>
        ))}
        {series.map((s) => {
          const { xs, ys } = decimateMinMax(s.x, s.y);
          const d = xs.map((xv, i) => `${i ? "L" : "M"}${sx(xv).toFixed(1)},${sy(ys[i]).toFixed(1)}`).join(" ");
          return <path key={s.name} d={d} fill="none" stroke={s.color} strokeWidth="1.6" strokeLinejoin="round" />;
        })}
      </svg>
      </div>
    </figure>
  );
}
