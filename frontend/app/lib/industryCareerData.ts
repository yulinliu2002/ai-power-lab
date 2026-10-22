/**
 * Industry & Career content (SPEC-013). Static, typed teaching content: no
 * engineering model, no units, no simulation. Every item carries exactly one
 * evidence label (Blueprint §5.1). Claims are attributed ("X says..."), never
 * stated as fact about the world, and each has a passage locator that the
 * claim-to-passage audit (docs/validation/SPEC-013-validation.md) is built from.
 *
 * Assumptions: content is illustrative teaching text built from five public
 * sources as read on the dates in READ_LOG; sources may change. Role-activity
 * sentences and generic standards notes are educational assumptions.
 * Limitations: five sources are a thin base, not an industry survey; vendor and
 * consortium statements are attributed, not endorsed, and no performance claim
 * is validated here.
 *
 * `data/industry/` (YAML) is the pre-existing Streamlit-era record; it is not
 * read or rendered by this module.
 */
import {
  REFERENCES,
  type EvidenceLabel,
  type Reference,
} from "./architectureChoicesData";

export type IndustryRefId = "NVIDIA" | "OCP" | "OCPWP" | "OCPSST" | "EATON";

export const INDUSTRY_REF_ORDER: readonly IndustryRefId[] = ["NVIDIA", "OCP", "OCPWP", "OCPSST", "EATON"];

/** Registry entry shape, with an id limited to this page's five sources. */
export type IndustryReference = Omit<Reference, "id"> & { id: IndustryRefId };

/**
 * Eaton is held here rather than in the shared `REFERENCES` registry: the
 * `/architecture` page renders every registry entry, so adding Eaton there
 * would change that page's text (SPEC-013 AC-18). See the validation record.
 */
const EATON_REFERENCE: IndustryReference = {
  id: "EATON",
  kind: "vendor-statement",
  inspection:
    "Web page text read on 2026-10-21 through a text fetch (no page date shown). Vendor product page: attributed, not endorsed.",
  citation: "Eaton: Medium-voltage solid-state transformer (MVSST) product page",
  url: "https://www.eaton.com/us/en-us/catalog/medium-voltage-power-distribution-control-systems/medium-voltage-solid-state-transformer.html",
};

export const INDUSTRY_REFERENCES: Record<IndustryRefId, IndustryReference> = {
  NVIDIA: REFERENCES.NVIDIA as IndustryReference,
  OCP: REFERENCES.OCP as IndustryReference,
  OCPWP: REFERENCES.OCPWP as IndustryReference,
  OCPSST: REFERENCES.OCPSST as IndustryReference,
  EATON: EATON_REFERENCE,
};

/**
 * Read dates are kept apart from the registry's `verifiedDate` (the 2026-10-04
 * YAML verification date, neither reused nor edited here).
 * `readDate`: when the live source was last read for this page.
 * `pageDate`: the date printed on the source, if any.
 */
export interface ReadLogEntry {
  readDate: string;
  pageDate?: string;
  /** Title printed on the page, where it differs from the registry citation. */
  pageTitle?: string;
  /** URL actually read, where it differs from the registry URL. */
  readUrl?: string;
  /** What was and was not re-read. */
  note?: string;
}

