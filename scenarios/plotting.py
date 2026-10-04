"""Shared matplotlib plotting helpers for scenario scripts.

Keeps each scenario script focused on assembling its own load/grid
profile rather than repeating plot boilerplate. No new physics or
analysis lives here -- purely presentation of Telemetry that a
scenario already produced.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from src.config import Config
from src.dc_bus import voltage_from_energy
from src.telemetry import Telemetry

EventMarkers = list[tuple[float, str]]


def _mark_events(ax, events: EventMarkers | None) -> None:
    if not events:
        return
    for t_s, label in events:
        ax.axvline(t_s, color="black", linestyle=":", linewidth=1, label=label)


def floor_voltage(config: Config) -> float:
    """Voltage corresponding to the configured numerical energy floor.

    Pass this to plot_voltage(floor_v=...) so the plot can shade/label
    that region as non-physical rather than a real residual bus voltage.
    """
    return voltage_from_energy(config.dc_bus.min_energy_j, config.dc_bus.capacitance_f)


def plot_voltage(
    telemetry: Telemetry,
    output_path: Path,
    title: str,
    v_ref_v: float = 800.0,
    events: EventMarkers | None = None,
    floor_v: float | None = None,
) -> Path:
    """Plot V_dc vs time.

    If `floor_v` is given (the voltage corresponding to dc_bus.min_energy_j
    -- see src/dc_bus.py), any region where V_dc has been clamped at that
    numerical safety floor is shaded and labeled as non-physical, so a
    reader cannot mistake it for a real residual bus voltage.
    """
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(telemetry.time_s, telemetry.v_dc_v, color="tab:blue", label="V_dc")
    ax.axhline(v_ref_v, color="gray", linestyle="--", linewidth=1, label=f"V_ref = {v_ref_v:.0f} V")
    if floor_v is not None:
        at_floor = telemetry.v_dc_v <= floor_v + 0.5
        if at_floor.any():
            ax.fill_between(
                telemetry.time_s, 0, v_ref_v * 1.1, where=at_floor, color="red", alpha=0.12,
                step="pre", label="numerical floor (non-physical)",
            )
    _mark_events(ax, events)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("DC bus voltage [V]")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_power(
    telemetry: Telemetry,
    output_path: Path,
    title: str,
    events: EventMarkers | None = None,
    include_target: bool = False,
) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(telemetry.time_s, telemetry.p_load_w / 1e3, color="tab:red", label="P_load")
    ax.plot(telemetry.time_s, telemetry.p_sst_w / 1e3, color="tab:green", label="P_sst")
    if include_target:
        ax.plot(
            telemetry.time_s, telemetry.p_target_w / 1e3, color="tab:orange",
            linestyle="--", linewidth=1, label="P_target",
        )
    _mark_events(ax, events)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("power [kW]")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_temperature(
    telemetry: Telemetry,
    output_path: Path,
    title: str,
    derate_start_c: float | None = None,
    trip_c: float | None = None,
    events: EventMarkers | None = None,
) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(telemetry.time_s, telemetry.temperature_c, color="tab:purple", label="T (SST, representative)")
    if derate_start_c is not None:
        ax.axhline(derate_start_c, color="orange", linestyle="--", linewidth=1, label=f"derate start = {derate_start_c:.0f} degC")
    if trip_c is not None:
        ax.axhline(trip_c, color="red", linestyle="--", linewidth=1, label=f"trip = {trip_c:.0f} degC")
    _mark_events(ax, events)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("temperature [degC]")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_protection(
    telemetry: Telemetry,
    output_path: Path,
    title: str,
    events: EventMarkers | None = None,
) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(telemetry.time_s, telemetry.derate_factor, color="tab:brown", label="derate_factor")
    ax.fill_between(
        telemetry.time_s, 0, 1, where=telemetry.trip_active, color="red", alpha=0.15,
        label="TRIPPED", step="pre",
    )
    _mark_events(ax, events)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("derate factor [-]")
    ax.set_ylim(-0.05, 1.05)
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_grid_voltage(
    telemetry: Telemetry,
    output_path: Path,
    title: str,
    events: EventMarkers | None = None,
) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(telemetry.time_s, telemetry.grid_voltage_pu, color="tab:blue", label="grid_voltage_pu")
    ax.fill_between(
        telemetry.time_s, 0, 1.2, where=~telemetry.grid_available, color="red", alpha=0.15,
        label="grid unavailable", step="pre",
    )
    _mark_events(ax, events)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("grid voltage [p.u.]")
    ax.set_ylim(-0.05, 1.2)
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
