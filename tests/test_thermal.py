"""Tests for the lumped SST thermal model (src/thermal.py).

Includes the Phase 2 validation requirement: compare the simulated
long-duration temperature against the analytical steady-state solution
of C_th * dT/dt = P_loss - (T - T_ambient) / R_th.
"""

import math

from src.thermal import step_thermal_temperature, steady_state_temperature

R_TH = 0.01  # degC/W
C_TH = 3000.0  # J/degC
T_AMBIENT = 25.0  # degC
DT_S = 0.01
TAU_TH_S = R_TH * C_TH  # 30 s


def _run_constant_loss(p_loss_w, duration_s, initial_temperature_c=T_AMBIENT):
    temperature_c = initial_temperature_c
    n_steps = int(duration_s / DT_S)
    for _ in range(n_steps):
        temperature_c = step_thermal_temperature(
            temperature_c, p_loss_w, DT_S, C_TH, R_TH, T_AMBIENT
        )
    return temperature_c


def test_zero_loss_at_ambient_stays_at_ambient():
    final_temperature_c = _run_constant_loss(
        p_loss_w=0.0, duration_s=10 * TAU_TH_S, initial_temperature_c=T_AMBIENT
    )
    assert math.isclose(final_temperature_c, T_AMBIENT, abs_tol=1e-6)


def test_positive_loss_causes_heating_above_ambient():
    temperature_c = step_thermal_temperature(
        T_AMBIENT, p_loss_w=5000.0, dt_s=DT_S, thermal_capacitance_j_per_c=C_TH,
        thermal_resistance_c_per_w=R_TH, ambient_temperature_c=T_AMBIENT,
    )
    assert temperature_c > T_AMBIENT


def test_cools_toward_ambient_when_loss_removed():
    hot_temperature_c = 80.0
    temperature_c = hot_temperature_c
    for _ in range(int(5 * TAU_TH_S / DT_S)):
        temperature_c = step_thermal_temperature(
            temperature_c, p_loss_w=0.0, dt_s=DT_S, thermal_capacitance_j_per_c=C_TH,
            thermal_resistance_c_per_w=R_TH, ambient_temperature_c=T_AMBIENT,
        )
    assert temperature_c < hot_temperature_c
    assert math.isclose(temperature_c, T_AMBIENT, abs_tol=0.5)


def test_simulated_steady_state_matches_analytical_formula():
    p_loss_w = 6000.0
    expected_t_ss = steady_state_temperature(p_loss_w, R_TH, T_AMBIENT)

    # Run for many thermal time constants so the transient has fully decayed.
    simulated_t_ss = _run_constant_loss(p_loss_w, duration_s=15 * TAU_TH_S)

    assert math.isclose(simulated_t_ss, expected_t_ss, rel_tol=1e-3)


def test_steady_state_formula_matches_governing_equation_at_equilibrium():
    # At steady state dT/dt = 0, so stepping should not change temperature.
    p_loss_w = 4000.0
    t_ss = steady_state_temperature(p_loss_w, R_TH, T_AMBIENT)
    t_next = step_thermal_temperature(t_ss, p_loss_w, DT_S, C_TH, R_TH, T_AMBIENT)
    assert math.isclose(t_next, t_ss, abs_tol=1e-9)
