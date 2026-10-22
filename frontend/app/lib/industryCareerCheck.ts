/**
 * Content-invariant checks for SPEC-013 (AC-2..AC-5, AC-7..AC-9, AC-14, AC-16,
 * AC-19..AC-22, AC-25). No test runner is added (SPEC-013 Q2); compile and run
 * with the commands in docs/validation/SPEC-013-validation.md.
 *
 *   node <outDir>/lib/industryCareerCheck.js <frontendDir> [--audit]
 *
 * `--audit` also prints the claim-to-passage audit table as Markdown.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { REFERENCES } from "./architectureChoicesData";
import {
  BACKGROUND_STANDARDS,
  CAREER_ROWS,
  CHARTER_LADDER,
  CLAIM_SHEETS,
  HOME_CARD,
  INDUSTRY_REFERENCES,
  INDUSTRY_REF_ORDER,
  QUESTIONS,
  QUESTIONS_TO_ASK,
  READ_LOG,
  SE_ACTIVITIES,
  SPEC_STATUS_ROWS,
} from "./industryCareerData";

const frontend = process.argv[2] ?? ".";
const app = join(frontend, "app");
let failures = 0;
const check = (id: string, ok: boolean, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"} ${id}${detail ? ` - ${detail}` : ""}`);
  if (!ok) failures += 1;
};

const industryDir = join(app, "industry");
const pageSrc = readFileSync(join(industryDir, "page.tsx"), "utf8");
const sheetSrc = readFileSync(join(industryDir, "ClaimSheet.tsx"), "utf8");
const dataSrc = readFileSync(join(app, "lib", "industryCareerData.ts"), "utf8");

// Everything a learner can read: the data module plus the two page files.
const rendered = [pageSrc, sheetSrc, dataSrc].join("\n");
// Text that is rendered as words (string literals and JSX text), without code.
const words = (src: string) => src.replace(/^\s*(import|export type|\/\/).*$/gm, "");

// AC-2: five sheets, one per source, no sixth.
check("AC-2 five sheets", CLAIM_SHEETS.length === 5);
check("AC-2 one sheet per source", new Set(CLAIM_SHEETS.map((s) => s.sourceId)).size === 5 &&
  INDUSTRY_REF_ORDER.every((id) => CLAIM_SHEETS.some((s) => s.sourceId === id)));
check("AC-2 no sample content", !/\bsample\b/i.test(words(rendered)));

// AC-3: one label per sheet; public-fact/emerging resolve to a reference with URL and a READ_LOG date.
for (const s of CLAIM_SHEETS) {
  const ref = INDUSTRY_REFERENCES[s.sourceId];
  const ok = ["public-fact", "assumption", "model-output", "emerging"].includes(s.evidence) &&
    (s.evidence === "assumption" || (!!ref.url && !!READ_LOG[s.sourceId]?.readDate));
  check(`AC-3 ${s.id}`, ok, s.evidence);
  check(`AC-3 ${s.id} model-output not used`, s.evidence !== "model-output");
}
check("AC-3 READ_LOG has all five", INDUSTRY_REF_ORDER.every((id) => /^\d{4}-\d{2}-\d{2}$/.test(READ_LOG[id]?.readDate ?? "")));

// R17 variant: the shared registry is untouched.
// Deviation 1 in the validation record: Eaton is page-local so /architecture is unchanged. This asserts the
// implemented design, not R17 compliance; R17 as written is open pending a Lead decision.
check("DEVIATION-1 EATON is page-local (R17 as written not met)", !("EATON" in REFERENCES) && INDUSTRY_REFERENCES.EATON.id === "EATON");

// AC-4
const sst = CLAIM_SHEETS.find((s) => s.sourceId === "OCPSST")!;
check("AC-4 OCP SST emerging and draft", sst.evidence === "emerging" && /\bdraft\b/i.test(JSON.stringify(sst)));

// AC-5 / R19: Eaton attribution, enumerated figures, non-calibration, conditions.
const eaton = CLAIM_SHEETS.find((s) => s.sourceId === "EATON")!;
const eatonText = JSON.stringify(eaton);
check("AC-5 Eaton attributed", /^Eaton (lists|says)/.test(eaton.claim) && eaton.claims.every((c) => /^Eaton /.test(c.text)));
check("AC-5 Eaton conditions unstated", /Conditions not stated on the page/.test(eatonText));
check("AC-5 Eaton non-calibration", /not calibrated to this or any product/.test(eatonText));
const eatonNumbers = (eaton.claims.map((c) => c.text).join(" ") + " " + eaton.claim).match(/\d+(\.\d+)?/g) ?? [];
check("R19 Eaton numbers only {15, 2, 97, 800}", eatonNumbers.every((n) => ["15", "2", "97", "800"].includes(n)), eatonNumbers.join(","));

// AC-6
check("AC-6 NVIDIA page and read dates", READ_LOG.NVIDIA.pageDate === "2026-08-11" && !!READ_LOG.NVIDIA.readDate);

// AC-7: non-empty "does not tell you".
check("AC-7 does-not-tell non-empty", CLAIM_SHEETS.every((s) => s.doesNotTell.length > 0 && s.doesNotTell.every((t) => t.trim().length > 20)));

// AC-8: ten rows matching Charter section 4; link targets exist.
const expectedPriority = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
check("AC-8 ten rows", CAREER_ROWS.map((r) => r.priority).join() === expectedPriority.join());
check("AC-8 bands", CAREER_ROWS.every((r) => r.band === (r.priority <= 3 ? "P0" : r.priority <= 6 ? "P1" : "P2")));
const targets = new Set<string>();
for (const r of CAREER_ROWS) for (const e of r.exercised) targets.add(e.href);
for (const a of SE_ACTIVITIES) for (const e of a.where) targets.add(e.href);
for (const s of CLAIM_SHEETS) targets.add(s.relation.href);
const routeOk = (href: string) => href.startsWith("#") || existsSync(join(app, href.replace(/^\//, ""), "page.tsx"));
check("AC-8 link targets exist", [...targets].every(routeOk), [...targets].join(" "));
check("AC-8 sheet competency rows exist", CLAIM_SHEETS.every((s) => CAREER_ROWS.some((r) => r.priority === s.competency.priority)));

// AC-9: forbidden wording (whole words, so "Leadership" in the charter ladder is not a hit).
const forbidden = /\b(ranking|rankings|leaders?|market share|salary|salaries|hiring|forecast|forecasts)\b/i;
check("AC-9 forbidden wording", !forbidden.test(words(rendered)));

// AC-14: no chart, tile, simulation or protection component imported by /industry.
const banned = /(TelemetryChart|KpiTile|ScenarioComparison|SensitivityStudy|ProtectionTimeline|ProtectionCoordination|TransientMetricsPanel|SweepChart|simulationApi|InfrastructureMap|PowerFlowSchematic)/;
const importLines = [pageSrc, sheetSrc].join("\n").split("\n").filter((l) => /^\s*import /.test(l)).join("\n");
check("AC-14 import scan", !banned.test(importLines));
check("AC-14 only EvidenceTag component reused", /components\/EvidenceTag/.test(importLines) && (importLines.match(/from "\.\.\/components\//g) ?? []).length === 2);

// AC-16: vocabulary scan outside link labels. Link labels live in `label:` fields and Link text.
const vocab = /\b(scenario|scenarios|run|runs|telemetry|kpi|stress|ride-through)\b/i;
const vocabSrc = words(rendered).replace(/label:\s*"[^"]*"/g, "").replace(/<Link[^>]*>[^<]*<\/Link>/g, "");
const vocabHit = vocab.exec(vocabSrc);
check("AC-16 vocabulary", !vocabHit, vocabHit ? vocabHit[0] : "");

// AC-19: every claim has a locator; spans <= 25 words; supported claims have a span.
for (const s of CLAIM_SHEETS) {
  for (const c of s.claims) {
    // A claim without a span passes only if it is an explicitly recorded exception (the two OCP white-paper
    // claims, whose 2026-10-21 fetch failed); any other missing span fails.
    const exception = s.sourceId === "OCPWP" && c.audit === "paraphrase-checked";
    const ok = c.locator.trim().length > 0 && (!c.span || c.span.split(/\s+/).length <= 25) &&
      (exception || (c.audit === "supported" && !!c.span));
    check(`AC-19 ${s.id}: ${c.text.slice(0, 48)}`, ok);
  }
}

// AC-20: SST disclosures present on the page (imported fixed wording) plus a page-level statement.
check("AC-20 SST not required (page imports DISCLOSURES.sst)", /DISCLOSURES\.sst/.test(pageSrc));
check("AC-20 functional abstraction (page imports DISCLOSURES.block)", /DISCLOSURES\.block/.test(pageSrc));

// AC-21: standards inventory.
const wanted = ["NFPA 70", "IEC 60364", "IEEE 1547", "UL 1741", "IEC 62477-1", "IEEE 493", "IEEE 1584"];
check("AC-21 inventory", BACKGROUND_STANDARDS.map((s) => s.name).sort().join("|") === [...wanted].sort().join("|"));
check("AC-21 sourced or assumption", BACKGROUND_STANDARDS.every((s) => (s.basis === "sourced" ? !!s.locator : s.basis === "assumption")));
check("AC-21 'not opened' rendered", /not opened/.test(pageSrc));
check("R2 status rows are draft/published", SPEC_STATUS_ROWS.length === 2 &&
  SPEC_STATUS_ROWS.find((r) => r.sourceId === "OCPSST")!.status === "draft");

// AC-22: ladder verbatim.
check("AC-22 ladder", CHARTER_LADDER.join("|") ===
  "Equipment / Controls Engineering|Systems Engineering|Senior Systems Engineering|Systems Architecture / Technical Leadership");

// AC-25: home card.
const homeSrc = readFileSync(join(app, "page.tsx"), "utf8");
check("AC-25 home card text", !/tracked over time/i.test(homeSrc) && homeSrc.includes('href: "/industry"') &&
  homeSrc.replace(/"\s*\+\s*\n\s*"/g, "").includes(HOME_CARD.description));
check("R10 nav live", /href: "\/industry", label: "Industry & Career" \}/.test(readFileSync(join(app, "components", "SiteNav.tsx"), "utf8")));

// Questions-to-ask lists on all three sections, and the interaction prompt set.
check("R1 questions lists", Object.values(QUESTIONS_TO_ASK).every((l) => l.length >= 3) && QUESTIONS.length === 6);
check("R20 no diagram/table", !/<(svg|table|canvas)\b/i.test(pageSrc + sheetSrc) && !/<img\b/i.test(pageSrc + sheetSrc));
check("route dir files", readdirSync(industryDir).sort().join() === "ClaimSheet.tsx,page.tsx");

if (process.argv.includes("--audit")) {
  console.log("\n| # | Source | Claim | Locator | Verbatim span | Status |\n|---|---|---|---|---|---|");
  let n = 0;
  for (const s of CLAIM_SHEETS) {
    for (const c of s.claims) {
      n += 1;
      const esc = (t: string) => t.replace(/\|/g, "\\|");
      console.log(`| ${n} | ${s.sourceId} | ${esc(c.text)} | ${esc(c.locator)} | ${c.span ? `"${esc(c.span)}"` : "none for this page"} | ${c.audit} |`);
    }
  }
}

console.log(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