export const READ_LOG: Record<IndustryRefId, ReadLogEntry> = {
  NVIDIA: {
    readDate: "2026-10-21",
    pageDate: "2026-08-11",
    pageTitle: "Why Scaling AI Compute Performance Requires a New Power Architecture",
    note: "The recorded industry-data date (\"2024-2025\") does not match the date printed on the page (11 August 2026); the printed date is used.",
  },
  OCP: {
    readDate: "2026-10-21",
    pageDate: "2026-08-11",
    pageTitle: "Powering the Next Era of AI: How Google, Microsoft and Nvidia Are Standardizing and Accelerating the Industry Transition to LVDC",
    readUrl:
      "https://www.opencompute.org/news/powering-the-next-era-of-ai-how-google-microsoft-and-nvidia-are-standardizing-and-accelerating-the-industry-transition-to-lvdc/",
    note: "The page also shows a later modified date of 2026-09-24.",
  },
  OCPWP: {
    readDate: "2026-10-18",
    pageDate: "2026-03-30",
    note: "Not re-read for this page: the fetch on 2026-10-21 failed. The claims below rely on the 2026-10-18 source audit (SPEC-011), in which only the cited sections were read, not the whole 155 pages.",
  },
  OCPSST: {
    readDate: "2026-10-21",
    pageDate: "2026-06-22",
    note: "The cover gives the effective date 2026-06-22; the version history gives 2026-05-20 for version 0.3.",
  },
  EATON: {
    readDate: "2026-10-21",
    note: "The page shows no publication date, only a 2026 copyright footer.",
  },
};

export const KIND_TEXT: Record<Reference["kind"], string> = {
  "repository-source": "Repository source",
  "textbook-standard": "Textbook or standard",
  "consortium-document": "Consortium document",
  "vendor-statement": "Vendor statement",
};

// ---------------------------------------------------------------------------
// "What would you ask?" -- a fixed list of validation prompts (no free input).
// ---------------------------------------------------------------------------

export type QuestionId = "conditions" | "method" | "status" | "independent" | "scope" | "nature";

export const QUESTIONS: ReadonlyArray<{ id: QuestionId; text: string }> = [
  { id: "conditions", text: "At what load and operating conditions does it apply?" },
  { id: "method", text: "By what test method was it established?" },
  { id: "status", text: "Is it a draft, a plan, or a finished document?" },
  { id: "independent", text: "Who other than the author has checked it?" },
  { id: "scope", text: "What does it leave out?" },
  { id: "nature", text: "Is it a measurement, a design target, or a description?" },
];

// ---------------------------------------------------------------------------
// Claim sheets
// ---------------------------------------------------------------------------

/** One attributed statement from a source, with the evidence for it. */
export interface SourceClaim {
  /** Attributed statement as shown in the sheet details. */
  text: string;
  /** Section heading, page number or table row in the source. */
  locator: string;
  /** Verbatim supporting span of at most 25 words, where one was extracted for this page. */
  span?: string;
  /**
   * `supported`: a verbatim span was extracted on the read date.
   * `paraphrase-checked`: carried from the SPEC-011 source audit; no verbatim span extracted for this page.
   */
  audit: "supported" | "paraphrase-checked";
}

export interface ClaimSheetData {
  id: string;
  sourceId: IndustryRefId;
  /** One plain-language claim sentence, shown at heading scale. */
  claim: string;
  /** Exactly one label: the label of the weakest claim on the sheet. */
  evidence: EvidenceLabel;
  /** Basis text shown beside the label. */
  basis: string;
  claims: readonly SourceClaim[];
  /** Required, non-empty. */
  doesNotTell: readonly string[];
  /** Sheet-specific answers to the shared prompts; a prompt without one is not answered by the passages audited. */
  answers: Partial<Record<QuestionId, string>>;
  /** One sentence relating the claim to another area, plus a text link. */
  relation: { text: string; href: string; label: string };
  /** Career Map priority (Charter §4 number) this sheet exercises. */
  competency: { priority: number; text: string };
  /** Extra notes on assumptions in this sheet, if any. */
  note?: string;
}

