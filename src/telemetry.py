"""Simulation telemetry: the time-series record produced by a simulation run.

This module defines the Telemetry container and a plain-stdlib CSV
exporter. It holds no physics -- it exists purely so that every
scenario produces one consistent, explicitly-named, explicitly-unitted
record of "what happened and why". No pandas: a stdlib csv.writer is
more than sufficient for flat time-series rows of this size.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np


@dataclass
class Telemetry:
    """Time-series simulation output. All arrays share the same length.

    Field units:
        time_s                  : [s]
        grid_voltage_pu         : [-]
        grid_available          : [bool]
        p_load_w                : [W]
        p_cmd_w                 : [W]   unsaturated controller command
        p_target_w              : [W]   saturated SST power target
        p_sst_w                 : [W]   actual delivered (bus-referenced) SST power
        p_input_w               : [W]   grid-side input power (P_sst / efficiency)
        p_loss_w                : [W]   conversion loss (P_input - P_sst)
        e_dc_j                  : [J]   DC-link stored energy
        v_dc_v                  : [V]   DC bus voltage
        voltage_error_v         : [V]   V_ref - V_dc
        controller_integral_v_s : [V*s] PI controller integrator state
        temperature_c           : [degC] representative SST temperature
        operating_state         : [-]   "RUNNING" | "DERATED" | "TRIPPED"
        derate_factor           : [-]   in [0, 1]
        trip_active             : [bool]
        trip_reason             : [-]   string, "" if no trip
    """

    time_s: np.ndarray
    grid_voltage_pu: np.ndarray
    grid_available: np.ndarray
    p_load_w: np.ndarray
    p_cmd_w: np.ndarray
    p_target_w: np.ndarray
    p_sst_w: np.ndarray
    p_input_w: np.ndarray
    p_loss_w: np.ndarray
    e_dc_j: np.ndarray
    v_dc_v: np.ndarray
    voltage_error_v: np.ndarray
    controller_integral_v_s: np.ndarray
    temperature_c: np.ndarray
    operating_state: np.ndarray
    derate_factor: np.ndarray
    trip_active: np.ndarray
    trip_reason: np.ndarray


def write_telemetry_csv(telemetry: Telemetry, path: str | Path) -> None:
    """Write telemetry to a CSV file, one row per timestep.

    Simple stdlib csv export -- no pandas. Column order matches the
    Telemetry field declaration order.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    field_names = [f.name for f in fields(Telemetry)]
    columns = [getattr(telemetry, name) for name in field_names]
    n_rows = len(columns[0])

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(field_names)
        for i in range(n_rows):
            writer.writerow([column[i] for column in columns])
