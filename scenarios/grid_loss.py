"""Scenario E: grid loss (outage) with no recovery.

Demonstrates the grid-unavailable path:

    grid_available -> False -> SST available power -> 0 (via
    src/grid.py:grid_power_availability_factor) -> P_target forced to 0
    by the existing saturation logic (no special-case shutdown needed)
    -> P_sst decays toward 0 per the EXISTING first-order SST dynamics
    -> DC bus discharges per the EXISTING energy balance
    dE_dc/dt = P_sst - P_load (never forced down directly).

Load level: a constant 300 kW demand, started at equilibrium. Grid is
available until t=0.2 s, then lost for the rest of the run.

Duration is deliberately short (0.5 s): given this project's small
illustrative DC-link capacitance, the bus fully discharges to the
NUMERICAL FLOOR (min_energy_j in src/dc_bus.py) within tens of
milliseconds of losing supply. Running longer would only add a long,
flat, physically-meaningless tail at the floor voltage -- so the
simulation is stopped shortly after the collapse is clearly visible,
and the voltage plot additionally shades that region explicitly so it
cannot be misread as a real residual bus voltage.

Run directly to generate plots:
    python -m scenarios.grid_loss
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from scenarios.plotting import floor_voltage, plot_grid_voltage, plot_power, plot_voltage
from src.config import load_config
from src.grid import make_outage_profile
from src.simulation import run_simulation
from src.telemetry import Telemetry, write_telemetry_csv

CONFIG_PATH = "config/default.yaml"
LOAD_W = 300_000.0
OUTAGE_START_S = 0.2
DURATION_S = 0.5
OUTPUT_DIR = Path("results")


def run() -> Telemetry:
    """Run the grid-loss scenario and return its telemetry."""
    config = load_config(CONFIG_PATH)
    config = dataclasses.replace(
        config, simulation=dataclasses.replace(config.simulation, duration_s=DURATION_S)
    )

    def load_fn(t_s: float) -> float:
        return LOAD_W

    grid_fn = make_outage_profile(
        nominal_voltage_pu=config.grid.nominal_voltage_pu,
        outage_start_s=OUTAGE_START_S,
        outage_duration_s=None,  # no recovery within this scenario
    )

    return run_simulation(
        config, load_fn, grid_fn=grid_fn,
        initial_p_sst_w=LOAD_W, initial_integral_error_v_s=0.0,
    )


def plot(telemetry: Telemetry, output_dir: Path = OUTPUT_DIR) -> list[Path]:
    config = load_config(CONFIG_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    events = [(OUTAGE_START_S, "grid lost")]

    return [
        plot_grid_voltage(
            telemetry, output_dir / "grid_loss_grid_voltage.png",
            "Scenario E: Grid Voltage vs Time", events=events,
        ),
        plot_voltage(
            telemetry, output_dir / "grid_loss_vdc.png",
            "Scenario E: DC Bus Voltage vs Time (grid loss)", events=events,
            floor_v=floor_voltage(config),
        ),
        plot_power(
            telemetry, output_dir / "grid_loss_power.png",
            "Scenario E: Load Power vs SST Delivered Power", events=events,
        ),
    ]


if __name__ == "__main__":
    telemetry = run()
    paths = plot(telemetry)
    csv_path = OUTPUT_DIR / "grid_loss_telemetry.csv"
    write_telemetry_csv(telemetry, csv_path)
    paths.append(csv_path)
    for p in paths:
        print(f"Wrote {p}")