export const CLAIM_SHEETS: readonly ClaimSheetData[] = [
  {
    id: "nvidia",
    sourceId: "NVIDIA",
    claim: "NVIDIA says 800 VDC distribution leaves fewer conversion stages between the grid and the accelerator.",
    evidence: "public-fact",
    basis: "What NVIDIA says on its own blog, as read on the date shown. A statement about the vendor's position, not a measured result.",
    claims: [
      {
        text: "NVIDIA says distributing power as direct current at higher voltage puts fewer conversion stages between the grid and the accelerator.",
        locator: "Article body, paragraph beginning \"800 VDC simplifies that path\"",
        span: "fewer conversion stages stand between the grid and the accelerator",
        audit: "supported",
      },
      {
        text: "NVIDIA describes a hybrid path that it says is designed to fit into existing AC infrastructure and deliver 800 VDC to compute racks within the row.",
        locator: "Article body, hybrid-path passage",
        span: "designed to slot into existing AC infrastructure and deliver 800 VDC to compute racks within the row",
        audit: "supported",
      },
    ],
    doesNotTell: [
      "It gives no efficiency percentage or measured benefit for 800 VDC.",
      "\"Fewer\" is not counted: the article does not say how many stages are removed.",
      "It is a vendor blog post, so it states NVIDIA's position, not independent test data.",
    ],
    answers: {
      conditions: "The article gives no efficiency or loss figure, so there are no conditions to check.",
      status: "A blog post dated 11 August 2026. It describes a direction, not a finished specification.",
      independent: "It is NVIDIA's own account of NVIDIA's architecture.",
      scope: "\"Fewer\" stages is not quantified, and no efficiency figure is given.",
    },
    relation: {
      text: "Fewer stages is the idea behind the AC-fed 800 VDC and MV-to-800 VDC options that Architecture Choices compares.",
      href: "/architecture",
      label: "Architecture Choices",
    },
    competency: { priority: 3, text: "Reading a vendor's architecture statement against the power chain it describes." },
  },
  {
    id: "ocp-blog",
    sourceId: "OCP",
    claim: "An OCP post describes two ways to reach 800 VDC: a side power rack that converts existing 480 VAC locally, or direct conversion from medium-voltage AC.",
    evidence: "public-fact",
    basis: "What the post says, as read on the date shown. The post is signed by two NVIDIA Data Center Engineering authors.",
    claims: [
      {
        text: "The post describes a dedicated side power rack that converts existing 480 VAC to DC locally, next to the compute racks.",
        locator: "Section \"A Flexible Path Forward for Every Data Center\", option A",
        span: "A dedicated side power rack converts existing 480 VAC to either +/-400 or 0-800 VDC locally",
        audit: "supported",
      },
      {
        text: "The post describes direct medium-voltage-AC-to-800 VDC conversion, using transformer rectifiers or solid-state transformer skids.",
        locator: "Section \"A Flexible Path Forward for Every Data Center\", option B",
        span: "transformer rectifiers or solid-state transformer skids to convert MVAC directly to 800 VDC",
        audit: "supported",
      },
      {
        text: "The post says the authors are engaging with UL Solutions, NFPA, IEEE and IEC.",
        locator: "Section \"What We Are Building Together at OCP\"",
        span: "We are engaging in parallel with UL Solutions, NFPA, IEEE, and IEC",
        audit: "supported",
      },
      {
        text: "The post says higher-voltage DC distribution can move more power with less conductor than lower-voltage alternatives.",
        locator: "Section \"A Shared Problem Demands a Shared Standard\"",
        span: "move more power with less conductor/copper than lower-voltage alternatives",
        audit: "supported",
      },
    ],
    doesNotTell: [
      "In the passages audited here it names the two options but does not say which is better or compare them on efficiency or cost.",
      "Saying that engagement with standards bodies is under way is not saying that any certification exists.",
      "The post is signed by two NVIDIA Data Center Engineering authors; it is a consortium site carrying those authors' account.",
    ],
    answers: {
      status: "A blog post, posted 11 August 2026 and later modified (2026-09-24).",
      independent: "It is signed by two NVIDIA Data Center Engineering authors.",
      scope: "It names two options; the audited passages do not compare them with measurements.",
    },
    relation: {
      text: "An SST is one candidate for the medium-voltage-to-DC stage; the first option needs no SST, so an SST is not required for 800 VDC.",
      href: "/system-map",
      label: "System Map",
    },
    competency: { priority: 9, text: "Recognising architecture patterns in public material, and which ones need no SST." },
  },
  {
    id: "ocp-whitepaper",
    sourceId: "OCPWP",
    claim: "The OCP low-voltage DC white paper says DC distribution does not allow a UPS maintenance-bypass strategy, and that availability strategies need further investigation.",
    evidence: "emerging",
    basis: "What the paper says in the sections read for this site (a first release, v1.0). Architecture direction, not demonstrated performance.",
    claims: [
      {
        text: "The paper says DC distribution does not allow a UPS maintenance-bypass strategy, and that strategies for availability in low-voltage DC data centers require further investigation.",
        locator: "White paper section 4.2 (SPEC-011 source audit, 2026-10-18)",
        span: "require further investigation",
        audit: "paraphrase-checked",
      },
      {
        text: "The paper says that, for a given power, a higher voltage class with correspondingly less conductor material can reduce relative cable losses and current.",
        locator: "White paper section 6.3.3 (SPEC-011 source audit, 2026-10-18)",
        audit: "paraphrase-checked",
      },
    ],
    doesNotTell: [
      "Only selected sections were read for this site, not the whole paper, so this sheet says nothing about the rest of it.",
      "The paper also cites earlier DC installations; this site makes no operating-experience claim either way.",
      "The loss statement is for a given power, and its numeric example is deliberately not reproduced here.",
    ],
    answers: {
      status: "Version 1.0, first release, dated 30 March 2026. The SST specification is a separate document and is a draft.",
      independent: "An OCP consortium document; this site treats it as attributed, not endorsed.",
      scope: "Only selected sections were read for this site.",
      conditions: "The section 6.3.3 statement is for a given power; its numeric example is not reproduced here.",
    },
    relation: {
      text: "Redundancy and availability are drivers that Architecture Choices compares across the three architectures.",
      href: "/architecture",
      label: "Architecture Choices",
    },
    competency: { priority: 4, text: "Reading an availability claim and asking what redundancy it assumes." },
    note: "Verbatim spans for this sheet were not re-extracted: the 2026-10-21 fetch of the white paper failed.",
  },
  {
    id: "ocp-sst",
    sourceId: "OCPSST",
    claim: "OCP's SST specification, Rev 0.3.0, is a first draft of a medium-voltage-to-800 VDC conversion platform, and it leaves some items to be defined.",
    evidence: "emerging",
    basis: "A draft specification: what it says it will specify, as read on the date shown. Not a statement that any product meets it.",
    claims: [
      {
        text: "The version history describes version 0.3 as the first draft of the SST product for the OCP community.",
        locator: "Version history, page 2",
        span: "first draft of SST product for OCP community",
        audit: "supported",
      },
      {
        text: "The specification is titled as a medium-voltage-to-800 VDC power conversion platform.",
        locator: "Cover page, subtitle",
        span: "Medium Voltage to 800 VDC Power Conversion Platform",
        audit: "supported",
      },
      {
        text: "The specification marks voltage levels for seamless redundancy design as to be defined.",
        locator: "Section 5.2.1, item (c), page 14",
        span: "(TBD, pending future definitions) voltage levels for seamless redundancy design",
        audit: "supported",
      },
      {
        text: "The specification says details of grounding will be provided in later revisions.",
        locator: "Section 5.4, page 15",
        span: "Details will be provided in later revisions of the specification.",
        audit: "supported",
      },
    ],
    doesNotTell: [
      "A specification states what a product must do, not that any product does it.",
      "Items marked TBD are not yet defined, so interfaces that depend on them can still change.",
      "It is a draft: later revisions may differ.",
    ],
    answers: {
      status: "A first draft (Rev 0.3.0), effective 22 June 2026.",
      scope: "Grounding detail and voltage levels for seamless redundancy design are left for later revisions.",
      nature: "A design specification: it states requirements for a platform, not measured results.",
      independent: "Its listed authors are Google, Microsoft and NVIDIA.",
    },
    relation: {
      text: "The OCP material places the SST as a candidate for the medium-voltage-to-DC stage; an SST is not required for an 800 VDC bus.",
      href: "/architecture",
      label: "Architecture Choices",
    },
    competency: { priority: 8, text: "Reading a draft specification: what it fixes, and what it leaves open." },
  },
  {
    id: "eaton",
    sourceId: "EATON",
    claim: "Eaton lists a 15 kV-class, 2 MW medium-voltage solid-state transformer with converter efficiency above 97% at 800 VDC output.",
    evidence: "public-fact",
    basis: "What Eaton lists on its product page, as read on the date shown. A vendor statement about a product, not a verified performance result.",
    claims: [
      {
        text: "Eaton lists a 15 kV class voltage.",
        locator: "Specifications table: Voltage class",
        span: "15 kV class",
        audit: "supported",
      },
      {
        text: "Eaton lists a 2 MW overall load power rating.",
        locator: "Specifications table: Overall load power rating",
        span: "2 MW",
        audit: "supported",
      },
      {
        text: "Eaton lists converter efficiency above 97% at 800 VDC output.",
        locator: "Specifications table: Converter efficiency",
        span: ">97% @ 800 VDC output",
        audit: "supported",
      },
      {
        text: "Eaton says the system is designed to support high-voltage DC systems, including emerging 800 VDC.",
        locator: "FAQ",
        span: "designed to support high-voltage DC systems, including emerging 800 VDC",
        audit: "supported",
      },
      {
        text: "Eaton lists the unit as having a hermetically sealed power section with liquid cooling.",
        locator: "Specifications table: Style",
        span: "Outdoor with hermetically sealed power section and liquid cooling",
        audit: "supported",
      },
    ],
    doesNotTell: [
      "Conditions not stated on the page: the efficiency row gives no load level, temperature or test method.",
      "The page's output and certification rows refer to electric vehicle charging; it states no data-center certification.",
      "The page shows no publication date, and its footer says specifications are subject to change without notice.",
      "The Advanced Sandbox is not calibrated to this or any product, and its output is not compared with this figure.",
    ],
    answers: {
      conditions: "Not stated on the page: no load level or temperature accompanies the efficiency figure.",
      method: "Not stated on the page: no test method accompanies the efficiency figure.",
      status: "A product page with no publication date; the footer says specifications may change without notice.",
      independent: "It is Eaton's own listing; it names no independent test of the efficiency figure.",
      scope: "The page's certification and output rows refer to electric vehicle charging.",
      nature: "A listed figure on a product page, with no stated method; it is not shown as a measurement.",
    },
    relation: {
      text: "Eaton's figure concerns one product; the System Map shows where a medium-voltage conversion stage sits in the chain.",
      href: "/system-map",
      label: "System Map",
    },
    competency: { priority: 10, text: "Reading a vendor efficiency figure: what load, temperature and method stand behind it." },
  },
];

