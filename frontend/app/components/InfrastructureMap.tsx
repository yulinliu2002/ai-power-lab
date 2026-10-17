"use client";

import { useMemo, useRef, useState } from "react";

import {
  ARCHITECTURES,
  CATEGORIES,
  LANE_META,
  type ArchitectureId,
  type ArchitectureNode,
  type Lane,
} from "../lib/infrastructureMapData";

/**
 * The expanded, interactive infrastructure map for `/system-map`
 * (AI Power Lab 2.0 Phase 1C). Replaces the narrow grid→SST→bus→load
 * view as the page's primary diagram: a broader set of infrastructure
 * categories, three switchable representative architectures, and a
 * progressive-disclosure detail panel per node.
 *
 * Deliberately plain HTML/CSS cards and connectors rather than SVG --
 * this needs to reflow cleanly from a horizontal flow on wide screens
 * to a stacked list on narrow ones, and the content (prose in a detail
 * panel) matters more here than precise diagram geometry. `lane`
 * groups (main/backup/cooling/monitoring) are rendered as visually
 * separate rows rather than one dense graph with crossing connector
 * lines, per the product brief's rejection of crowded diagrams.
 */
export function InfrastructureMap() {
  const [architectureId, setArchitectureId] = useState<ArchitectureId>(ARCHITECTURES[0].id);
  const architecture = useMemo(
    () => ARCHITECTURES.find((a) => a.id === architectureId) ?? ARCHITECTURES[0],
    [architectureId],
  );
  const [selectedNodeId, setSelectedNodeId] = useState<string>(architecture.nodes[0].id);
  const detailRef = useRef<HTMLDivElement>(null);

  const selectedNode =
    architecture.nodes.find((n) => n.id === selectedNodeId) ?? architecture.nodes[0];

  function selectArchitecture(next: ArchitectureId) {
    setArchitectureId(next);
    const nextArchitecture = ARCHITECTURES.find((a) => a.id === next);
    if (nextArchitecture) setSelectedNodeId(nextArchitecture.nodes[0].id);
  }

  function selectNode(id: string) {
    setSelectedNodeId(id);
    detailRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  const lanes: Lane[] = ["main", "backup", "cooling", "monitoring"];

  return (
    <section className="flex flex-col gap-3 border border-hairline bg-surface px-4 py-3.5">
      <div className="flex flex-col gap-2">
        <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
          Architecture view
        </span>
        <ArchitectureSelector selected={architectureId} onSelect={selectArchitecture} />
        <p className="max-w-3xl text-[12px] leading-relaxed text-secondary">{architecture.summary}</p>
        <p className="border border-hairline bg-surface-raised px-2.5 py-2 text-[12px] leading-relaxed text-secondary">
          <strong className="text-primary">Illustrative, not universal:</strong> {architecture.caveat}
        </p>
      </div>

      {/* The electrical chain gets the section's full content width --
       * the detail panel used to sit beside it in a fixed 300px
       * column, which squeezed the main lane below its unscrolled
       * content width on most desktop viewports and forced horizontal
       * scrolling that a wider column would have avoided. `min-w-0`
       * still matters here: without it, this flex item's automatic
       * minimum size is its full min-content width, so the
       * `overflow-x-auto` main-lane row below can't shrink below its
       * unscrolled width on narrow viewports where scrolling is
       * actually needed. */}
      <div className="flex min-w-0 flex-col gap-3">
        {lanes.map((lane) => (
          <LaneRow
            key={lane}
            lane={lane}
            nodes={architecture.nodes.filter((n) => n.lane === lane)}
            selectedNodeId={selectedNodeId}
            onSelect={selectNode}
          />
        ))}
      </div>

      <DetailPanel ref={detailRef} node={selectedNode} />
    </section>
  );
}

function ArchitectureSelector({
  selected,
  onSelect,
}: {
  selected: ArchitectureId;
  onSelect: (id: ArchitectureId) => void;
}) {
  return (
    <div role="radiogroup" aria-label="Architecture view" className="flex flex-wrap gap-1.5">
      {ARCHITECTURES.map((a) => {
        const isSelected = a.id === selected;
        return (
          <button
            key={a.id}
            type="button"
            role="radio"
            aria-checked={isSelected}
            onClick={() => onSelect(a.id)}
            className={`flex flex-col items-start gap-0.5 rounded border-2 px-2.5 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary ${
              isSelected
                ? "border-primary bg-surface-raised text-primary"
                : "border-hairline bg-surface text-secondary hover:bg-surface-raised"
            }`}
          >
            <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.03em]">{a.name}</span>
            <span className="text-[10.5px] text-muted">{a.tagline}</span>
          </button>
        );
      })}
    </div>
  );
}

