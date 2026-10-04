"""Configuration loading for the AI Power Lab digital twin.

This module is the one I/O boundary where engineering parameters cross
from a YAML file into typed, unit-explicit Python objects. No unit
conversion happens here in Phase 1 -- the YAML file is already in SI
units -- but this is where such conversions would live if a future
config ever used non-SI units for operator convenience.

Governing relationships: none (this is a data-loading module).
Assumptions: the YAML file is well-formed and contains all required
keys; no partial/default-merging is implemented in V1.
Limitations: minimal validation (presence and basic numeric sanity
checks only). Not a schema-validation framework by design -- see
CLAUDE.md "no frameworks just in case".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SimulationConfig:
    timestep_s: float
    duration_s: float


@dataclass(frozen=True)
class SstConfig:
    rated_power_w: float
    min_power_w: float
    efficiency: float
    time_constant_s: float


@dataclass(frozen=True)
class DcBusConfig:
    nominal_voltage_v: float
    capacitance_f: float
    initial_voltage_v: float
    min_energy_j: float


@dataclass(frozen=True)
class ControllerConfig:
    voltage_reference_v: float
    kp_w_per_v: float
    ki_w_per_v_s: float
    integral_min_v_s: float
    integral_max_v_s: float


@dataclass(frozen=True)
class LoadConfig:
    rated_power_w: float


@dataclass(frozen=True)
class ThermalConfig:
    ambient_temperature_c: float
    initial_temperature_c: float
    thermal_resistance_c_per_w: float
    thermal_capacitance_j_per_c: float


@dataclass(frozen=True)
class ProtectionConfig:
    thermal_derate_start_c: float
    thermal_trip_c: float
    thermal_trip_time_s: float
    derate_factor_min: float


@dataclass(frozen=True)
class GridConfig:
    nominal_voltage_pu: float


@dataclass(frozen=True)
class Config:
    simulation: SimulationConfig
    sst: SstConfig
    dc_bus: DcBusConfig
    controller: ControllerConfig
    load: LoadConfig
    thermal: ThermalConfig
    protection: ProtectionConfig
    grid: GridConfig


def load_config(path: str | Path) -> Config:
    """Load and validate a simulation configuration from a YAML file.

    Args:
        path: path to a YAML config file (e.g. config/default.yaml).

    Returns:
        A populated, validated Config.

    Raises:
        ValueError: if a required key is missing or a value fails a
            basic physical sanity check (e.g. negative time constant).
    """
    with open(path) as f:
        raw = yaml.safe_load(f)

    sim = SimulationConfig(**raw["simulation"])
    sst = SstConfig(**raw["sst"])
    dc_bus = DcBusConfig(**raw["dc_bus"])
    controller = ControllerConfig(**raw["controller"])
    load = LoadConfig(**raw["load"])
    thermal = ThermalConfig(**raw["thermal"])
    protection = ProtectionConfig(**raw["protection"])
    grid = GridConfig(**raw["grid"])

    _validate(sim, sst, dc_bus, controller, load, thermal, protection, grid)

    return Config(
        simulation=sim,
        sst=sst,
        dc_bus=dc_bus,
        controller=controller,
        load=load,
        thermal=thermal,
        protection=protection,
        grid=grid,
    )


def _validate(
    sim: SimulationConfig,
    sst: SstConfig,
    dc_bus: DcBusConfig,
    controller: ControllerConfig,
    load: LoadConfig,
    thermal: ThermalConfig,
    protection: ProtectionConfig,
    grid: GridConfig,
) -> None:
    if sim.timestep_s <= 0:
        raise ValueError("simulation.timestep_s must be positive")
    if sim.duration_s <= 0:
        raise ValueError("simulation.duration_s must be positive")
    if sst.time_constant_s <= 0:
        raise ValueError("sst.time_constant_s must be positive")
    if not (0.0 < sst.efficiency <= 1.0):
        raise ValueError("sst.efficiency must be in (0, 1]")
    if sst.min_power_w > sst.rated_power_w:
        raise ValueError("sst.min_power_w must not exceed sst.rated_power_w")
    if dc_bus.capacitance_f <= 0:
        raise ValueError("dc_bus.capacitance_f must be positive")
    if dc_bus.initial_voltage_v <= 0:
        raise ValueError("dc_bus.initial_voltage_v must be positive")
    if dc_bus.min_energy_j <= 0:
        raise ValueError("dc_bus.min_energy_j must be positive")
    if controller.integral_min_v_s >= controller.integral_max_v_s:
        raise ValueError(
            "controller.integral_min_v_s must be less than integral_max_v_s"
        )
    if load.rated_power_w <= 0:
        raise ValueError("load.rated_power_w must be positive")
    if thermal.thermal_resistance_c_per_w <= 0:
        raise ValueError("thermal.thermal_resistance_c_per_w must be positive")
    if thermal.thermal_capacitance_j_per_c <= 0:
        raise ValueError("thermal.thermal_capacitance_j_per_c must be positive")
    if protection.thermal_derate_start_c >= protection.thermal_trip_c:
        raise ValueError(
            "protection.thermal_derate_start_c must be less than thermal_trip_c"
        )
    if protection.thermal_trip_time_s < 0:
        raise ValueError("protection.thermal_trip_time_s must be non-negative")
    if not (0.0 <= protection.derate_factor_min <= 1.0):
        raise ValueError("protection.derate_factor_min must be in [0, 1]")
    if grid.nominal_voltage_pu <= 0:
        raise ValueError("grid.nominal_voltage_pu must be positive")