/**
 * Factual assertions made outside `claims` (in `answers`, `doesNotTell`, bases and
 * detail notes). Each is audited like a claim (SPEC-013 AC-19).
 * `supported`: verbatim span extracted 2026-10-21.
 * `absence-observed`: a negative statement; `span` is empty and `checked` says what was looked for.
 * `registry-citation`: taken from the shared registry citation (SPEC-011 audit), no span for this page.
 */
export interface SourceAssertion {
  sheetId: string;
  assertion: string;
  locator: string;
  span?: string;
  checked?: string;
  audit: "supported" | "absence-observed" | "registry-citation";
}

export const ASSERTION_AUDIT: readonly SourceAssertion[] = [
  { sheetId: "nvidia", assertion: "The post is dated 11 August 2026.", locator: "Article byline", span: "August 11, 2026", audit: "supported" },
  { sheetId: "nvidia", assertion: "The article gives no efficiency percentage or measured benefit for 800 VDC.", locator: "Whole article", checked: "Searched the fetched article text for an efficiency percentage or measured 800 VDC benefit; none found.", audit: "absence-observed" },
  { sheetId: "nvidia", assertion: "\"Fewer\" stages is not counted.", locator: "Article body, paragraph beginning \"800 VDC simplifies that path\"", checked: "The passage states \"fewer conversion stages\" without a number of stages.", audit: "absence-observed" },
  { sheetId: "ocp-blog", assertion: "The post is signed by two NVIDIA Data Center Engineering authors.", locator: "Post byline", span: "Posted by Jason Adrian and Mike Tu, NVIDIA Data Center Engineering", audit: "supported" },
  { sheetId: "ocp-blog", assertion: "The post was posted on 11 August 2026.", locator: "Post header", span: "Date of Post August 11, 2026", audit: "supported" },
  { sheetId: "ocp-blog", assertion: "The page metadata gives a later modified date of 2026-09-24.", locator: "Page metadata: modified time", span: "2026-09-24", audit: "supported" },
  { sheetId: "ocp-blog", assertion: "The audited passages name two options but do not compare them on efficiency or cost.", locator: "Section \"A Flexible Path Forward for Every Data Center\"", checked: "Bounded to the passages audited here; no efficiency or cost comparison found in them.", audit: "absence-observed" },
  { sheetId: "ocp-whitepaper", assertion: "The white paper is version 1.0, first release, dated 30 March 2026.", locator: "Registry citation for OCPWP (SPEC-011 audit)", audit: "registry-citation" },
  { sheetId: "ocp-sst", assertion: "The specification is Rev 0.3.0, effective 22 June 2026.", locator: "Cover page", span: "Specification Effective 6/22/2026", audit: "supported" },
  { sheetId: "ocp-sst", assertion: "The listed authors are Google, Microsoft and NVIDIA.", locator: "Cover page", span: "Author: Google, Microsoft, Nvidia", audit: "supported" },
  { sheetId: "ocp-sst", assertion: "Grounding detail is left to later revisions.", locator: "Section 5.4, page 15", span: "Details will be provided in later revisions of the specification.", audit: "supported" },
  { sheetId: "eaton", assertion: "The page's certification line concerns electric vehicle charging.", locator: "Certifications table", span: "certified by UL or equivalent NRTL for electric vehicle charging", audit: "supported" },
  { sheetId: "eaton", assertion: "The page's output rows describe passenger-vehicle charging connections.", locator: "Specifications table: DC output / DC charger circuit types", span: "Passenger vehicle configuration CCS or NACS (200-900V)", audit: "supported" },
  { sheetId: "eaton", assertion: "The footer says specifications are subject to change without notice.", locator: "Page footer", span: "Due to continuing improvements, specifications are subject to change without notice.", audit: "supported" },
  { sheetId: "eaton", assertion: "The page shows no publication date.", locator: "Page metadata and body", checked: "Publish-date metadata empty; only a 2026 copyright footer found.", audit: "absence-observed" },
  { sheetId: "eaton", assertion: "The efficiency row gives no load level, temperature or test method.", locator: "Specifications table: Converter efficiency", checked: "Row reads \">97% @ 800 VDC output\" with no further conditions.", audit: "absence-observed" },
];

