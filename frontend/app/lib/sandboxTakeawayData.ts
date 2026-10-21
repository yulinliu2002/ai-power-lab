/**
 * Fixed strings for the Advanced Sandbox's stage copy (SPEC-014 Appendix A,
 * items A5-A12). Each string is approved wording with a stated source in
 * the spec; nothing here is computed and no number appears. Basis classes:
 * M model-calculated, P physical principle, A illustrative assumption; no
 * string makes a claim about real equipment (class R is never used).
 */

/** A5: what the model does not represent. */
export const MODEL_DOES_NOT_REPRESENT =
  "A simplified average-value model: no switching dynamics, no AC power flow, constant efficiency, one lumped DC-bus capacitance, no cabling impedance, and no calibration to any commercial SST.";

/** A6: protection coverage statement (also shown at its source panel). */
export const PROTECTION_COVERAGE_STATEMENT =
  "V1 models sustained thermal overtemperature protection only. It has no DC-bus undervoltage or overvoltage protection.";

/** A14: standing statement for the takeaway stage. */
export const NOT_VALIDATED_STATEMENT =
  "Nothing here is a validated measurement of real equipment. Values are outputs of a simplified model with illustrative parameters.";

/** A9: link text to Architecture Choices, validation step. */
export const VALIDATE_LINK_TEXT =
  "What would have to be shown, and by what kind of evidence, before any real-world conclusion.";

/** A13: outcome caution (also rendered at the outcome banner and comparison table). */
export const OUTCOME_CAUTION =
  "Outcome labels are this simplified model's classification of the run, not certified hardware fault-ride-through performance. The model has no fault ride-through dynamics.";

/** A7: V_dc chart caption. */
export const VDC_CHART_CAPTION =
  "DC bus voltage over time, calculated by the model. The dashed line is the V_ref reference. For Load Step the marker is the lowest V_dc in the run.";

/** A8: power-balance chart caption (the shaded-area sentence applies to Load Step only). */
export const POWER_BALANCE_CAPTION =
  "P_load (dashed) is the scenario's AI demand; P_sst is SST output power calculated by the model. Where demand exceeds SST output, the model takes the difference from the energy stored in the DC bus (dE/dt = P_sst − P_load), until its numerical energy floor is reached; after that the model keeps running but no longer represents physically supplied energy, so values past that point are a numerical limit, not hardware behavior.";
export const POWER_BALANCE_CAPTION_LOAD_STEP =
  "For Load Step, the shaded area is the sampled positive-gap energy from the event to the V_dc minimum (energy, not power). The Engineering Result's energy deficit is the closed-form capacitor-energy change, so the two are defined differently.";

/** A10 and A11: capability-limit notices. */
export const SWEEP_LOAD_STEP_ONLY = "Sensitivity sweeps are available for Load Step only.";
export const FIXED_PRESET_NOTE = "This scenario is a fixed preset; parameters are not adjustable here.";

/** A12: state markers. */
export const STALE_RUN_MARKER = "Values changed since this run.";
export const UNRUN_VALUES_MARKER = "Slider values not yet run.";
