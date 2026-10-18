/**
 * Content model for the Architecture Choices page (SPEC-011 v0.3).
 *
 * Reasoning content, not simulation input: no governing equations are
 * modeled and nothing here is a score or a ranking. Architectures are keyed
 * by the existing System Map `ArchitectureId` values, which are preserved.
 *
 * Evidence labels follow `docs/PRODUCT_BLUEPRINT.md` §5.1. A cell or item
 * carries ONE label: the label of its weakest claim. `public-fact` and
 * `emerging` items must cite at least one entry of `REFERENCES`; anything
 * that cannot cite a reference is labeled `assumption`. Textbook and
 * standard references are title-level (no page numbers).
 */

import type { ArchitectureId } from "./infrastructureMapData";

export type DriverId = "rd1" | "rd2" | "rd3" | "rd4" | "rd5" | "rd6" | "rd7";

export type EvidenceLabel = "public-fact" | "assumption" | "model-output" | "emerging";

export type ReferenceId =
  | "NVIDIA"
  | "OCP"
  | "OCPWP"
  | "OCPSST"
  | "SYSMAP"
  | "SANDBOX"
  | "MOHAN"
  | "GRAINGER"
  | "GOLDBOOK"
  | "NEC"
  | "IEEE1584"
  | "GARZON";

/**
 * Source type keeps vendor statements, consortium documents, textbook
 * principles and repository material distinct. `inspection` states what was
 * actually examined in the SPEC-011 source audit (2026-10-18); a textbook or
 * standard that was not opened is listed as background, not as verified.
 */
export interface Reference {
  id: ReferenceId;
  kind: "repository-source" | "textbook-standard" | "consortium-document" | "vendor-statement";
  inspection: string;
  citation: string;
  /** Present only for sources already recorded in `data/industry/`. */
  url?: string;
  verifiedDate?: string;
}

export const REFERENCES: Record<ReferenceId, Reference> = {
  NVIDIA: {
    id: "NVIDIA",
    kind: "vendor-statement",
    inspection: "Web page read in the 2026-10-18 audit (page dated 2026-08-11). Vendor statement: attributed, not endorsed.",
    citation: "NVIDIA Blog — 800 VDC Power Architecture for AI Factories (also recorded in data/industry/developments.yaml)",
    url: "https://blogs.nvidia.com/blog/800-vdc-power-architecture-ai-factory/",
    verifiedDate: "2026-10-04",
  },
  OCP: {
    id: "OCP",
    kind: "consortium-document",
    inspection: "Web page read in the 2026-10-18 audit. Consortium statement (Google, Microsoft, NVIDIA and others): attributed, not endorsed.",
    citation: "Open Compute Project Blog — Powering the Next Era of AI (also recorded in data/industry/standards.yaml)",
    url: "https://www.opencompute.org/index.php/blog/powering-the-next-era-of-ai-how-google-microsoft-and-nvidia-are-standardizing-and-accelerating-the-industry-transition-to-lvdc",
    verifiedDate: "2026-10-04",
  },
  OCPWP: {
    id: "OCPWP",
    kind: "consortium-document",
    inspection: "PDF text extracted and searched; the sections cited here were read (not all 155 pages). Consortium document: attributed, not endorsed.",
    citation: "OCP Data Center Facility — Low Voltage Direct Current Power Distribution white paper, v1.0 (30 March 2026)",
    url: "https://www.opencompute.org/documents/dcf-power-distribution-lvdc-white-paper-version-1-0-final-pdf-1",
  },
  OCPSST: {
    id: "OCPSST",
    kind: "consortium-document",
    inspection: "PDF text extracted and read (24 pages). Consortium document: attributed, not endorsed.",
    citation: "OCP Solid State Transformer (SST) Specification, Rev 0.3.0 (effective 22 June 2026; authors Google, Microsoft, NVIDIA; first draft)",
    url: "https://www.opencompute.org/documents/ocp-sst-design-specification-v0-3-final-pdf",
  },
  SYSMAP: {
    id: "SYSMAP",
    kind: "repository-source",
    inspection: "This repository.",
    citation: "This site's System Map category and architecture definitions (frontend/app/lib/infrastructureMapData.ts)",
  },
  SANDBOX: {
    id: "SANDBOX",
    kind: "repository-source",
    inspection: "This repository.",
    citation: "Advanced Sandbox: simplified average-value SST chain simulation (src/, SPEC-002 sensitivity study)",
  },
  MOHAN: {
    id: "MOHAN",
    kind: "textbook-standard",
    inspection: "Not inspected in the audit. Listed as background for a general engineering principle; not verified against the text.",
    citation: "Mohan, Undeland, Robbins — Power Electronics: Converters, Applications, and Design",
  },
  GRAINGER: {
    id: "GRAINGER",
    kind: "textbook-standard",
    inspection: "Not inspected in the audit. Listed as background for a general engineering principle; not verified against the text.",
    citation: "Grainger, Stevenson — Power System Analysis",
  },
  GOLDBOOK: {
    id: "GOLDBOOK",
    kind: "textbook-standard",
    inspection: "Not inspected in the audit. Listed as background for a general engineering principle; not verified against the text.",
    citation: "IEEE Std 493 (Gold Book) — Design of Reliable Industrial and Commercial Power Systems",
  },
  NEC: {
    id: "NEC",
    kind: "textbook-standard",
    inspection: "Not opened. The OCP white paper (inspected) cites NFPA 70 and IEC 60364 for these topics.",
    citation: "NFPA 70 (National Electrical Code); IEC 60364 (low-voltage electrical installations)",
  },
  IEEE1584: {
    id: "IEEE1584",
    kind: "textbook-standard",
    inspection: "Not inspected in the audit. Listed as background for a general engineering principle; not verified against the text.",
    citation: "IEEE Std 1584 — Guide for Performing Arc-Flash Hazard Calculations",
  },
  GARZON: {
    id: "GARZON",
    kind: "textbook-standard",
    inspection: "Not inspected in the audit. Listed as background for a general engineering principle; not verified against the text.",
    citation: "Garzon — High Voltage Circuit Breakers: Design and Applications",
  },
};