// ---------------------------------------------------------------------------
// Standards and specifications
// ---------------------------------------------------------------------------

export interface SpecStatusRow {
  sourceId: "OCPWP" | "OCPSST";
  title: string;
  status: "draft" | "published";
  statusLine: string;
  /** Anchor of the claim sheet this row links back to. */
  sheetId: string;
}

export const SPEC_STATUS_ROWS: readonly SpecStatusRow[] = [
  {
    sourceId: "OCPWP",
    title: "OCP low-voltage DC power distribution white paper",
    status: "published",
    statusLine: "Published, version 1.0, first release, 30 March 2026.",
    sheetId: "ocp-whitepaper",
  },
  {
    sourceId: "OCPSST",
    title: "OCP Solid State Transformer (SST) Specification",
    status: "draft",
    statusLine: "Draft: Rev 0.3.0, first draft, effective 22 June 2026.",
    sheetId: "ocp-sst",
  },
];

export interface BackgroundStandard {
  name: string;
  title: string;
  /** Topic sentence. */
  topic: string;
  /** `assumption`: generic educational note. `sourced`: a source read in this repository already says so. */
  basis: "assumption" | "sourced";
  /** Locator for a sourced note. */
  locator?: string;
}

export const BACKGROUND_STANDARDS: readonly BackgroundStandard[] = [
  {
    name: "NFPA 70",
    title: "National Electrical Code",
    topic: "Installation practice for electrical systems. The OCP white paper cites it.",
    basis: "sourced",
    locator: "OCP white paper, cited (SPEC-011 source audit, 2026-10-18)",
  },
  {
    name: "IEC 60364",
    title: "Low-voltage electrical installations",
    topic: "Installation practice for low-voltage systems. The OCP white paper cites it.",
    basis: "sourced",
    locator: "OCP white paper, cited (SPEC-011 source audit, 2026-10-18)",
  },
  {
    name: "IEEE 1547",
    title: "Interconnection and interoperability of distributed energy resources with associated electrical power systems interfaces",
    topic: "How equipment that supplies power connects to the grid.",
    basis: "assumption",
  },
  {
    name: "UL 1741",
    title: "Inverters, converters, controllers and interconnection system equipment for use with distributed energy resources",
    topic: "Safety listing of power-conversion equipment connected to a grid.",
    basis: "assumption",
  },
  {
    name: "IEC 62477-1",
    title: "Safety requirements for power electronic converter systems and equipment, Part 1: General",
    topic: "Safety of power-electronic converters in general.",
    basis: "assumption",
  },
  {
    name: "IEEE 493",
    title: "Recommended practice for the design of reliable industrial and commercial power systems (Gold Book)",
    topic: "Reliability of power system designs.",
    basis: "assumption",
  },
  {
    name: "IEEE 1584",
    title: "Guide for performing arc-flash hazard calculations",
    topic: "Arc-flash incident energy. The OCP white paper notes there is no DC equivalent of it.",
    basis: "sourced",
    locator: "OCP white paper, protection section (SPEC-011 source audit, 2026-10-18)",
  },
];

