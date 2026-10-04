"""Tests for the PI voltage controller with feedforward (src/controller.py)."""

from src.controller import ControllerState, step_voltage_controller


def _step(state, v_dc_v, p_load_w, **overrides):
    defaults = dict(
        v_ref_v=800.0,
        kp_w_per_v=2000.0,
        ki_w_per_v_s=20000.0,
        integral_min_v_s=-250.0,
        integral_max_v_s=250.0,
        p_min_w=0.0,
        p_max_w=500_000.0,
        dt_s=1e-4,
    )
    defaults.update(overrides)
    return step_voltage_controller(state, v_dc_v, p_load_w, **defaults)


def test_zero_error_and_zero_integral_gives_feedforward_only():
    state = ControllerState()
    p_cmd_w, p_target_w = _step(state, v_dc_v=800.0, p_load_w=150_000.0)
    assert p_cmd_w == 150_000.0
    assert p_target_w == 150_000.0


def test_undervoltage_increases_commanded_power_above_feedforward():
    state = ControllerState()
    p_cmd_w, _ = _step(state, v_dc_v=790.0, p_load_w=150_000.0)
    assert p_cmd_w > 150_000.0


def test_overvoltage_decreases_commanded_power_below_feedforward():
    state = ControllerState()
    p_cmd_w, _ = _step(state, v_dc_v=810.0, p_load_w=150_000.0)
    assert p_cmd_w < 150_000.0


def test_integral_accumulates_under_persistent_error():
    state = ControllerState()
    for _ in range(100):
        _step(state, v_dc_v=790.0, p_load_w=150_000.0)
    assert state.integral_error_v_s > 0.0


def test_integral_is_clamped_to_configured_bounds():
    state = ControllerState()
    # error=100V, dt=1e-4s -> integral grows by 0.01 V*s/step; 10 V*s bound
    # is reached well within 2000 steps.
    for _ in range(2000):
        _step(
            state,
            v_dc_v=700.0,
            p_load_w=150_000.0,
            integral_min_v_s=-10.0,
            integral_max_v_s=10.0,
            p_max_w=1e9,  # avoid saturating P_cmd so the integral keeps winding
        )
    assert state.integral_error_v_s <= 10.0 + 1e-9


def test_command_is_saturated_to_sst_limits():
    state = ControllerState()
    _, p_target_w = _step(state, v_dc_v=500.0, p_load_w=150_000.0, p_max_w=500_000.0)
    assert p_target_w == 500_000.0


def test_integrator_freezes_while_saturated():
    state = ControllerState()
    # Drive the command hard into saturation every step.
    for _ in range(1000):
        _, p_target_w = _step(
            state, v_dc_v=400.0, p_load_w=150_000.0, p_max_w=500_000.0
        )
        assert p_target_w == 500_000.0
    frozen_integral = state.integral_error_v_s

    # One more saturated step should not change the integral at all.
    _step(state, v_dc_v=400.0, p_load_w=150_000.0, p_max_w=500_000.0)
    assert state.integral_error_v_s == frozen_integral