type NonEmptyRefs = readonly [ReferenceId, ...ReferenceId[]];

/** Evidence block shared by every content item. */
export type Evidence =
  | { evidence: "public-fact" | "emerging"; basis: string; refs: NonEmptyRefs }
  | { evidence: "model-output"; basis: string; refs: NonEmptyRefs; sandboxOnly: true }
  | { evidence: "assumption"; basis: string; refs?: readonly ReferenceId[] };

export const SOURCE_KIND_TEXT: Record<Reference["kind"], string> = {
  "repository-source": "this site",
  "textbook-standard": "textbook/standard, background",
  "consortium-document": "consortium document",
  "vendor-statement": "vendor statement",
};

export const EVIDENCE_LABEL_TEXT: Record<EvidenceLabel, string> = {
  "public-fact": "Public fact",
  assumption: "Illustrative assumption",
  "model-output": "Model output (simplified)",
  emerging: "Emerging / uncertain",
};

export const ARCHITECTURE_CHOICE_NAMES: Record<ArchitectureId, string> = {
  "conventional-ac": "Conventional AC",
  "ac-to-800vdc": "AC-fed 800 VDC",
  "mv-to-800vdc": "Conceptual MV-to-800 VDC via SST",
};

export const ARCHITECTURE_ORDER: readonly ArchitectureId[] = [
  "conventional-ac",
  "ac-to-800vdc",
  "mv-to-800vdc",
];

/** Mandatory disclosures (SPEC-011 R2). Wording is fixed by the spec. */
export const DISCLOSURES = {
  sst:
    "SST is one candidate technology for the medium-voltage-to-DC stage. It is not required for 800 VDC: the AC-fed 800 VDC architecture reaches the same bus without one.",
  block:
    "Blocks in these architectures are functional abstractions, not literal single-stage converters or literal racks; real equipment is internally multi-stage.",
  sim:
    "The Advanced Sandbox simulates only the Conceptual MV-to-800 VDC via SST slice, as a simplified average-value model. It does not validate, size or benchmark Conventional AC or AC-fed 800 VDC, and it is not evidence that any architecture is better.",
  illustrative:
    "Requirement drivers are illustrative teaching assumptions, not a design basis for any facility.",
  noWinner:
    "This page does not rank architectures or name a winner; every conditional statement depends on which driver dominates for a given site.",
} as const;

// ---------------------------------------------------------------------------
// Requirement drivers (illustrative). Each answers the five Blueprint §4
// questions: what / why / system / tradeoffs / decision.
// ---------------------------------------------------------------------------

export interface Driver {
  id: DriverId;
  title: string;
  question: string;
  what: string;
  why: string;
  system: string;
  tradeoffs: string;
  decision: string;
}