// ---------------------------------------------------------------------------
// Career Map (PROJECT_CHARTER.md section 4) and the section 2.2 ladder
// ---------------------------------------------------------------------------

export interface CareerRow {
  priority: number;
  band: "P0" | "P1" | "P2";
  title: string;
  /** In-app exercise points; empty means "not yet exercised". */
  exercised: ReadonlyArray<{ href: string; label: string }>;
  /** Generic role-activity sentence (educational assumption, not a job description). */
  activity: string;
}

const SYSTEM_MAP = { href: "/system-map", label: "System Map" };
const ARCHITECTURE = { href: "/architecture", label: "Architecture Choices" };
const LEARN = { href: "/learn", label: "Learn by Example" };
const SANDBOX = { href: "/sandbox", label: "Advanced Sandbox" };

export const CAREER_ROWS: readonly CareerRow[] = [
  {
    priority: 1, band: "P0", title: "Systems architecture and controls",
    exercised: [SYSTEM_MAP, ARCHITECTURE],
    activity: "Define subsystem boundaries and interfaces, and decide which controller has authority over which quantity.",
  },
  {
    priority: 2, band: "P0", title: "SST and power-electronics architecture at the system level",
    exercised: [ARCHITECTURE, SANDBOX],
    activity: "Reason about conversion stages, source and load interaction, and where energy is buffered.",
  },
  {
    priority: 3, band: "P0", title: "AI data-center power architecture",
    exercised: [SYSTEM_MAP, ARCHITECTURE, LEARN],
    activity: "Follow power from the utility to the rack and explain what each stage is for.",
  },
  {
    priority: 4, band: "P1", title: "Thermal, protection and reliability",
    exercised: [LEARN, SANDBOX],
    activity: "Check that a protection setting clears a fault in time, and that a thermal limit is respected.",
  },
  {
    priority: 5, band: "P1", title: "Controls, SCADA and industrial integration",
    exercised: [],
    activity: "Connect a controller to supervisory systems and check that signals mean what each side thinks they mean.",
  },
  {
    priority: 6, band: "P1", title: "Commissioning, FAT/SAT, sequence of operation and system validation",
    exercised: [],
    activity: "Write and follow a test sequence that shows equipment behaves as specified before it is energised for service.",
  },
  {
    priority: 7, band: "P2", title: "Requirements engineering",
    exercised: [ARCHITECTURE],
    activity: "Turn a stated need into a requirement that can be allocated to a subsystem and later verified.",
  },
  {
    priority: 8, band: "P2", title: "Relevant industry standards",
    exercised: [{ href: "#standards", label: "Standards and specifications (this page)" }],
    activity: "Find which standard governs an interface and note whether the document is a draft or published.",
  },
  {
    priority: 9, band: "P2", title: "Real-world system-architecture patterns",
    exercised: [ARCHITECTURE, { href: "#claims", label: "Claims to read (this page)" }],
    activity: "Recognise a pattern in a public description and say what it assumes.",
  },
  {
    priority: 10, band: "P2", title: "Verification and validation methodology",
    exercised: [ARCHITECTURE, { href: "#claims", label: "Claims to read (this page)" }],
    activity: "Decide what evidence (analysis, simulation, factory test, site test) would show a requirement is met.",
  },
];

