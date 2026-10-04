"""Scenario: 40% -> 80% rated-load step on the electrical core.

Demonstrates the Phase 1 electrical chain (Grid-side input assumed
always available; SST average-value model; 800 VDC bus; PI voltage
controller) responding to a step change in AI load:

    1. System initialized AT the 40%-load steady-state operating point
       (V_dc = 800 V, P_sst = P_load(0) = 40% rated, controller
       integral = 0 -- consistent with equilibrium, see
       src/simulation.py:run_simulation). This is a modeling choice,
       not a new physical effect: it only changes the initial
       condition so the plot isolates the load-step transient instead
       of mixing it with an arbitrary cold-start transient.
    2. At t = step_time_s, load steps to 80% of rated power.
    3. Transient response is simulated and plotted.

This module only assembles a scenario (load profile + config) and
calls the physics layer in src/ -- it does not implement any new
physics itself. Scenarios only ever change external inputs (load/grid
profiles, initial conditions); they never reach into internal physics
state.

Run directly to generate plots:
    python -m scenarios.load_step
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from src.config import load_config
from src.load import make_step_load_profile
from src.simulation import run_simulation
from src.telemetry import Telemetry, write_telemetry_csv

CONFIG_PATH = "config/default.yaml"
STEP_TIME_S = 0.2
INITIAL_FRACTION = 0.4
FINAL_FRACTION = 0.8
OUTPUT_DIR = Path("results")


def run() -> Telemetry:
    """Run the load-step scenario and return its telemetry."""
    config = load_config(CONFIG_PATH)
    load_fn = make_step_load_profile(
        rated_power_w=config.load.rated_power_w,
        initial_fraction=INITIAL_FRACTION,
        final_fraction=FINAL_FRACTION,
        step_time_s=STEP_TIME_S,
    )
    initial_p_sst_w = INITIAL_FRACTION * config.load.rated_power_w
    return run_simulation(
        config,
        load_fn,
        initial_p_sst_w=initial_p_sst_w,
        initial_integral_error_v_s=0.0,
    )


def plot(telemetry: Telemetry, output_dir: Path = OUTPUT_DIR) -> list[Path]:
    """Generate the two requested plots and save them as PNGs.

    Returns the list of file paths written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []

    # Plot 1: V_dc vs time
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(telemetry.time_s, telemetry.v_dc_v, label="V_dc", color="tab:blue")
    ax1.axhline(800.0, color="gray", linestyle="--", linewidth=1, label="V_ref = 800 V")
    ax1.axvline(STEP_TIME_S, color="black", linestyle=":", linewidth=1, label="load step")
    ax1.set_xlabel("time [s]")
    ax1.set_ylabel("DC bus voltage [V]")
    ax1.set_title("DC Bus Voltage vs Time (40% -> 80% Load Step)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    fig1.tight_layout()
    path1 = output_dir / "load_step_vdc.png"
    fig1.savefig(path1, dpi=150)
    plt.close(fig1)
    written.append(path1)

    # Plot 2: P_load and P_sst vs time
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.plot(telemetry.time_s, telemetry.p_load_w / 1000.0, label="P_load", color="tab:red")
    ax2.plot(telemetry.time_s, telemetry.p_sst_w / 1000.0, label="P_sst", color="tab:green")
    ax2.axvline(STEP_TIME_S, color="black", linestyle=":", linewidth=1, label="load step")
    ax2.set_xlabel("time [s]")
    ax2.set_ylabel("power [kW]")
    ax2.set_title("Load Power vs SST Delivered Power")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    fig2.tight_layout()
    path2 = output_dir / "load_step_power.png"
    fig2.savefig(path2, dpi=150)
    plt.close(fig2)
    written.append(path2)

    return written


if __name__ == "__main__":
    telemetry = run()
    paths = plot(telemetry)
    csv_path = OUTPUT_DIR / "load_step_telemetry.csv"
    write_telemetry_csv(telemetry, csv_path)
    paths.append(csv_path)
    for p in paths:
        print(f"Wrote {p}")