export const DRIVERS: readonly Driver[] = [
  {
    id: "rd1",
    title: "Rack power and growth",
    question: "How much power must reach each rack, and how does delivery scale as that grows?",
    what: "The power each rack draws, and the path by which that power is expected to increase.",
    why: "AI compute concentrates power in each rack, so delivery equipment must be sized for rack power and for its growth.",
    system: "Sets current, conductor and conversion capacity from the distribution stage to the rack input.",
    tradeoffs: "Higher delivery capacity costs equipment, space and money; unused headroom is stranded capacity.",
    decision: "Which distribution voltage and form to build for the expected range of rack power.",
  },
  {
    id: "rd2",
    title: "Load dynamics",
    question: "How fast can the load change, and where does the energy buffer sit?",
    what: "How quickly rack power can swing and how far the supply side must absorb that swing.",
    why: "A load step the supply cannot absorb becomes a voltage excursion on the bus or a disturbance seen upstream.",
    system: "Couples load behavior to the energy buffer, converter control response and the grid-side interface.",
    tradeoffs: "More buffering and faster control reduce excursions but add equipment, cost and control complexity.",
    decision: "Where to place stored energy and how fast the conversion stage must respond.",
  },
  {
    id: "rd3",
    title: "Availability and maintainability",
    question: "What redundancy exists, and can a section be isolated and worked on?",
    what: "How the design tolerates a failed component and allows maintenance without losing the load.",
    why: "Compute load lost to a single failure or maintenance action is costly, and redundancy has its own cost.",
    system: "Spans switchgear arrangement, conversion modules, storage and generation integration.",
    tradeoffs: "Higher redundancy (N+1, 2N) adds equipment and footprint; fewer series elements reduce failure points but concentrate risk.",
    decision: "What redundancy scheme and isolation capability each stage needs.",
  },
  {
    id: "rd4",
    title: "Safety and protection practice",
    question: "How are faults cleared, and how is personnel safety managed?",
    what: "How fault current is detected and interrupted, and the practice that keeps people safe around energized equipment.",
    why: "Fault energy and touch hazard depend on voltage, current and clearing time, and practice must match the technology.",
    system: "Links distribution voltage and form, protective devices and the monitoring/control system.",
    tradeoffs: "Faster, more selective protection costs complexity; unfamiliar technology means practice is less settled.",
    decision: "What protection scheme and safe-work practice the chosen distribution form requires.",
  },
  {
    id: "rd5",
    title: "Conversion chain and losses",
    question: "How many series conversion functions exist, and where is heat produced?",
    what: "The count of series conversion functions between grid and compute, and the loss each one adds.",
    why: "Each conversion function dissipates some power as heat, which must be rejected and paid for.",
    system: "Connects the conversion stage choice to cooling load and operating cost.",
    tradeoffs: "Fewer stages can mean lower loss on paper but more stress per stage and different failure modes.",
    decision: "Whether consolidating conversion functions is worth the new interface and protection requirements.",
  },
  {
    id: "rd6",
    title: "Physical footprint",
    question: "What space, conductor cross-section and cooling infrastructure does delivery require?",
    what: "The floor space, copper and cooling plant needed to deliver the power.",
    why: "Space and conductor mass are costly, and more space means longer runs and more loss.",
    system: "Ties the distribution voltage to conductor size and the conversion stage to cooling infrastructure.",
    tradeoffs: "Smaller conductors from higher voltage can be offset by larger or more specialized conversion and cooling equipment.",
    decision: "How to allocate floor space between conversion equipment, storage, distribution and compute.",
  },
  {
    id: "rd7",
    title: "Standards and ecosystem maturity",
    question: "How settled are the standards, equipment supply and operating practice?",
    what: "How established the governing standards, supplier base and field experience are.",
    why: "Unsettled standards risk interoperability gaps, supply constraints and rework.",
    system: "Affects every interface, because standards define what must interoperate at each boundary.",
    tradeoffs: "Mature practice lowers risk but may limit density; emerging practice offers capability with higher uncertainty.",
    decision: "How much emerging-technology risk the program accepts for the capability it needs.",
  },
] as const;

// ---------------------------------------------------------------------------
// Architectures by driver: 7 drivers x 3 architectures. The Record type makes
// a missing cell a compile error (SPEC-011 AC-3).
// ---------------------------------------------------------------------------

export type Cell = { how: string; harder: string } & Evidence;

