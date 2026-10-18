/**
 * Content model for the System Map's expanded infrastructure diagram
 * (AI Power Lab 2.0 Phase 1C). This is reference/educational material,
 * not simulation input -- no governing equations, no units, no engine
 * coupling. It is kept as data (not JSX) so the diagram component stays
 * a thin renderer and the prose can be reviewed/edited on its own.
 *
 * Source basis: public data-center engineering concepts (UPS topologies,
 * switchgear/ATS practice, DCIM/BMS, liquid cooling) and public industry
 * commentary on 800 VDC distribution (NVIDIA, the Open Compute Project).
 * Where a claim is a simplification for teaching purposes rather than a
 * universal fact, the prose says so explicitly -- see each architecture's
 * `caveat` and the category `alternatives` fields.
 */

export type CategoryId =
  | "grid"
  | "substation"
  | "mv_switchgear"
  | "power_conversion"
  | "backup_generation"
  | "distribution"
  | "rack_power"
  | "compute"
  | "cooling"
  | "monitoring";

export interface CategoryInfo {
  id: CategoryId;
  /** The ten infrastructure categories from the task brief, in the
   * canonical order they're introduced -- used for the legend. */
  title: string;
  what: string;
  why: string;
  considerations: readonly string[];
  alternatives: readonly string[];
}

