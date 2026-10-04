"""Lumped single-node thermal model for a representative SST temperature.

Governing equation
-------------------
    C_th * dT/dt = P_loss - (T - T_ambient) / R_th

where:
    T          = representative SST temperature [degC]
    T_ambient  = ambient temperature [degC]
    C_th       = thermal capacitance [J/degC]
    R_th       = thermal resistance [degC/W]
    P_loss     = conversion loss power entering the thermal node [W]
                 (see src/sst.py:compute_sst_losses for P_loss = P_in - P_sst)

Steady state (dT/dt = 0):
    T_ss = T_ambient + R_th * P_loss

Purpose and scope
------------------
T is a single, generic aggregate SST thermal state -- NOT a junction,
case, or heatsink temperature of any real device. Its only job is to
demonstrate the coupling between electrical loading, conversion loss,
and a protection-relevant thermal state. See CLAUDE.md / architecture
review for why a single-node model is an intentional simplification.

Assumptions
-----------
- Single lumped thermal mass: no distinction between junction, case,
  heatsink, or coolant -- one time constant for the whole SST.
- Linear heat loss to ambient (a resistive/Newtonian cooling term),
  independent of airflow, coolant flow rate, or temperature itself.
- P_loss is the only heat source; no other loss mechanisms (e.g.
  auxiliary power supplies, cabling) are modeled.

Limitations
-----------
- Cannot represent spatial temperature gradients or multi-time-constant
  thermal behavior (e.g. a fast junction response riding on a slow
  heatsink response).
- Not suitable for predicting real device survival margins -- it is a
  coupling demonstration only (electrical loading -> loss -> heat ->
  protection); see README Limitations.
"""

from __future__ import annotations


def step_thermal_temperature(
    temperature_c: float,
    p_loss_w: float,
    dt_s: float,
    thermal_capacitance_j_per_c: float,
    thermal_resistance_c_per_w: float,
    ambient_temperature_c: float,
) -> float:
    """Advance the lumped SST temperature by one explicit-Euler step.

    Implements:
        T[k+1] = T[k] + dt * (P_loss - (T[k] - T_ambient) / R_th) / C_th

    Args:
        temperature_c: current representative SST temperature [degC].
        p_loss_w: conversion loss power for this step [W].
        dt_s: integration timestep [s].
        thermal_capacitance_j_per_c: C_th [J/degC].
        thermal_resistance_c_per_w: R_th [degC/W].
        ambient_temperature_c: T_ambient [degC].

    Returns:
        Updated temperature [degC].
    """
    d_t_dt = (
        p_loss_w - (temperature_c - ambient_temperature_c) / thermal_resistance_c_per_w
    ) / thermal_capacitance_j_per_c
    return temperature_c + dt_s * d_t_dt


def steady_state_temperature(
    p_loss_w: float,
    thermal_resistance_c_per_w: float,
    ambient_temperature_c: float,
) -> float:
    """Analytical steady-state temperature for a constant loss power.

    Implements: T_ss = T_ambient + R_th * P_loss (from dT/dt = 0).

    Used to validate the simulated thermal model against the governing
    equation's closed-form steady-state solution; see
    tests/test_thermal.py.
    """
    return ambient_temperature_c + thermal_resistance_c_per_w * p_loss_w