/** Charter section 2.2 ladder, quoted as written there. */
export const CHARTER_LADDER: readonly string[] = [
  "Equipment / Controls Engineering",
  "Systems Engineering",
  "Senior Systems Engineering",
  "Systems Architecture / Technical Leadership",
];

export const SE_ACTIVITIES: ReadonlyArray<{ activity: string; where: ReadonlyArray<{ href: string; label: string }>; note: string }> = [
  { activity: "Requirements", where: [ARCHITECTURE], note: "Step 1 of Architecture Choices picks an illustrative requirement." },
  { activity: "Interface definition", where: [SYSTEM_MAP, ARCHITECTURE], note: "The System Map shows interfaces; Architecture Choices lists what each boundary needs." },
  { activity: "Trade study", where: [ARCHITECTURE], note: "Architecture Choices compares alternatives against a requirement, without naming a winner." },
  { activity: "Verification and validation", where: [ARCHITECTURE], note: "Step 4 of Architecture Choices lists the validation each architecture would need." },
  { activity: "Commissioning", where: [], note: "Not yet exercised in this app." },
];

// ---------------------------------------------------------------------------
// "Questions to ask" lists (validation prompts; educational assumptions)
// ---------------------------------------------------------------------------

export const QUESTIONS_TO_ASK = {
  claims: [
    "What load and temperature does a stated efficiency apply to?",
    "What test method produced the figure, and who ran it?",
    "Is the document a draft, and what does it leave undefined?",
    "Who other than the author has checked it?",
  ],
  standards: [
    "Is this a published standard, a draft specification, or a title I have not opened?",
    "Which interface or topic does it govern, and does a source I have read say so?",
    "Does it apply to DC at this voltage, or was it written for AC?",
  ],
  career: [
    "Which activity here does the app only describe, and which does it let me practise?",
    "What evidence would show I can do this activity, not only name it?",
    "Which of these rows has no exercise point yet, and why?",
  ],
} as const;

/** Handoff handling for the home card (SPEC-013 R10, AC-25). */
export const HOME_CARD = {
  question: "How do I judge what the industry is claiming?",
  description:
    "Read public 800 VDC and solid-state-transformer claims the way an engineer would: what each one says, how strong the evidence is, and which systems-engineering competency it exercises.",
} as const;