export const CELLS: Record<DriverId, Record<ArchitectureId, Cell>> = {
  rd1: {
    "conventional-ac": {
      how: "Rack power is delivered as AC at a chosen distribution voltage. For a given voltage, conductor arrangement and power factor, more rack power means proportionally more current, so growth is met with larger conductors or more circuits. The OCP article describes the baseline as medium-voltage AC stepped down to 480 VAC feeding AC racks.",
      harder: "Large steps in rack power push conductor and busway size, or the number of circuits, upward.",
      evidence: "public-fact",
      basis: "Power–current relation (textbook principle; reference not inspected); OCP article's description of the baseline architecture.",
      refs: ["GRAINGER", "OCP", "SYSMAP"],
    },
    "ac-to-800vdc": {
      how: "For the same power, a higher distribution voltage means lower current per conductor, all else equal. The actual benefit depends on the AC voltage and phase arrangement it is compared with and on the DC conductor arrangement; the OCP white paper's wiring analysis (§6.3.3) shows that, for a given power, moving to a higher voltage class with correspondingly less conductor material can reduce relative cable losses and current, and that a bipolar arrangement with a midpoint conductor can reduce losses compared with a unipolar one when loads are balanced. Both NVIDIA and the OCP white paper cite rising rack power density as the motivation for DC distribution.",
      harder: "It needs rack-level DC-DC conversion and DC-rated equipment that conventional racks do not use.",
      evidence: "public-fact",
      basis: "Power–current relation (textbook principle; reference not inspected); OCP white paper executive summary and §6.3.3 wiring analysis; NVIDIA vendor statement on rack density.",
      refs: ["GRAINGER", "OCPWP", "NVIDIA", "SYSMAP"],
    },
    "mv-to-800vdc": {
      how: "The distribution-voltage benefit is the same as AC-fed 800 VDC. The difference is upstream, where an SST is the conceptual medium-voltage-to-DC source.",
      harder: "Supplying a facility-scale DC block this way depends on SST technology that is still being specified: NVIDIA describes direct medium-voltage conversion only for a future facility-scale unit, and the OCP SST specification is a first draft (Rev 0.3.0) with open items.",
      evidence: "emerging",
      basis: "NVIDIA vendor statement on a future facility-scale DC power block; OCP SST specification version history and TBD items.",
      refs: ["NVIDIA", "OCPSST"],
    },
  },
  rd2: {
    "conventional-ac": {
      how: "A double-conversion UPS places a DC link and battery between the AC source and the load, which can decouple load swings from the upstream source. How much depends on the UPS design.",
      harder: "Fast swings must still be absorbed within the UPS inverter and DC link ratings; this page gives no ratings.",
      evidence: "public-fact",
      basis: "Double-conversion UPS topology (textbook principle; reference not inspected); System Map description.",
      refs: ["MOHAN", "SYSMAP"],
    },
    "ac-to-800vdc": {
      how: "Storage attaches directly to the DC bus. Bus capacitance and the control of the centralized AC-DC stage set how far voltage moves in a load step (stored capacitor energy is ½CV², a relation also exercised in this repository's DC-bus tests). The OCP white paper examines closer integration of energy storage as part of DC distribution.",
      harder: "Bus voltage regulation becomes a control interface between the centralized stage and the rack DC-DC converters.",
      evidence: "public-fact",
      basis: "Capacitor energy relation (principle); OCP white paper efficiency discussion; System Map description of storage on the DC bus.",
      refs: ["MOHAN", "OCPWP", "SYSMAP"],
    },
    "mv-to-800vdc": {
      how: "The DC-bus mechanics match AC-fed 800 VDC, with the SST's control response also in the loop. The Advanced Sandbox illustrates this slice with a simplified model: an AI load step produces a bus-voltage sag whose size depends on bus capacitance and SST response time.",
      harder: "A fast load step also stresses the grid side of the SST. The Sandbox's simplified model does not represent real SST internals and validates no product.",
      evidence: "model-output",
      basis: "Calculated by the simplified Sandbox model from stated educational assumptions; applies to this slice only.",
      refs: ["SANDBOX"],
      sandboxOnly: true,
    },
  },
  rd3: {
    "conventional-ac": {
      how: "The OCP white paper cites strategies such as N+1 power blocks and UPS maintenance bypass for managing power-electronics failures, and the System Map describes N+1 and 2N redundancy.",
      harder: "More series equipment (transformers, UPS plant, distribution) has to be maintained.",
      evidence: "public-fact",
      basis: "OCP white paper redundancy section; System Map redundancy discussion; commercial power-system reliability practice (textbook; reference not inspected).",
      refs: ["OCPWP", "GOLDBOOK", "SYSMAP"],
    },
    "ac-to-800vdc": {
      how: "Redundancy concepts such as N+1 can be applied to centralized conversion modules and the DC bus, but the OCP white paper says DC distribution does not allow a UPS maintenance-bypass strategy, so redundancy is needed at power-block level and possibly in distribution.",
      harder: "The OCP white paper says strategies for availability in LVDC data centers require further investigation; this page cites no operating data for 800 VDC AI data centers.",
      evidence: "emerging",
      basis: "OCP white paper section on redundancy levels and availability.",
      refs: ["OCPWP", "OCP"],
    },
    "mv-to-800vdc": {
      how: "The OCP SST specification illustrates block (catcher) and distributed redundancy arrangements, and the OCP white paper says major building blocks are moving toward modular sub-blocks with live-swap capability.",
      harder: "Voltage levels for seamless redundancy design are an open (TBD) item in the SST specification, and this page cites no field data for a medium-voltage solid-state stage.",
      evidence: "emerging",
      basis: "OCP SST specification Appendix A and TBD items; OCP white paper availability discussion.",
      refs: ["OCPSST", "OCPWP"],
    },
  },
  rd4: {
    "conventional-ac": {
      how: "Installation practice and protective devices for AC are codified (the OCP white paper cites NFPA 70 and IEC 60364), and AC selectivity by time-current settings is the most widespread method. AC current's periodic zero crossings assist arc interruption (textbook principle; reference not inspected).",
      harder: "Arc-flash incident energy depends on fault current and protective clearing time together; the OCP white paper notes that time-current selectivity delays in AC systems can mean long arcing time in an arc flash. It must be reassessed whenever capacity or configuration changes.",
      evidence: "public-fact",
      basis: "OCP white paper protection section; NFPA 70, IEC 60364 and IEEE 1584 as general background (not inspected).",
      refs: ["OCPWP", "NEC", "IEEE1584", "GARZON"],
    },
    "ac-to-800vdc": {
      how: "DC interruption needs devices rated for DC. The OCP white paper describes conventional fuses and breakers interrupting by creating an arc voltage above the system voltage, and newer semiconductor-based devices. Clearances and personnel practice for 800 V DC differ from AC practice.",
      harder: "The OCP white paper states there is currently no standard or recognized practice for coordinating protection for the DC fault behaviors it describes, and no DC equivalent of IEEE 1584 for incident energy; the OCP article reports engagement with UL Solutions, NFPA, IEEE and IEC.",
      evidence: "emerging",
      basis: "OCP white paper protection section and incident-energy note; OCP article on standards and safety organizations.",
      refs: ["OCPWP", "OCP"],
    },
    "mv-to-800vdc": {
      how: "The OCP white paper's converter classification lists galvanic isolation by a high-frequency transformer, and notes fault-limiting converters can hold steady-state fault current to zero or low values.",
      harder: "The white paper says migrating to solid-state solutions may need a new approach to coordination studies, and the OCP SST specification is a first draft in which short-circuit duration and other values are still TBD.",
      evidence: "emerging",
      basis: "OCP white paper converter classification and protection discussion; OCP SST specification TBD items.",
      refs: ["OCPWP", "OCPSST"],
    },
  },
  rd5: {
    "conventional-ac": {
      how: "Power passes through AC-DC-AC conversion in a double-conversion UPS and AC-DC again in rack supplies. Each series function dissipates some power as heat, and series efficiencies multiply. The OCP article describes direct DC architectures as removing intermediate AC conversion stages and repeated AC/DC conversions.",
      harder: "Repeated conversion compounds losses and heat; this page gives no efficiency figures.",
      evidence: "public-fact",
      basis: "Series efficiency multiplication (textbook principle; reference not inspected); System Map conversion chain; OCP article.",
      refs: ["MOHAN", "SYSMAP", "OCP"],
    },
    "ac-to-800vdc": {
      how: "A centralized AC-DC stage replaces the UPS AC-AC chain. NVIDIA says 800 VDC leaves fewer conversion stages between grid and accelerator, and the OCP white paper cites a potential reduction in conversion stages while noting that realized gains depend on site-specific design.",
      harder: "The side-rack option still performs AC-to-DC conversion locally, the net stage count still depends on equipment upstream of the DC bus, and neither NVIDIA nor the OCP article gives a stage count or efficiency figure here, so no efficiency comparison is made.",
      evidence: "public-fact",
      basis: "NVIDIA vendor statement and OCP white paper efficiency discussion (attributed, not endorsed); OCP article description of the side-rack option.",
      refs: ["NVIDIA", "OCPWP", "OCP", "SYSMAP"],
    },
    "mv-to-800vdc": {
      how: "The OCP SST specification defines the SST as replacing the line-frequency medium-voltage transformer, rectifier units and, as required, energy storage: one functional block.",
      harder: "The specification is a black-box definition that lists several product components (power conversion, MVAC input, LVDC output, firmware and control, auxiliary power) and gives no stage count, so any stage reduction is not shown; general engineering practice is that such a converter is internally multi-stage; the efficiency of any real SST is product-specific and not compared here.",
      evidence: "public-fact",
      basis: "OCP SST specification scope and product-composition sections; System Map SST caveat.",
      refs: ["OCPSST", "SYSMAP"],
    },
  },
  rd6: {
    "conventional-ac": {
      how: "At a given distribution voltage and conductor arrangement, more power means more current and so more conductor cross-section for the same loss; UPS and battery rooms also occupy floor space.",
      harder: "Footprint grows with UPS plant and conductor size as rack power rises.",
      evidence: "public-fact",
      basis: "Conductor loss and sizing relations (textbook principle; reference not inspected); System Map UPS and battery plant description.",
      refs: ["GRAINGER", "SYSMAP"],
    },
    "ac-to-800vdc": {
      how: "Where the distribution voltage is higher for the same power and loss basis, conductors can be smaller. The saving depends on the comparison basis (AC voltage, phases, power factor, DC arrangement); the OCP white paper examines improved utilization of conductors while noting that realized gains depend on site-specific design. Centralized conversion equipment still needs space and cooling.",
      harder: "It moves heat and floor space from UPS rooms to conversion blocks and rack DC-DC stages; no sizing is claimed.",
      evidence: "public-fact",
      basis: "Conductor loss and sizing relations (textbook principle; reference not inspected); OCP white paper efficiency discussion.",
      refs: ["GRAINGER", "OCPWP"],
    },
    "mv-to-800vdc": {
      how: "The OCP SST specification states that an SST uses medium-to-high-frequency magnetic components and targets higher power density; smaller magnetics at higher frequency is a textbook relationship.",
      harder: "Cooling of the power section and packaging of new equipment become design questions; this page makes no footprint comparison.",
      evidence: "public-fact",
      basis: "OCP SST specification scope statement (a design target, not measured performance); transformer size–frequency relation (textbook; reference not inspected).",
      refs: ["OCPSST", "MOHAN"],
    },
  },
  rd7: {
    "conventional-ac": {
      how: "AC distribution is covered by established codes and standards (for example NFPA 70 and IEC 60364, both cited by the OCP white paper) and long operating practice.",
      harder: "The OCP white paper says rising rack power density and more dynamic loads are pushing data-center power beyond the limits of traditional architectures.",
      evidence: "public-fact",
      basis: "OCP white paper executive summary; NFPA 70 and IEC 60364 as cited there.",
      refs: ["OCPWP", "NEC", "GOLDBOOK"],
    },
    "ac-to-800vdc": {
      how: "The OCP article describes a Google, Microsoft and NVIDIA workstream to standardize 800 VDC (LVDC) data-center power, including an AC-fed side power rack option and a direct medium-voltage-to-800 VDC option.",
      harder: "Standards are still being developed: the OCP article describes engagement with UL Solutions, NFPA, IEEE and IEC on certification and regulatory frameworks. Interoperability and equipment availability should be verified, and this page makes no adoption claim.",
      evidence: "emerging",
      basis: "OCP article description of the standardization workstream and safety-organization engagement.",
      refs: ["OCP", "NVIDIA"],
    },
    "mv-to-800vdc": {
      how: "The OCP SST specification (Rev 0.3.0, effective 22 June 2026) defines the SST as a black box, with a focus on electrical, mechanical, thermal, control and communications interfaces.",
      harder: "Its own version history calls it a first draft and several values are TBD (for example short-circuit fault duration); this page makes no adoption claim and no maturity ordering among the architectures.",
      evidence: "emerging",
      basis: "OCP SST specification version history, scope and TBD items.",
      refs: ["OCPSST"],
    },
  },
};