function LaneRow({
  lane,
  nodes,
  selectedNodeId,
  onSelect,
}: {
  lane: Lane;
  nodes: readonly ArchitectureNode[];
  selectedNodeId: string;
  onSelect: (id: string) => void;
}) {
  if (nodes.length === 0) return null;
  const meta = LANE_META[lane];
  // Only the main lane is a single continuous electrical path end to
  // end -- it scrolls horizontally as one row instead of wrapping, so
  // the grid→...→load sequence always reads left to right without a
  // line break splitting it. The other lanes aren't a single series
  // path (backup/cooling/monitoring describe parallel or overlay
  // systems), so they keep wrapping to fit the viewport.
  const isMainPath = lane === "main";

  return (
    <div className={`flex min-w-0 flex-col gap-1.5 border-l-2 ${meta.accentClass} pl-2.5`}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-primary">
          {meta.label}
        </span>
        <span className="text-[11px] text-muted">{meta.description}</span>
      </div>
      <div
        role="group"
        aria-label={meta.label}
        className={
          isMainPath
            ? "-mx-1 flex min-w-0 items-stretch gap-1.5 overflow-x-auto px-1 pb-1"
            : "flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:items-stretch sm:gap-1.5"
        }
      >
        {nodes.map((node, i) => (
          <div key={node.id} className="flex items-stretch gap-1.5">
            <NodeButton
              node={node}
              isSelected={node.id === selectedNodeId}
              onSelect={onSelect}
              noShrink={isMainPath}
            />
            {i < nodes.length - 1 && lane !== "monitoring" && <LaneArrow />}
          </div>
        ))}
      </div>
    </div>
  );
}

/** A small flat chevron -- replaces a plain "→" character so the
 * connector reads cleanly at any zoom level and stays on the muted
 * token rather than an ad hoc text color. */
function LaneArrow() {
  return (
    <span aria-hidden="true" className="flex shrink-0 items-center text-muted">
      <svg width="12" height="10" viewBox="0 0 12 10" fill="none">
        <path d="M1 5h9M6 1l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function NodeButton({
  node,
  isSelected,
  onSelect,
  noShrink = false,
}: {
  node: ArchitectureNode;
  isSelected: boolean;
  onSelect: (id: string) => void;
  /** Main-lane buttons sit in a horizontally scrolling row and must
   * not shrink to fit -- every other lane still flexes/wraps. */
  noShrink?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={isSelected}
      onClick={() => onSelect(node.id)}
      className={`flex min-w-[132px] flex-col gap-0.5 border-2 px-2.5 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary ${
        noShrink ? "shrink-0 basis-[150px]" : "flex-1 sm:flex-none sm:basis-[150px]"
      } ${
        isSelected
          ? "border-primary bg-surface-raised"
          : "border-hairline bg-surface hover:bg-surface-raised"
      }`}
    >
      <span className="text-[12px] font-semibold text-primary">{node.label}</span>
      <span className="text-[10.5px] text-muted">{node.detail}</span>
    </button>
  );
}

function DetailPanel({
  node,
  ref,
}: {
  node: ArchitectureNode;
  ref: React.Ref<HTMLDivElement>;
}) {
  const category = CATEGORIES[node.categoryId];

  return (
    <div
      ref={ref}
      tabIndex={-1}
      className="flex max-w-2xl flex-col gap-2.5 border border-hairline bg-surface-raised px-3 py-3"
    >
      <div className="flex flex-col gap-0.5 border-b border-hairline pb-2">
        <span className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-muted">
          {category.title}
        </span>
        <span className="text-[13px] font-bold text-primary">{node.label}</span>
      </div>

      {/* Keyed by node id so switching nodes always re-collapses the
       * technical-depth section -- a learner moving on to the next
       * node shouldn't inherit the previous node's expanded state. */}
      <DetailPanelContent key={node.id} node={node} category={category} />
    </div>
  );
}

function DetailPanelContent({
  node,
  category,
}: {
  node: ArchitectureNode;
  category: (typeof CATEGORIES)[ArchitectureNode["categoryId"]];
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      {/* Concise by default: just this node's own instantiation and
       * the category's one-sentence definition -- enough to orient
       * without reading three more fields on every single click. */}
      <DetailField label="In this architecture" body={node.instantiation} />
      <DetailField label="What it is" body={category.what} />

      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        className="flex items-center gap-1.5 self-start font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
      >
        <span className="font-mono text-[12px] leading-none">{expanded ? "−" : "+"}</span>
        {expanded ? "Show less" : "Why it exists, considerations & alternatives"}
      </button>

      {expanded && (
        <div className="flex flex-col gap-2.5 border-t border-hairline pt-2">
          <DetailField label="Why it exists" body={category.why} />
          <DetailList label="Key design considerations" items={category.considerations} />
          <DetailList label="Alternatives & variations" items={category.alternatives} />
        </div>
      )}
    </>
  );
}

function DetailField({ label, body }: { label: string; body: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
        {label}
      </span>
      <p className="text-[12px] leading-relaxed text-secondary">{body}</p>
    </div>
  );
}

function DetailList({ label, items }: { label: string; items: readonly string[] }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
        {label}
      </span>
      <ul className="flex flex-col gap-1">
        {items.map((item) => (
          <li key={item} className="flex gap-1.5 text-[12px] leading-relaxed text-secondary">
            <span aria-hidden="true" className="text-muted">
              &middot;
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
