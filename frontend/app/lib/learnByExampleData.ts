/**
 * Content model for Learn by Example (SPEC-012 v0.2 + R19).
 *
 * Authored, static prose only. Every model number the learner sees comes
 * from the live API response at runtime, never from this file (R6), so no
 * digit appears in any string below except the allowlisted forms: driver
 * ids (rd2 shown as RD2), citation identifiers in `basis`, and text inside
 * `equation` (rendered in a `data-equation` node, stripped by the AC-4 scan).
 *
 * `claims` are hypotheses UNDER TEST: the verification script evaluates
 * them against the live responses (R16). They are never rendered as values.
 */

import type {
  BoundaryId,
  DriverId,
  Evidence,
  EvidenceKind,
  ReferenceId,
} from "./architectureChoicesData";
import type { ScenarioName } from "./simulationApi";

export type Item = { text: string } & Evidence;

export interface ExplainStep {
  text: string;
  /** Relation from SPEC-012 §5.2, shown in a data-equation node. */
  equation?: string;
}

export type NotModeledItem = {
  name: string;
  text: string;
} & Evidence;

export interface ValidationReasoning {
  verifies: string;
  kinds: readonly [EvidenceKind, ...EvidenceKind[]];
}

/** R16 claim kinds, evaluated by the verification script. */
export type Claim =
  | { kind: "outcome"; value: "RIDE_THROUGH" | "PROTECTION_TRIP" | "BUS_COLLAPSE_UNPROTECTED" }
  | { kind: "recovery"; value: "RECOVERED" | "NOT_RECOVERED" | "NOT_APPLICABLE" }
  | { kind: "dominantStress"; value: string }
  | { kind: "statesReached"; value: readonly string[] }
  | { kind: "voltageFalls"; value: boolean }
  | { kind: "voltageRecovers"; value: boolean }
  | { kind: "reachesFloor"; value: boolean }
  | { kind: "order"; value: "busCollapseBeforeTrip" }
  // Predicate kinds added during SPEC-012 implementation (R16 clarification, flagged for approval):
  | { kind: "voltageStaysInBand"; value: boolean }
  | { kind: "noSustainedDeficit"; value: boolean }
  | { kind: "temperatureRises"; value: boolean }
  | { kind: "temperatureRiseSlows"; value: boolean }
  | { kind: "tripAfterDebounce"; value: boolean }
  | { kind: "deliveryExceedsDemandAfterEvent"; value: boolean }
  | { kind: "deliveryShortfallDuringSag"; value: boolean }
  | { kind: "deliveryDecays"; value: boolean }
  | { kind: "deliveryShortfallAfterEvent"; value: boolean }
  | { kind: "targetAboveDemandWhileBelowRef"; value: boolean }
  | { kind: "endsInState"; value: string }
  | { kind: "derateBelowDemand"; value: boolean }
  | { kind: "deliveryShortfallPersists"; value: boolean }
  | { kind: "floorBeforeSagEnds"; value: boolean }
  | { kind: "targetGoesToZero"; value: boolean }
  | { kind: "gridStaysUnavailable"; value: boolean };

export interface Case {
  id: ScenarioName;
  title: string;
  /** Show D-L2 (numerical-floor disclosure) prominently on this case. */
  busCollapseCase: boolean;
  situation: Item;
  drivers: readonly DriverId[];
  predict: { question: string; reveal: string } & Evidence;
  explain: {
    steps: readonly [ExplainStep, ExplainStep, ExplainStep, ...ExplainStep[]];
    limitingQuantity: string;
  } & Evidence;
  limits: readonly [Item, ...Item[]];
  notModeled: readonly NotModeledItem[];
  decision: { drivers: readonly DriverId[]; boundary: BoundaryId; text: string } & Evidence;
  validation: readonly [ValidationReasoning, ValidationReasoning, ...ValidationReasoning[]];
  claims: readonly Claim[];
}