export const CATEGORIES: Record<CategoryId, CategoryInfo> = {
  grid: {
    id: "grid",
    title: "Utility Grid & Power Sourcing",
    what:
      "The facility's connection to the utility transmission or sub-transmission grid -- usually " +
      "a dedicated feeder negotiated directly with the utility, carrying power at a high voltage " +
      "(commonly tens to hundreds of kV) down to the site boundary.",
    why:
      "Grid power is almost always the lowest-cost, highest-availability energy source available, " +
      "and a data center's continuous, large, predictable load makes it an attractive utility " +
      "customer for a dedicated interconnection.",
    considerations: [
      "Interconnection capacity and utility queue time are often the binding constraint on how fast a new campus can be energized, not construction speed.",
      "Large campuses increasingly negotiate for multiple independent feeds, or sit near transmission substations, to reduce single-point grid risk.",
      "Power-purchase agreements (PPAs) for renewable generation offset the facility's accounted-for carbon intensity, but the physical electrons delivered still come from the local grid mix.",
    ],
    alternatives: [
      "On-site generation (gas turbines, fuel cells) as a primary rather than backup source, used by some newer high-density campuses facing interconnection delays.",
      "Dual-utility or dual-substation feeds for N+1 grid redundancy at the site level.",
    ],
  },
  substation: {
    id: "substation",
    title: "Substation & Voltage Transformation",
    what:
      "A step-down transformer stage that converts transmission/sub-transmission voltage down to a " +
      "medium-voltage (MV) level suitable for on-site distribution (commonly in the 13.8 kV or " +
      "34.5 kV class), using a conventional line-frequency transformer.",
    why:
      "Transmitting power at high voltage keeps resistive losses low over distance; stepping down " +
      "to MV makes on-site switchgear, cabling, and protection practical and safer to operate.",
    considerations: [
      "Utility-owned vs. customer-owned substations shift who is responsible for maintenance, metering, and outage response.",
      "Dual-transformer substation configurations (each sized to carry the full load) are common for N+1 redundancy at this stage.",
    ],
    alternatives: [
      "A single large substation serving an entire campus vs. several smaller substations per building/power block.",
    ],
  },
  mv_switchgear: {
    id: "mv_switchgear",
    title: "Medium-Voltage Distribution & Switchgear",
    what:
      "Circuit breakers, protection relays, and metering that receive MV power from the substation " +
      "and split it into multiple feeders, each protected and switchable independently, typically " +
      "one feeder per power block or data hall.",
    why:
      "A fault or maintenance need on one feeder must not take down the whole facility; switchgear " +
      "is the layer that isolates faults and lets one section be de-energized, verified, and worked " +
      "on safely while other sections may remain in service, depending on the installation's bus " +
      "arrangement and switching scheme.",
    considerations: [
      "Breaker coordination (which protection device trips first for a given fault) has to be engineered deliberately, or a local fault can cascade into an unnecessarily large outage.",
      "This is also the point where backup generators are typically paralleled back onto the facility's power path via an automatic or manual transfer scheme.",
      "Working on any section still requires proper isolation, de-energization, verification, and lockout/tagout procedures -- a bus arrangement that lets other sections stay energized during that work does not change what is required for the section actually being worked on.",
    ],
    alternatives: [
      "Single bus vs. dual/ring bus switchgear arrangements, trading cost against the ability to keep one section energized and in service while another section is isolated and worked on.",
    ],
  },
  power_conversion: {
    id: "power_conversion",
    title: "Power Conversion, UPS & Energy Storage",
    what:
      "The stage that conditions facility power and bridges the short gap between a utility loss " +
      "event and backup generation coming online -- historically a double-conversion UPS, where " +
      "incoming AC is rectified to an internal DC link, then inverted back to AC for the load, " +
      "with a battery (or flywheel) connected to that internal DC link rather than to the AC input " +
      "or output directly; in 800 VDC architectures, a centralized AC/DC conversion stage produces " +
      "a DC bus that the battery connects to directly, without a separate AC-output UPS stage.",
    why:
      "Generators take seconds to start and synchronize; a momentary grid loss without local energy " +
      "storage would still crash every downstream server before the generator could pick up the load.",
    considerations: [
      "Ride-through time is a sizing choice -- typically on the order of minutes, enough to cover generator start/transfer, not sustained outages.",
      "Battery chemistry (VRLA vs. lithium-ion) and flywheel-based UPS trade upfront cost, footprint, and maintenance against response time and lifespan.",
      "A double-conversion UPS converts AC-DC-AC continuously for the main load path, whether or not the battery is actively charging or discharging; 800 VDC designs are motivated in part by stopping that chain at the DC bus instead of re-inverting to AC for distribution, but the total number of conversion stages from grid to rack still depends on the specific architecture upstream of the DC bus, not on this stage alone.",
    ],
    alternatives: [
      "Distributed UPS (one small unit per rack or row) vs. centralized UPS (one large plant per power block).",
      "Flywheel energy storage instead of batteries, trading ride-through duration for faster response and no chemical degradation.",
    ],
  },
  backup_generation: {
    id: "backup_generation",
    title: "Backup Generation & Redundancy",
    what:
      "On-site diesel (or increasingly natural gas) generators with an automatic transfer switch " +
      "(ATS), sized to assume the full critical load if the utility feed is lost for an extended " +
      "period, with on-site fuel storage for a contracted runtime.",
    why:
      "UPS energy storage only bridges seconds to minutes; generators are what allow the facility " +
      "to keep running through an outage that lasts hours.",
    considerations: [
      "Redundancy is usually described as N+1 (one spare unit beyond what's needed) or 2N (a fully duplicated second system), which drives both cost and physical footprint.",
      "Generators are conventionally AC synchronous machines and typically connect into the facility's AC-side power path upstream of any DC conversion stage; the exact integration point varies by architecture and site design and should not be read as one universal rule across all facilities.",
      "Routine load-bank testing is required to verify generators will actually start and carry load under a real event, not just at idle.",
    ],
    alternatives: [
      "Grid-independent microgrids combining generation with on-site storage for facilities pursuing higher sustainability targets.",
      "Fuel cells as a lower-emission alternative to diesel in some newer deployments.",
    ],
  },
  distribution: {
    id: "distribution",
    title: "AC and DC Distribution",
    what:
      "The wiring/busway layer that carries conditioned power from the UPS or central conversion " +
      "stage out to each row and rack -- conventionally AC busway or panel-fed PDUs at utilization " +
      "voltage (e.g., 415/480 V), or, in an 800 VDC architecture, a DC busway at 800 V.",
    why:
      "This is the layer that actually reaches every rack; its voltage and topology choice is what " +
      "determines how much conversion still has to happen downstream, at the rack.",
    considerations: [
      "DC distribution removes the need for downstream equipment to handle AC's voltage/frequency/phase characteristics, but it introduces its own protection challenges -- DC fault currents don't naturally go to zero the way AC does every half-cycle, so DC breakers and fuses are a distinct (and less mature) discipline.",
      "800 VDC does not imply any component downstream operates at 800 V end-to-end -- see Rack-Level Power Conversion.",
    ],
    alternatives: [
      "Lower-voltage DC distribution standards (e.g., 48 VDC) used in some telecom and smaller IT deployments, trading distribution efficiency for simpler, more mature low-voltage DC hardware.",
    ],
  },
  rack_power: {
    id: "rack_power",
    title: "Rack-Level Power Conversion",
    what:
      "The conversion stage inside (or directly feeding) each rack that steps the distribution " +
      "voltage down to the DC rails servers actually consume -- rack power supply units (PSUs) " +
      "converting AC to roughly 12 V or 48 V internal rails, or, in a DC-bus architecture, rack- or " +
      "shelf-level DC-DC converters stepping 800 V down to a similar 48 V/12 V rail.",
    why:
      "Every path above this point is about getting bulk power to the rack efficiently; this is the " +
      "stage that finally produces the low, high-current DC rails servers' own point-of-load " +
      "regulators can work with.",
    considerations: [
      "GPUs and other accelerator ASICs run their compute cores at roughly 1 V, supplied by board-level voltage regulator modules (VRMs) even further downstream -- 800 VDC (or 48 V) never reaches the silicon directly.",
      "High-density AI racks have pushed rack-level power conversion toward higher efficiency and power density, since every watt lost here becomes heat that the cooling system then has to remove.",
    ],
    alternatives: [
      "Centralized rack-level DC-DC conversion (one shared converter shelf per rack) vs. per-server PSUs.",
      "48 V intermediate rail vs. other intermediate voltages, trading current (and conductor losses) at the final, highest-current conversion step.",
    ],
  },
  compute: {
    id: "compute",
    title: "AI Servers & Compute Loads",
    what:
      "The GPU/accelerator servers themselves -- today's highest-density AI racks can draw on the " +
      "order of tens to over a hundred kW per rack, well above a traditional enterprise server rack.",
    why:
      "This is the load every upstream stage exists to serve, and its behavior is unusual: training " +
      "and inference workloads can swing power demand very fast and very hard, which is a major " +
      "driver of the protection and power-quality challenges elsewhere in the chain.",
    considerations: [
      "Fast, large load transients (not just steady-state power draw) are what stress upstream voltage regulation and energy-storage sizing.",
      "Rack power density is a primary driver of the cooling technology choice (air vs. liquid) discussed below.",
    ],
    alternatives: [
      "Air-cooled vs. liquid-cooled compute nodes at a given density, discussed under Cooling.",
    ],
  },
  cooling: {
    id: "cooling",
    title: "Cooling & Heat-Rejection Infrastructure",
    what:
      "The thermal path that removes the heat the compute load converts electrical power into -- " +
      "air cooling (CRAC/CRAH units plus chillers or cooling towers) historically, and increasingly " +
      "liquid cooling (direct-to-chip cold plates or rear-door heat exchangers, fed by a coolant " +
      "distribution unit, or CDU) for high-density AI racks.",
    why:
      "Essentially all the electrical power this map traces ends up as heat at the compute load; if " +
      "that heat isn't removed at the same rate it's generated, components throttle or fault on " +
      "over-temperature protection.",
    considerations: [
      "Cooling is a connected but physically separate infrastructure system from the electrical power path -- it's driven by rack heat density, not by whether the electrical architecture is AC or 800 VDC.",
      "A CDU interfaces the facility's water loop to a closed rack-level coolant loop, so facility water chemistry/contamination never reaches the electronics directly.",
      "Air-side economizers and other free-cooling techniques reduce chiller run-time in favorable climates.",
    ],
    alternatives: [
      "Immersion cooling (submerging boards directly in a dielectric fluid) as a less common alternative to cold-plate liquid cooling.",
      "Hybrid air/liquid designs where only the highest-power components (GPUs) are liquid-cooled and the rest of the rack stays air-cooled.",
    ],
  },
  monitoring: {
    id: "monitoring",
    title: "Monitoring, Controls & System Integration",
    what:
      "The supervisory layer that ties the electrical and mechanical systems together -- a building " +
      "management system (BMS) for mechanical/electrical plant control, an electrical power " +
      "monitoring system (EPMS) for breaker/meter telemetry, and data-center infrastructure " +
      "management (DCIM) software correlating IT and facility data.",
    why:
      "No single piece of equipment in this map can be operated safely in isolation -- protection " +
      "coordination, generator start sequencing, and cooling setpoints all depend on real-time " +
      "visibility across stages that this layer provides.",
    considerations: [
      "This layer overlays every other category in this map rather than sitting at one point in the power path -- it's drawn separately here rather than wired into the diagram to avoid implying it's just another electrical stage.",
      "Integration between electrical (EPMS), mechanical (BMS), and IT-facing (DCIM) systems is often cited as an operational weak point, since they're frequently sourced from different vendors.",
    ],
    alternatives: [
      "Vendor-unified DCIM suites vs. best-of-breed point tools integrated via an open protocol (e.g., BACnet, Modbus) or API layer.",
    ],
  },
} as const;

