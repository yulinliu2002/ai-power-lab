"""Scenario B: sustained high load -> thermal response (no trip).

Demonstrates the electrical-to-thermal coupling introduced in Phase 2:

    constant high SST loading -> conversion loss -> gradual temperature
    rise -> (mild) derating -- all WITHOUT a power deficit or a trip.

Load level: a constant 200 kW demand (40% of the SST's rated_power_w,
50% of the AI load's own rated_power_w). This is chosen specifically to
stay BELOW rated_power_w * derate_factor_min (250 kW): even once fully
derated, the SST could still supply this demand, so the system settles
into a stable DERATED operating point with the load fully met --
contrast with scenarios/thermal_trip.py (Scenario C), where the demand
exceeds that floor and the SST cannot keep up once derated.

The system starts AT this operating point in equilibrium (V_dc = 800 V,
P_sst = P_load = 200 kW), matching Scenarios A and C, so the voltage
plot shows a clean, flat baseline with no electrical startup transient
to distract from the thermal story this scenario is actually about.

This scenario intentionally runs far longer than Scenario A (hundreds
of seconds, not fractions of a second) because the thermal time
constant (R_th * C_th = 30 s) is ~1000x slower than the electrical one.
A coarser timestep (1 ms vs Phase 1's 0.1 ms) is used to keep the long
run fast; 1 ms is still >>10x smaller than tau_sst (20 ms), so the
fast electrical dynamics remain numerically stable. A 10 ms step was
tested directly and found NOT safe here -- it destabilizes the closed-
loop PI+SST+bus interaction into a sustained limit cycle regardless of
thermal behavior (see README "Key Design Decisions" #5 and
tests/test_thermal_protection_simulation.py).

Run directly to generate plots:
    python -m scenarios.sustained_high_load
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from scenarios.plotting import plot_power, plot_protection, plot_temperature, plot_voltage
from src.config import load_config
from src.simulation import run_simulation
from src.telemetry import Telemetry, write_telemetry_csv

CONFIG_PATH = "config/default.yaml"
SUSTAINED_LOAD_W = 200_000.0
DURATION_S = 200.0
TIMESTEP_S = 0.001
OUTPUT_DIR = Path("results")


def run() -> Telemetry:
    """Run the sustained-high-load scenario and return its telemetry."""
    config = load_config(CONFIG_PATH)
    config = dataclasses.replace(
        config,
        simulation=dataclasses.replace(
            config.simulation, timestep_s=TIMESTEP_S, duration_s=DURATION_S
        ),
    )

    def load_fn(t_s: float) -> float:
        return SUSTAINED_LOAD_W

    return run_simulation(
        config, load_fn,
        initial_p_sst_w=SUSTAINED_LOAD_W, initial_integral_error_v_s=0.0,
    )


def plot(telemetry: Telemetry, output_dir: Path = OUTPUT_DIR) -> list[Path]:
    config = load_config(CONFIG_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = [
        plot_voltage(
            telemetry, output_dir / "sustained_high_load_vdc.png",
            "Scenario B: DC Bus Voltage vs Time (sustained 200 kW load)",
        ),
        plot_power(
            telemetry, output_dir / "sustained_high_load_power.png",
            "Scenario B: Load Power vs SST Delivered Power",
        ),
        plot_temperature(
            telemetry, output_dir / "sustained_high_load_temperature.png",
            "Scenario B: SST Temperature vs Time",
            derate_start_c=config.protection.thermal_derate_start_c,
            trip_c=config.protection.thermal_trip_c,
        ),
        plot_protection(
            telemetry, output_dir / "sustained_high_load_derate.png",
            "Scenario B: Derate Factor vs Time",
        ),
    ]
    return paths


if __name__ == "__main__":
    telemetry = run()
    paths = plot(telemetry)
    csv_path = OUTPUT_DIR / "sustained_high_load_telemetry.csv"
    write_telemetry_csv(telemetry, csv_path)
    paths.append(csv_path)
    for p in paths:
        print(f"Wrote {p}")