/** Page-level disclosures (SPEC-012 §6.5). DISCLOSURES.sim/.block/.illustrative come from SPEC-011. */
export const LEARN_DISCLOSURES = {
  d1: "These cases run the five fixed Sandbox scenarios on a simplified average-value model. Results show how the model behaves under stated illustrative assumptions, not how real equipment behaves.",
  d2: "In the grid-sag, grid-loss and thermal-trip cases, 'bus collapse' means the integrator reached its numerical energy floor. It is not a physically meaningful residual voltage.",
  d3: "Real-world fault behavior listed under 'not modeled' is described from public sources or general engineering principle. It is not simulated here, and no result on this page validates it.",
} as const;

const MODEL_ASSUMPTION = (file: string): Evidence => ({
  evidence: "assumption",
  basis: `Model assumption stated in ${file} (this repository); an illustrative modeling choice, not data.`,
});

const AUTHORED = (why: string): Evidence => ({
  evidence: "assumption",
  basis: why,
});

const SST_SPEC: ReferenceId = "OCPSST";
const WHITE_PAPER: ReferenceId = "OCPWP";

/** Items shared by several cases (same wording, same evidence). */
const BLOCK_ITEM: NotModeledItem = {
  name: "Internal structure of a real SST",
  text: "A real solid-state transformer is built from several functional parts, and the public specification lists power conversion, input, output, control and auxiliary power as separate components. This engine treats the whole SST as one averaged block.",
  evidence: "public-fact",
  basis: "OCP SST specification §4.1 (product components; a black-box definition that gives no stage count).",
  refs: [SST_SPEC],
};

const STORAGE_ITEM: NotModeledItem = {
  name: "Energy storage and backup",
  text: "In the public specification an SST coupled with energy storage could function as a medium-voltage UPS, so real designs place stored energy beside the conversion stage. This engine has no storage element: the only buffer is the DC-link capacitance.",
  evidence: "emerging",
  basis: "OCP SST specification §3 (scope; SST coupled with energy storage as an MV-UPS). The sentence about this engine is a repository fact.",
  refs: [SST_SPEC],
};

const FAULT_CURRENT_ITEM: NotModeledItem = {
  name: "Fault current from a converter-fed DC system",
  text: "Three things are different in a real system and none is modeled here: the upstream short-circuit withstand of the SST, the controlled current the SST may deliver into a downstream fault before it is allowed to trip, and the discharge of DC capacitance into a fault. The first is a rating in a draft specification, the second is a recommended setting in that draft, and the third is the part the white paper says has no recognized coordination practice yet.",
  evidence: "emerging",
  basis: "OCP SST specification §4.2 (upstream withstand, duration TBD) and §4.3 (recommended fault-coordination setting; a draft recommendation, not a requirement or measured result); OCP white paper §7.2.4 (capacitor-discharge peak).",
  refs: [SST_SPEC, WHITE_PAPER],
};

const ARC_ITEM: NotModeledItem = {
  name: "Interrupting a DC fault",
  text: "Conventional fuses and breakers interrupt DC by creating an arc voltage larger than the system voltage, and newer semiconductor-based devices work differently. This engine represents no fault, arc or interruption device.",
  evidence: "emerging",
  basis: "OCP white paper §7.2.4 (overcurrent protection devices for DC).",
  refs: [WHITE_PAPER],
};

const COORDINATION_ITEM: NotModeledItem = {
  name: "Selective protection coordination across stages",
  text: "The white paper says there is currently no standard or recognized practice for coordinating protection for the converter-fed DC fault behavior it describes, in particular the capacitor-discharge peak, and separately that migration to solid-state solutions may need a new approach to coordination studies. This engine has one protection function, thermal, and no coordination logic.",
  evidence: "emerging",
  basis: "OCP white paper §7.2.4 (no recognized coordination practice for the described converter-fed DC faults) and §4.2 (new approach to coordination studies; cited separately).",
  refs: [WHITE_PAPER],
};

const GROUNDING_ITEM: NotModeledItem = {
  name: "Grounding and insulation monitoring",
  text: "The draft SST specification calls for an ungrounded or high-resistance-grounded DC side with detection and protection coordination, with the detailed design still to be defined. This engine has no grounding or insulation model.",
  evidence: "emerging",
  basis: "OCP SST specification §4.3 (DC grounding: IT ground, floating or high-resistance, detailed design TBD).",
  refs: [SST_SPEC],
};