// ---------------------------------------------------------------------------
// Interfaces: 5 boundaries x 3 architectures. nodeIds are existing System Map
// node ids (verified by the SPEC-011 AC-4 check).
// ---------------------------------------------------------------------------

export type BoundaryId = "mv-utility" | "conversion-distribution" | "distribution-rack" | "storage-backup" | "monitoring-control";

export const BOUNDARIES: ReadonlyArray<{ id: BoundaryId; title: string }> = [
  { id: "mv-utility", title: "Medium-voltage / utility" },
  { id: "conversion-distribution", title: "Conversion to distribution" },
  { id: "distribution-rack", title: "Distribution to rack" },
  { id: "storage-backup", title: "Storage and backup" },
  { id: "monitoring-control", title: "Monitoring and control" },
];

export type InterfaceItem = {
  crosses: string;
  concern: string;
  nodeIds: readonly [string, string];
} & Evidence;

const INTERFACE_BASIS =
  "System Map node definitions combined with illustrative engineering reasoning about the boundary.";

export const INTERFACES: Record<ArchitectureId, Record<BoundaryId, InterfaceItem>> = {
  "conventional-ac": {
    "mv-utility": {
      crosses: "Utility medium-voltage feed into site switchgear, through a step-down transformer.",
      concern: "Fault isolation and breaker coordination; utility interconnection requirements apply.",
      nodeIds: ["a-substation", "a-switchgear"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "conversion-distribution": {
      crosses: "UPS AC output at the distribution voltage.",
      concern: "Voltage and frequency quality, and behavior during transfer to and from the UPS.",
      nodeIds: ["a-conversion", "a-distribution"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "distribution-rack": {
      crosses: "AC feed into rack power supplies.",
      concern: "Rack supply input tolerance and per-rack capacity.",
      nodeIds: ["a-distribution", "a-rack"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "storage-backup": {
      crosses: "Battery on the UPS internal DC link; generators join the AC path through an automatic transfer switch.",
      concern: "Timing between storage ride-through and generator pickup.",
      nodeIds: ["a-backup", "a-conversion"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "monitoring-control": {
      crosses: "Status, alarms and setpoints between the monitoring system and the UPS plant.",
      concern: "Which system has control authority during a transfer event.",
      nodeIds: ["a-monitoring", "a-conversion"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
  },
  "ac-to-800vdc": {
    "mv-utility": {
      crosses: "Utility medium-voltage feed into site switchgear, through a step-down transformer (unchanged from conventional AC).",
      concern: "Fault isolation and breaker coordination; utility interconnection requirements apply.",
      nodeIds: ["b-substation", "b-switchgear"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "conversion-distribution": {
      crosses: "A regulated 800 VDC bus from the centralized AC-DC stage.",
      concern: "Bus voltage regulation, storage connection and DC fault protection.",
      nodeIds: ["b-conversion", "b-distribution"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "distribution-rack": {
      crosses: "800 VDC into rack-level DC-DC conversion.",
      concern: "Rack input voltage window, inrush or pre-charge, and DC protection at the rack.",
      nodeIds: ["b-distribution", "b-rack"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "storage-backup": {
      crosses: "Storage tied to the DC bus; generators remain AC and join upstream of the centralized stage.",
      concern: "Coordination between DC-bus storage and generator transfer.",
      nodeIds: ["b-backup", "b-conversion"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "monitoring-control": {
      crosses: "Status, alarms and setpoints between the monitoring system and the centralized conversion stage.",
      concern: "Control authority over DC-bus voltage between the centralized stage and the rack converters.",
      nodeIds: ["b-monitoring", "b-conversion"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
  },
  "mv-to-800vdc": {
    "mv-utility": {
      crosses: "Medium-voltage AC from site switchgear directly into the SST (conceptual; the utility's upstream transformation still exists).",
      concern: "Grid-side stress from load swings and protection coordination across a solid-state stage.",
      nodeIds: ["c-switchgear", "c-sst"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "conversion-distribution": {
      crosses: "A regulated 800 VDC bus from the SST output.",
      concern: "Bus voltage regulation by SST control, storage connection and DC fault protection.",
      nodeIds: ["c-sst", "c-distribution"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "distribution-rack": {
      crosses: "800 VDC into rack-level DC-DC conversion.",
      concern: "Rack input voltage window, inrush or pre-charge, and DC protection at the rack.",
      nodeIds: ["c-distribution", "c-rack"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "storage-backup": {
      crosses: "Storage tied to the DC bus; generators remain AC and connect on the medium-voltage side.",
      concern: "How backup sources and DC-bus storage coordinate with the SST during a grid loss.",
      nodeIds: ["c-backup", "c-sst"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
    "monitoring-control": {
      crosses: "Status, alarms and setpoints between the monitoring system and the SST.",
      concern: "SST control response and facility-level coordination across one large conversion block.",
      nodeIds: ["c-monitoring", "c-sst"],
      evidence: "assumption",
      basis: INTERFACE_BASIS,
    },
  },
};

// ---------------------------------------------------------------------------
// Conditional decisions: exactly one per driver. `favored` is a set and never
// asserts a universal winner.
// ---------------------------------------------------------------------------

export interface ConditionalDecision {
  dominantDriver: DriverId;
  favored: readonly [ArchitectureId, ...ArchitectureId[]];
  because: string;
  unless: readonly [string, ...string[]];
  connects: string;
  informs: string;
  evidence: EvidenceLabel;
  basis: string;
  refs?: readonly ReferenceId[];
}

export const CONDITIONAL_DECISIONS: Record<DriverId, ConditionalDecision> = {
  rd1: {
    dominantDriver: "rd1",
    favored: ["ac-to-800vdc", "mv-to-800vdc"],
    because: "At a higher distribution voltage the same power needs lower current per conductor, all else equal, which can ease conductor sizing as rack power grows; the benefit depends on the AC voltage and conductor arrangement being compared.",
    unless: [
      "DC-rated protection and safe-work practice cannot be established for the site (see safety and protection practice).",
      "Standards and equipment maturity must be settled before commitment (see standards and ecosystem maturity).",
      "AC distribution can still deliver the required rack power in the available space.",
    ],
    connects: "Links the rack power requirement to the distribution-to-rack interface.",
    informs: "Which distribution voltage to design for.",
    evidence: "assumption",
    basis: "Illustrative preference, not a ranking. Context: power–current relation; NVIDIA's description of 800 VDC for high-density racks.",
    refs: ["GRAINGER", "NVIDIA"],
  },
  rd2: {
    dominantDriver: "rd2",
    favored: ["conventional-ac", "ac-to-800vdc", "mv-to-800vdc"],
    because: "Load-step behavior depends on where stored energy sits and how fast the controls respond, not on the architecture label, so favor whichever places adequate buffering closest to the load with enough control bandwidth.",
    unless: [
      "The expected step size exceeds the buffer or converter rating of the chosen design.",
      "The control response of the conversion stage cannot hold bus or output voltage within the load's tolerance.",
    ],
    connects: "Links load behavior to the storage and control interfaces.",
    informs: "Where to place the energy buffer and what control response to require.",
    evidence: "assumption",
    basis: "Illustrative reasoning; the simplified Sandbox illustrates this only for the SST slice and does not compare architectures.",
  },
  rd3: {
    dominantDriver: "rd3",
    favored: ["conventional-ac"],
    because: "Redundancy patterns, switching schemes and operating practice are established, and this page cites no comparable operating data for the DC architectures.",
    unless: [
      "Rack power requirements exceed what AC distribution can deliver in the available space.",
      "The operator can validate a redundancy design for centralized conversion modules and the DC bus.",
    ],
    connects: "Links availability needs to switchgear, conversion and storage arrangements.",
    informs: "What redundancy scheme to adopt and how much operating-experience risk to accept.",
    evidence: "assumption",
    basis: "Illustrative preference, not a ranking. Context: established redundancy practice; the OCP white paper's statement that LVDC availability strategies require further investigation; this page cites no operating data for the DC architectures.",
    refs: ["OCPWP", "GOLDBOOK", "SYSMAP"],
  },
  rd4: {
    dominantDriver: "rd4",
    favored: ["conventional-ac"],
    because: "AC installation practice and protective devices are codified, while DC fault interruption and 800 V DC safe-work practice are still being established.",
    unless: [
      "The organization can adopt DC-rated protection, training and procedures.",
      "Standards and safety guidance for 800 VDC reach the maturity the site requires.",
    ],
    connects: "Links protection scheme to distribution form and the monitoring system.",
    informs: "What protection scheme and safe-work practice to commit to.",
    evidence: "assumption",
    basis: "Illustrative preference, not a ranking. Context: codified AC practice; the OCP white paper's statement (§7.2) that there is currently no standard or recognized practice for coordinating protection for the converter-fed DC fault behavior it describes, in particular the capacitor-discharge peak; OCP's reported work with standards and safety organizations.",
    refs: ["NEC", "OCPWP", "OCP"],
  },
  rd5: {
    dominantDriver: "rd5",
    favored: ["ac-to-800vdc"],
    because: "A centralized AC-DC stage can replace the UPS AC-AC chain on paper, and series efficiencies multiply. The SST folds functions into one block but is internally multi-stage, so a reduction there is not established.",
    unless: [
      "Upstream equipment or utility constraints fix the stage count regardless of architecture.",
      "Functional blocks are not physical stages: any stage-count or efficiency reduction must be shown for the specific equipment, and this page makes no efficiency comparison.",
    ],
    connects: "Links conversion stage choice to the heat the cooling system must reject.",
    informs: "Whether consolidating conversion functions justifies the new interface and protection requirements.",
    evidence: "assumption",
    basis: "Illustrative preference, not a ranking. Context: series efficiency multiplication; NVIDIA's stated aim of fewer conversion stages.",
    refs: ["MOHAN", "NVIDIA"],
  },
  rd6: {
    dominantDriver: "rd6",
    favored: ["ac-to-800vdc", "mv-to-800vdc"],
    because: "Where the distribution voltage is higher for the same power and loss basis, conductors can be smaller; the saving depends on the comparison basis.",
    unless: [
      "Centralized conversion and cooling equipment offsets the conductor saving.",
      "Available space or building layout favors a distributed approach.",
    ],
    connects: "Links distribution voltage to conductor size and conversion location to cooling infrastructure.",
    informs: "How to allocate floor space between conversion, storage, distribution and compute.",
    evidence: "assumption",
    basis: "Illustrative preference, not a ranking. Context: conductor loss and sizing relations.",
    refs: ["GRAINGER"],
  },
  rd7: {
    dominantDriver: "rd7",
    favored: ["conventional-ac"],
    because: "Standards, equipment supply and operating practice are established, while public sources describe the 800 VDC and SST work as in progress.",
    unless: [
      "Required rack density cannot be met with AC distribution.",
      "The program accepts emerging-standard risk and can follow the OCP workstream.",
    ],
    connects: "Links standards maturity to every interface boundary.",
    informs: "How much emerging-technology risk the program accepts for the capability it needs.",
    evidence: "assumption",
    basis: "Illustrative preference, not a ranking. Context: established codes and reliability standards; OCP's description of ongoing standardization.",
    refs: ["NEC", "GOLDBOOK", "OCP"],
  },
};

// ---------------------------------------------------------------------------
// Validation needs: what would have to be shown, by what kind of evidence.
// ---------------------------------------------------------------------------

export type EvidenceKind = "analysis" | "simulation" | "factory test" | "site test" | "conformance review";

export interface ValidationItem {
  verifies: string;
  kinds: readonly [EvidenceKind, ...EvidenceKind[]];
}

export const VALIDATION_NEEDS: Record<ArchitectureId, readonly ValidationItem[]> = {
  "conventional-ac": [
    { verifies: "UPS transfer and ride-through on utility loss, including generator pickup.", kinds: ["site test"] },
    { verifies: "Protection coordination from medium voltage through low-voltage distribution.", kinds: ["analysis"] },
    { verifies: "Distribution capacity at the target rack power and growth path.", kinds: ["analysis"] },
    { verifies: "Arc-flash hazard at available fault current.", kinds: ["analysis"] },
  ],
  "ac-to-800vdc": [
    { verifies: "DC fault detection and clearing at the bus and at the rack.", kinds: ["analysis", "factory test"] },
    { verifies: "Bus voltage behavior under load steps with the specified storage.", kinds: ["simulation", "site test"] },
    { verifies: "Rack DC-DC compatibility with the bus voltage window, inrush and pre-charge.", kinds: ["factory test", "conformance review"] },
    { verifies: "Safe-work and clearance practice for 800 V DC.", kinds: ["conformance review"] },
  ],
  "mv-to-800vdc": [
    { verifies: "Medium-voltage-side protection coordination and fault ride-through of the solid-state stage.", kinds: ["analysis", "factory test"] },
    { verifies: "Thermal performance of the power section at rated loss.", kinds: ["factory test"] },
    { verifies: "DC-bus control stability with the SST response in the loop.", kinds: ["simulation", "site test"] },
    { verifies: "Conformance to the evolving SST specification.", kinds: ["conformance review"] },
  ],
};

export const VALIDATION_SECTION_EVIDENCE: Evidence = {
  evidence: "assumption",
  basis: "Illustrative list of what would need to be shown; not a complete validation plan for any facility.",
};