export type ArchitectureId = "conventional-ac" | "ac-to-800vdc" | "mv-to-800vdc";

export type Lane = "main" | "backup" | "cooling" | "monitoring";

export interface ArchitectureNode {
  id: string;
  categoryId: CategoryId;
  lane: Lane;
  /** Short label shown on the node button. */
  label: string;
  /** One-line technology/voltage descriptor shown under the label. */
  detail: string;
  /** 1-2 sentences specific to how *this* architecture instantiates the category. */
  instantiation: string;
}

export interface Architecture {
  id: ArchitectureId;
  name: string;
  tagline: string;
  summary: string;
  /** Explicit "this is a simplification" statement shown with the architecture. */
  caveat: string;
  nodes: readonly ArchitectureNode[];
}

export const ARCHITECTURES: readonly Architecture[] = [
  {
    id: "conventional-ac",
    name: "Conventional AC",
    tagline: "AC end to end, with battery storage on the UPS's internal DC link",
    summary:
      "Power stays in AC form from the utility down to the rack, with a double-conversion UPS and " +
      "battery (or flywheel) plant providing ride-through. This is the traditional enterprise/" +
      "hyperscale data-center pattern, predating the recent push toward DC distribution for " +
      "high-density AI racks.",
    caveat:
      "Shown here as one representative, simplified pattern -- real conventional facilities vary " +
      "widely in redundancy level (N+1 vs. 2N), UPS topology, and distribution voltage.",
    nodes: [
      {
        id: "a-grid",
        categoryId: "grid",
        lane: "main",
        label: "Utility Grid",
        detail: "MV/transmission feed",
        instantiation:
          "A dedicated utility feeder delivers AC power to the site boundary; everything downstream stays AC.",
      },
      {
        id: "a-substation",
        categoryId: "substation",
        lane: "main",
        label: "Substation",
        detail: "Step-down transformer",
        instantiation:
          "A conventional line-frequency transformer steps the incoming voltage down to a medium-voltage (MV) distribution level on-site.",
      },
      {
        id: "a-switchgear",
        categoryId: "mv_switchgear",
        lane: "main",
        label: "MV Switchgear",
        detail: "Breakers, protection, metering",
        instantiation:
          "MV switchgear splits power into protected feeders per power block, and is the point where backup generators are paralleled in.",
      },
      {
        id: "a-conversion",
        categoryId: "power_conversion",
        lane: "main",
        label: "UPS + Battery Plant",
        detail: "Double-conversion AC UPS",
        instantiation:
          "A unit substation transformer first steps MV down to utilization voltage; a double-conversion UPS with battery (or flywheel) strings then conditions and rides through short outages, entirely in AC form on either side of the UPS's internal DC bus.",
      },
      {
        id: "a-distribution",
        categoryId: "distribution",
        lane: "main",
        label: "AC Distribution",
        detail: "415/480 V busway & PDUs",
        instantiation:
          "Conditioned AC power is distributed via busway or panel-fed PDUs to each row at utilization voltage.",
      },
      {
        id: "a-rack",
        categoryId: "rack_power",
        lane: "main",
        label: "Rack PSUs",
        detail: "AC → 12 V/48 V DC",
        instantiation:
          "Each server's AC-DC power supply converts rack-delivered AC down to the internal DC rails the board uses.",
      },
      {
        id: "a-compute",
        categoryId: "compute",
        lane: "main",
        label: "AI Servers",
        detail: "GPU/accelerator racks",
        instantiation: "The compute load the entire chain above exists to serve.",
      },
      {
        id: "a-backup",
        categoryId: "backup_generation",
        lane: "backup",
        label: "Diesel Generators + ATS",
        detail: "Connects at MV switchgear",
        instantiation:
          "Sized to assume the full critical load within the UPS's ride-through window if the utility feed is lost.",
      },
      {
        id: "a-cooling-rack",
        categoryId: "cooling",
        lane: "cooling",
        label: "Rack Cooling",
        detail: "CRAC/CRAH air cooling",
        instantiation:
          "Air handlers at the row or room level remove heat from the rack; typical of lower-to-moderate rack power density.",
      },
      {
        id: "a-cooling-rejection",
        categoryId: "cooling",
        lane: "cooling",
        label: "Heat Rejection",
        detail: "Chillers / cooling towers",
        instantiation: "Chiller plants and cooling towers reject the collected heat to the outside air.",
      },
      {
        id: "a-monitoring",
        categoryId: "monitoring",
        lane: "monitoring",
        label: "BMS / EPMS / DCIM",
        detail: "Overlays every stage above",
        instantiation:
          "Monitors and coordinates the electrical, generator, and cooling systems above as one system.",
      },
    ],
  },
  {
    id: "ac-to-800vdc",
    name: "AC-fed 800 VDC",
    tagline: "Conventional AC up to a centralized conversion stage, then DC to the rack",
    summary:
      "The grid-facing infrastructure (substation, MV switchgear, backup generation) stays " +
      "conventional AC, but a centralized conversion stage then produces an 800 VDC bus that carries " +
      "power the rest of the way to the rack, with energy storage tied directly to that DC bus.",
    caveat:
      "A conceptual, illustrative midpoint between the conventional and fully-DC patterns -- public " +
      "sources (e.g., NVIDIA, the Open Compute Project) describe this general direction, not a single " +
      "standardized design.",
    nodes: [
      {
        id: "b-grid",
        categoryId: "grid",
        lane: "main",
        label: "Utility Grid",
        detail: "MV/transmission feed",
        instantiation: "Same AC grid interconnection as the conventional pattern.",
      },
      {
        id: "b-substation",
        categoryId: "substation",
        lane: "main",
        label: "Substation",
        detail: "Step-down transformer",
        instantiation: "A conventional transformer still steps incoming voltage down to MV on-site.",
      },
      {
        id: "b-switchgear",
        categoryId: "mv_switchgear",
        lane: "main",
        label: "MV Switchgear",
        detail: "Breakers, protection, metering",
        instantiation: "Protects and splits MV feeders; still the point where backup generators tie in on the AC side.",
      },
      {
        id: "b-conversion",
        categoryId: "power_conversion",
        lane: "main",
        label: "Centralized AC-DC Conversion",
        detail: "Rectifier stage → 800 VDC bus",
        instantiation:
          "A centralized conversion stage (a conventional rectifier/transformer combination, or a solid-state transformer -- see the MV-to-800VDC view) produces an 800 VDC bus. Battery energy storage ties directly onto this bus rather than through a separate AC-output UPS stage, and because downstream distribution stays DC instead of being re-inverted to AC, the path from this DC bus to the rack avoids an additional DC-AC conversion stage that the conventional pattern's AC distribution requires. This does not mean the full grid-to-rack path necessarily has fewer conversion stages overall -- that also depends on what happens upstream of this stage.",
      },
      {
        id: "b-distribution",
        categoryId: "distribution",
        lane: "main",
        label: "800 VDC Distribution",
        detail: "DC busway",
        instantiation: "DC busway carries 800 VDC to each row, rather than AC at utilization voltage.",
      },
      {
        id: "b-rack",
        categoryId: "rack_power",
        lane: "main",
        label: "Rack DC-DC Conversion",
        detail: "800 V → 48 V/12 V",
        instantiation:
          "Rack- or shelf-level DC-DC converters step 800 V down to the same ~48 V/12 V internal rail a conventional rack PSU would produce -- GPUs still don't see 800 V directly.",
      },
      {
        id: "b-compute",
        categoryId: "compute",
        lane: "main",
        label: "AI Servers",
        detail: "GPU/accelerator racks",
        instantiation: "The compute load this architecture is typically motivated by.",
      },
      {
        id: "b-backup",
        categoryId: "backup_generation",
        lane: "backup",
        label: "Diesel Generators + ATS",
        detail: "Connects at MV switchgear (AC side)",
        instantiation:
          "Generators remain AC machines, so backup still ties in upstream of the DC conversion stage, regardless of the DC bus downstream.",
      },
      {
        id: "b-cooling-rack",
        categoryId: "cooling",
        lane: "cooling",
        label: "Rack Cooling",
        detail: "Direct-to-chip liquid cooling",
        instantiation:
          "Often paired with liquid cooling, since this architecture is typically adopted alongside higher-density AI racks -- density, not the DC bus itself, is the main driver.",
      },
      {
        id: "b-cooling-rejection",
        categoryId: "cooling",
        lane: "cooling",
        label: "Heat Rejection",
        detail: "CDU + chillers",
        instantiation: "A coolant distribution unit (CDU) bridges the rack loop to the facility water loop and chiller plant.",
      },
      {
        id: "b-monitoring",
        categoryId: "monitoring",
        lane: "monitoring",
        label: "BMS / EPMS / DCIM",
        detail: "Overlays every stage above",
        instantiation: "Coordinates the AC-side plant and the new DC conversion/distribution stages as one system.",
      },
    ],
  },
  {
    id: "mv-to-800vdc",
    name: "Conceptual MV-to-800 VDC via SST",
    tagline: "A solid-state transformer merges voltage step-down and AC-DC conversion into one stage",
    summary:
      "A solid-state transformer (SST) performs medium-voltage AC-to-800VDC conversion directly, " +
      "conceptually folding the separate substation transformer and centralized rectifier stages of " +
      "the previous view into one solid-state stage, with energy storage on the resulting DC bus.",
    caveat:
      "Conceptual and educational, matching this project's simulated chain (see the simplified model " +
      "further down this page). SST is one possible technology for this stage, not a required " +
      "component of 800 VDC distribution in general -- the previous view reaches the same 800 VDC bus " +
      "without one. This view folds the on-site substation transformer and centralized rectifier " +
      "stages into the SST; it does not eliminate the utility's own upstream transmission- or " +
      "sub-transmission-level transformation, which still happens before an MV feed reaches any site, " +
      "SST-based or not.",
    nodes: [
      {
        id: "c-grid",
        categoryId: "grid",
        lane: "main",
        label: "Utility Grid",
        detail: "MV feed",
        instantiation: "Same AC grid interconnection, typically already at or near MV for this pattern.",
      },
      {
        id: "c-switchgear",
        categoryId: "mv_switchgear",
        lane: "main",
        label: "MV Switchgear",
        detail: "Breakers, protection, metering",
        instantiation:
          "Still needed upstream of the SST for protection, isolation, and metering -- the SST does not remove the need for MV-side switchgear.",
      },
      {
        id: "c-sst",
        categoryId: "power_conversion",
        lane: "main",
        label: "Solid-State Transformer",
        detail: "MV AC → 800 VDC, one stage",
        instantiation:
          "The SST is presented here as one functional system-level block -- conceptually combining the separate substation transformer and rectifier stages shown in the other two views -- using active semiconductor switching and a medium-frequency transformer. Internally it comprises multiple cascaded conversion stages (e.g., input AC-DC rectification, a medium-frequency isolation stage, output regulation to the DC bus), which this project does not model individually. Energy storage attaches to the resulting 800 VDC bus. This project's simplified simulation models the whole stage as a single average-value block, not its internal stages.",
      },
      {
        id: "c-distribution",
        categoryId: "distribution",
        lane: "main",
        label: "800 VDC Distribution",
        detail: "DC busway",
        instantiation: "Identical DC busway role to the previous view -- the difference is only in how the 800 VDC was produced.",
      },
      {
        id: "c-rack",
        categoryId: "rack_power",
        lane: "main",
        label: "Rack DC-DC Conversion",
        detail: "800 V → 48 V/12 V",
        instantiation: "Same downstream rack-level DC-DC conversion as the previous view -- GPUs still run at roughly 1 V, several conversion steps away from 800 V.",
      },
      {
        id: "c-compute",
        categoryId: "compute",
        lane: "main",
        label: "AI Servers",
        detail: "GPU/accelerator racks",
        instantiation: "The compute load this project's Advanced Sandbox simulates as a dynamic lumped load.",
      },
      {
        id: "c-backup",
        categoryId: "backup_generation",
        lane: "backup",
        label: "Diesel Generators + ATS",
        detail: "Connects at MV switchgear (AC side)",
        instantiation: "Still an AC-side connection upstream of the SST, for the same reason as the other two views.",
      },
      {
        id: "c-cooling-rack",
        categoryId: "cooling",
        lane: "cooling",
        label: "Rack Cooling",
        detail: "Direct-to-chip liquid cooling",
        instantiation: "Same cooling role as the AC-to-800VDC view -- cooling technology tracks rack density, not this stage's internal design.",
      },
      {
        id: "c-cooling-rejection",
        categoryId: "cooling",
        lane: "cooling",
        label: "Heat Rejection",
        detail: "CDU + chillers",
        instantiation: "Same facility-side heat rejection role as the other two views.",
      },
      {
        id: "c-monitoring",
        categoryId: "monitoring",
        lane: "monitoring",
        label: "BMS / EPMS / DCIM",
        detail: "Overlays every stage above",
        instantiation: "Coordinates the SST, DC distribution, and cooling systems as one system.",
      },
    ],
  },
] as const;

/**
 * `accentClass` is deliberately the same neutral hairline for every
 * lane (DESIGN.md §9/"Engineering Visual Semantics"): these four
 * lanes are a categorization, not a health state, so none of them
 * borrows a status color (accent/warning/good) the way an earlier
 * version of this map did -- that collided with the one rule that a
 * color always means something real about engineering state. Lanes
 * are told apart by their label text, not by which status color they
 * happen to look like.
 */
export const LANE_META: Record<Lane, { label: string; description: string; accentClass: string }> = {
  main: {
    label: "Main Power Path",
    description: "The electrical series path from the grid to the compute load.",
    accentClass: "border-l-hairline",
  },
  backup: {
    label: "Backup & Redundancy",
    description: "Not in the main series path -- connects into the AC side when the grid is unavailable.",
    accentClass: "border-l-hairline",
  },
  cooling: {
    label: "Cooling & Heat Rejection",
    description: "A separate thermal path, not an electrical one -- removes the heat the compute load produces.",
    accentClass: "border-l-hairline",
  },
  monitoring: {
    label: "Monitoring & Controls",
    description: "Overlays every layer above rather than sitting at one point in the power path.",
    accentClass: "border-l-hairline",
  },
};