const RESET_ITEM: NotModeledItem = {
  name: "Trip reset and restart",
  text: "This model has no reset or restart logic: once the trip latches it stays latched for the rest of the run. That is a statement about the model only; it says nothing about how real equipment restarts.",
  evidence: "assumption",
  basis: "Model fact from the repository's protection coverage list (automatic trip reset: not modeled). Real restart behavior is deliberately not described because no opened source supports a claim.",
};

export const CASES: Record<ScenarioName, Case> = {
  load_step: {
    id: "load_step",
    title: "AI load step",
    busCollapseCase: false,
    drivers: ["rd2"],
    situation: {
      text: "The AI load suddenly asks for more power while the chain is in a steady state. The converter cannot deliver the new demand instantly, so something else has to cover the gap. The question is what the DC bus does in the meantime and what brings it back.",
      ...MODEL_ASSUMPTION("the Sandbox's fixed load-step preset"),
    },
    predict: {
      question: "Before looking at the chart: after the load steps up, does the bus voltage rise, fall, or stay put, and what finally restores it?",
      reveal: "Expect the voltage to fall first, because demand exceeds delivered power until the converter catches up, and then to return toward its reference once the controller has pushed delivered power above demand long enough to refill the bus energy.",
      ...AUTHORED("Authored expectation; checked against the live response by the verification script."),
    },
    explain: {
      limitingQuantity:
        "The energy the DC link can give up before the converter catches up, set by the link capacitance, the converter's response time and the controller.",
      steps: [
        {
          text: "The load demand rises at once, but the converter's delivered power follows its target only with a first-order lag set by the converter time constant.",
          equation: "P_sst follows P_target with time constant tau_sst",
        },
        {
          text: "While delivery is below demand, the DC link supplies the difference, so the stored energy falls and the bus voltage falls with it.",
          equation: "dE_dc/dt = P_sst − P_load,  E_dc = ½ C_dc V_dc²",
        },
        {
          text: "The PI voltage controller sees the voltage below its reference and raises the power target above the demand.",
          equation: "kp [W/V], ki [W/(V·s)]",
        },
        {
          text: "Delivered power rises above demand, the surplus refills the stored energy, and the voltage returns toward its reference.",
        },
      ],
      ...AUTHORED("Cause chain from relations already in the repository (src/dc_bus.py, src/sst.py, src/controller.py); reviewed, not scripted."),
    },
    limits: [
      { text: "The SST is an averaged power-lag block: no switching, no internal stages, no input-side behavior.", ...MODEL_ASSUMPTION("src/sst.py") },
      { text: "The link capacitance is an illustrative value, not derived from any specification.", ...MODEL_ASSUMPTION("config/default.yaml (dc_bus.capacitance_f)") },
      { text: "There is no storage, UPS or backup element, and nothing models effects on the grid side of a fast demand change.", ...MODEL_ASSUMPTION("src/dc_bus.py and src/grid.py") },
    ],
    notModeled: [STORAGE_ITEM, BLOCK_ITEM],
    decision: {
      drivers: ["rd2"],
      boundary: "storage-backup",
      text: "This case informs where to place stored energy relative to the conversion stage and how fast that stage must respond to the load. It shows the mechanism in one simplified chain and does not compare architectures.",
      ...AUTHORED("Authored link to the Architecture Choices driver on load dynamics; no verdict or ranking."),
    },
    validation: [
      { verifies: "Measured bus voltage excursion and recovery for the actual load profile with the specified storage and converter.", kinds: ["factory test", "site test"] },
      { verifies: "Converter and controller response under the real control design, not an averaged model.", kinds: ["simulation", "factory test"] },
      { verifies: "Effect of fast load swings at the grid interface.", kinds: ["analysis", "site test"] },
    ],
    claims: [
      { kind: "voltageFalls", value: true },
      { kind: "voltageRecovers", value: true },
      { kind: "deliveryShortfallAfterEvent", value: true },
      { kind: "targetAboveDemandWhileBelowRef", value: true },
      { kind: "deliveryExceedsDemandAfterEvent", value: true },
      { kind: "outcome", value: "RIDE_THROUGH" },
    ],
  },

  sustained_high_load: {
    id: "sustained_high_load",
    title: "Sustained high load",
    busCollapseCase: false,
    drivers: ["rd5", "rd6"],
    situation: {
      text: "The load holds a steady, high demand that stays within what the converter can supply even when it is derated. Nothing electrical goes wrong, but conversion loss turns into heat and the heat has to go somewhere.",
      ...MODEL_ASSUMPTION("the Sandbox's fixed sustained-load preset"),
    },
    predict: {
      question: "Before looking: with demand held steady, does the converter temperature rise, and does the bus voltage ever leave its reference?",
      reveal: "Expect the temperature to rise slowly toward a steady value, a mild derating to engage, and the bus voltage to stay at its reference throughout because the derated converter can still meet demand.",
      ...AUTHORED("Authored expectation; checked against the live response by the verification script."),
    },
    explain: {
      limitingQuantity:
        "Heat accumulation against the thermal path to ambient, whose slow time constant is the product of thermal resistance and thermal capacitance.",
      steps: [
        {
          text: "A converter that is not perfectly efficient turns part of the power it passes into heat.",
          equation: "P_loss = P_sst·(1−η)/η, η constant",
        },
        {
          text: "The heat raises the temperature of one lumped thermal node toward a steady value, slowly, on a time scale far longer than the electrical dynamics.",
          equation: "C_th dT/dt = P_loss − (T − T_amb)/R_th",
        },
        {
          text: "Above the derating start temperature the model reduces available power linearly. Because demand stays below even the fully derated limit, delivery still meets demand and the bus voltage stays at its reference.",
        },
        {
          text: "The system settles into a stable derated operating point: a thermal effect with no electrical consequence in this case.",
        },
      ],
      ...AUTHORED("Cause chain from relations already in the repository (src/sst.py, src/thermal.py, src/protection.py); reviewed, not scripted."),
    },
    limits: [
      { text: "Efficiency is a constant that does not depend on load level or temperature; the loss itself still grows with the power delivered.", ...MODEL_ASSUMPTION("src/sst.py") },
      { text: "Heat is a single lumped node; there is no cooling system, coolant flow or multi-node thermal behavior.", ...MODEL_ASSUMPTION("src/thermal.py") },
      { text: "The linear derating curve is an illustrative choice, not any real product's curve.", ...MODEL_ASSUMPTION("src/protection.py") },
    ],
    notModeled: [
      {
        name: "Load- and temperature-dependent efficiency, cooling dynamics",
        text: "Real converters change efficiency with load and temperature, and real cooling systems have their own dynamics and limits. None of that is in this engine.",
        evidence: "assumption",
        basis: "Repository Learn content lists these as ignored by the model (content/learn, what_ignored). A statement about the model; no external source is claimed.",
      },
      BLOCK_ITEM,
    ],
    decision: {
      drivers: ["rd5", "rd6"],
      boundary: "conversion-distribution",
      text: "This case informs how much thermal margin and cooling to plan around a sustained load, which feeds the choice of where conversion happens. It does not compare architectures.",
      ...AUTHORED("Authored link to the Architecture Choices drivers on conversion losses and physical footprint; no verdict or ranking."),
    },
    validation: [
      { verifies: "Temperature rise and derating of the real converter at the real sustained load.", kinds: ["factory test"] },
      { verifies: "Cooling system response and limits under sustained loading.", kinds: ["analysis", "site test"] },
      { verifies: "The real derating curve against the specification.", kinds: ["factory test", "conformance review"] },
    ],
    claims: [
      { kind: "voltageFalls", value: false },
      { kind: "voltageStaysInBand", value: true },
      { kind: "temperatureRises", value: true },
      { kind: "temperatureRiseSlows", value: true },
      { kind: "noSustainedDeficit", value: true },
      { kind: "statesReached", value: ["RUNNING", "DERATED"] },
      { kind: "endsInState", value: "DERATED" },
      { kind: "outcome", value: "RIDE_THROUGH" },
      { kind: "recovery", value: "RECOVERED" },
    ],
  },

  thermal_trip: {
    id: "thermal_trip",
    title: "Thermal trip",
    busCollapseCase: true,
    drivers: ["rd4", "rd3"],
    situation: {
      text: "The load demands more than a derated converter can supply. Heat builds up, the allowed power shrinks, and at some point supply can no longer meet demand. The question is which happens first: the electrical collapse or the protective trip.",
      ...MODEL_ASSUMPTION("the Sandbox's fixed thermal-trip preset"),
    },
    predict: {
      question: "Before looking: does the thermal protection trip before the bus voltage collapses, or after?",
      reveal: "Expect the bus to reach the model's numerical floor before the trip latches. Thermal protection acts on a slow thermal time scale, while the electrical bus runs out of energy on a much faster one.",
      ...AUTHORED("Authored expectation; checked against the live response by the verification script."),
    },
    explain: {
      limitingQuantity:
        "The derated available power against the demand, and the thermal protection's response time against the electrical collapse time.",
      steps: [
        {
          text: "Sustained high demand produces conversion loss, and the loss accumulates heat in the lumped thermal node.",
          equation: "C_th dT/dt = P_loss − (T − T_amb)/R_th",
        },
        {
          text: "Above the derating start temperature the available power shrinks. Because demand exceeds even the fully derated limit, the converter eventually cannot meet it.",
        },
        {
          text: "Once delivery persistently falls short of demand, the DC link drains through the energy balance within a time that is tiny compared with the thermal time scale.",
          equation: "dE_dc/dt = P_sst − P_load",
        },
        {
          text: "The trip latches only after the temperature stays above the trip threshold for the debounce time. In this model the electrical collapse reaches its numerical floor before that happens, so thermal protection is too slow to prevent it.",
        },
      ],
      ...AUTHORED("Cause chain from relations already in the repository (src/thermal.py, src/protection.py, src/dc_bus.py); reviewed, not scripted."),
    },
    limits: [
      { text: "Protection is thermal only: there is no bus-voltage or grid protection, and the latched trip has no reset.", ...MODEL_ASSUMPTION("src/protection.py") },
      { text: "After the collapse the voltage shown is the integrator's numerical floor, not a physical voltage, and energy is not conserved at the floor because the load is an ideal sink that keeps drawing its commanded power.", ...MODEL_ASSUMPTION("src/load.py and src/dc_bus.py") },
      { text: "The derating curve and thresholds are illustrative choices.", ...MODEL_ASSUMPTION("config/default.yaml (protection)") },
    ],
    notModeled: [FAULT_CURRENT_ITEM, ARC_ITEM, GROUNDING_ITEM, COORDINATION_ITEM, RESET_ITEM, BLOCK_ITEM],
    decision: {
      drivers: ["rd4", "rd3"],
      boundary: "conversion-distribution",
      text: "This case informs whether protection must act faster than a thermal function can, and what would need validating about fast protection and coordination. It is a lesson about response times in one simplified chain, not a comparison of architectures.",
      ...AUTHORED("Authored link to the Architecture Choices drivers on protection and availability; no verdict or ranking."),
    },
    validation: [
      { verifies: "Protection coordination and clearing times for the real converter and distribution, including fast electrical protection beyond thermal.", kinds: ["analysis", "factory test"] },
      { verifies: "Derated capability against the real demand profile at rated conditions.", kinds: ["factory test"] },
      { verifies: "Presence and timing of bus undervoltage protection in the real design.", kinds: ["simulation", "site test"] },
    ],
    claims: [
      { kind: "outcome", value: "BUS_COLLAPSE_UNPROTECTED" },
      { kind: "recovery", value: "NOT_RECOVERED" },
      { kind: "dominantStress", value: "DC_BUS_VIABILITY_LOSS" },
      { kind: "statesReached", value: ["RUNNING", "DERATED", "TRIPPED"] },
      { kind: "reachesFloor", value: true },
      { kind: "order", value: "busCollapseBeforeTrip" },
      { kind: "tripAfterDebounce", value: true },
      { kind: "temperatureRises", value: true },
      { kind: "derateBelowDemand", value: true },
      { kind: "deliveryShortfallPersists", value: true },
    ],
  },

  grid_sag: {
    id: "grid_sag",
    title: "Grid sag",
    busCollapseCase: true,
    drivers: ["rd2", "rd7"],
    situation: {
      text: "The grid voltage dips for a short time and then returns. During the dip the converter can supply less power than the load demands. The question is how long the DC link can cover the gap.",
      ...MODEL_ASSUMPTION("the Sandbox's fixed grid-sag preset"),
    },
    predict: {
      question: "Before looking: does the bus ride through the dip, and is a run that ends back at its reference really a ride-through?",
      reveal: "Expect the bus to run out of stored energy during the dip and touch the model's numerical floor, then recover when the grid returns. That recovery is a model classification, not a physical ride-through, because the load is an ideal sink and the floor does not conserve energy.",
      ...AUTHORED("Authored expectation; checked against the live response by the verification script."),
    },
    explain: {
      limitingQuantity:
        "The power the converter can supply during the dip against the demand, with only the link capacitance as a buffer.",
      steps: [
        {
          text: "The grid voltage dips, and the model scales the converter's available power in proportion to it. This is a modeling assumption, not a real converter's ride-through behavior.",
          equation: "available power ∝ grid voltage (per unit)",
        },
        {
          text: "Available power falls below demand, so delivery cannot match the load and the DC link supplies the difference.",
          equation: "dE_dc/dt = P_sst − P_load",
        },
        {
          text: "The stored energy is small, so in this preset the bus reaches the numerical floor before the dip ends.",
        },
        {
          text: "When the grid returns, available power returns, and the energy balance lets the bus refill. The final state looks recovered, but the run passed through the numerical floor, so it must not be read as a clean ride-through.",
        },
      ],
      ...AUTHORED("Cause chain from relations already in the repository (src/grid.py, src/dc_bus.py); reviewed, not scripted."),
    },
    limits: [
      { text: "Available power is scaled in proportion to grid voltage. That is an illustrative assumption, not a ride-through curve, and there is no input-current limiting.", ...MODEL_ASSUMPTION("src/grid.py") },
      { text: "The sag depth and duration are illustrative presets. They are not derived from, tested against, or compliant with any published ride-through standard.", ...MODEL_ASSUMPTION("scenarios/grid_sag.py (preset)") },
      { text: "The load is an ideal power sink that draws its commanded power at any bus voltage, and the energy floor is a numerical clamp, so energy is not conserved at the floor and the later 'recovered' classification has no physical meaning as a real recovery.", ...MODEL_ASSUMPTION("src/load.py and src/dc_bus.py") },
    ],
    notModeled: [
      {
        name: "How real converters ride through a voltage dip",
        text: "The draft specification describes ride-through for an SST together with energy storage: in one voltage range the SST limits its input current while supplying the load, and in a deeper range the coupled energy storage supplies the load. It notes there is no unified standard for the design criteria. This engine uses the proportional-availability assumption instead and has no storage.",
        evidence: "emerging",
        basis: "OCP SST specification §5.1.2 (voltage ride-through for SST and energy storage operating together; no unified standard).",
        refs: [SST_SPEC],
      },
      FAULT_CURRENT_ITEM,
      COORDINATION_ITEM,
      BLOCK_ITEM,
    ],
    decision: {
      drivers: ["rd2", "rd7"],
      boundary: "mv-utility",
      text: "This case informs what a conversion stage must do when the grid dips and how much stored energy or input-current limiting that implies. It shows the mechanism in one simplified chain and does not compare architectures.",
      ...AUTHORED("Authored link to the Architecture Choices drivers on load dynamics and standards; no verdict or ranking."),
    },
    validation: [
      { verifies: "Ride-through of the real converter and storage against the applicable grid-code voltage-dip requirements.", kinds: ["factory test", "conformance review"] },
      { verifies: "Energy storage sizing for the required dip duration at the real demand.", kinds: ["analysis", "simulation"] },
      { verifies: "Grid-side behavior during and after the dip.", kinds: ["site test"] },
    ],
    claims: [
      { kind: "outcome", value: "BUS_COLLAPSE_UNPROTECTED" },
      { kind: "recovery", value: "RECOVERED" },
      { kind: "dominantStress", value: "DC_BUS_VIABILITY_LOSS" },
      { kind: "reachesFloor", value: true },
      { kind: "voltageRecovers", value: true },
      { kind: "deliveryShortfallDuringSag", value: true },
      { kind: "floorBeforeSagEnds", value: true },
    ],
  },

  grid_loss: {
    id: "grid_loss",
    title: "Grid loss",
    busCollapseCase: true,
    drivers: ["rd3"],
    situation: {
      text: "The grid supply is lost completely and does not come back. With no source and no storage in the chain, the question is how quickly the DC link runs out of energy.",
      ...MODEL_ASSUMPTION("the Sandbox's fixed grid-loss preset"),
    },
    predict: {
      question: "Before looking: how long can the DC link carry the load once the supply is gone, and does the system recover?",
      reveal: "Expect the stored energy to be exhausted almost at once on the electrical time scale, the bus to reach the model's numerical floor, and no recovery, because nothing restores the supply.",
      ...AUTHORED("Authored expectation; checked against the live response by the verification script."),
    },
    explain: {
      limitingQuantity:
        "The energy stored in the DC-link capacitance against the load's demand, with no other energy source.",
      steps: [
        {
          text: "The grid becomes unavailable, so the converter's available power drops to nothing and its target is forced to zero by the existing saturation logic.",
        },
        {
          text: "Delivered power decays toward zero along the converter's first-order response, so it cannot cover the load.",
          equation: "P_sst decays with time constant tau_sst",
        },
        {
          text: "The DC link supplies the load from its stored energy until that energy is gone.",
          equation: "dE_dc/dt = P_sst − P_load,  E_dc = ½ C_dc V_dc²",
        },
        {
          text: "The stored energy is small, so the bus reaches the numerical floor very quickly. Nothing restores the supply, so the run does not recover.",
        },
      ],
      ...AUTHORED("Cause chain from relations already in the repository (src/grid.py, src/sst.py, src/dc_bus.py); reviewed, not scripted."),
    },
    limits: [
      { text: "There is no storage, battery, UPS or generator element, so the link capacitance is the only energy buffer.", ...MODEL_ASSUMPTION("src/dc_bus.py") },
      { text: "The load is an ideal power sink and the energy floor is a numerical clamp, so energy is not conserved at the floor and the shape after it is not physical.", ...MODEL_ASSUMPTION("src/load.py and src/dc_bus.py") },
      { text: "The run does not recover because the supply never returns within it; the model also has no restart logic.", ...MODEL_ASSUMPTION("scenarios/grid_loss.py (preset) and src/protection.py") },
    ],
    notModeled: [STORAGE_ITEM, RESET_ITEM, BLOCK_ITEM],
    decision: {
      drivers: ["rd3"],
      boundary: "storage-backup",
      text: "This case informs what must carry the load through a supply loss and for how long, which is the availability question behind storage and backup. It does not compare architectures.",
      ...AUTHORED("Authored link to the Architecture Choices driver on availability; no verdict or ranking."),
    },
    validation: [
      { verifies: "Backup energy and transfer behavior for the required outage duration.", kinds: ["analysis", "site test"] },
      { verifies: "Behavior of the real converter and storage on loss of supply and on restoration.", kinds: ["factory test", "site test"] },
    ],
    claims: [
      { kind: "outcome", value: "BUS_COLLAPSE_UNPROTECTED" },
      { kind: "recovery", value: "NOT_RECOVERED" },
      { kind: "dominantStress", value: "DC_BUS_VIABILITY_LOSS" },
      { kind: "statesReached", value: ["RUNNING"] },
      { kind: "reachesFloor", value: true },
      { kind: "deliveryDecays", value: true },
      { kind: "targetGoesToZero", value: true },
      { kind: "gridStaysUnavailable", value: true },
    ],
  },
};

export const CASE_ORDER: readonly ScenarioName[] = [
  "load_step",
  "sustained_high_load",
  "thermal_trip",
  "grid_sag",
  "grid_loss",
];
