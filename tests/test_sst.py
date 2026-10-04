"""Tests for the average-value SST power-response model (src/sst.py)."""

from src.sst import compute_sst_losses, step_sst_power


def test_sst_power_converges_to_target_after_many_time_constants():
    tau_s = 0.02
    dt_s = 1e-4
    p_target_w = 300_000.0
    p_sst_w = 0.0

    n_steps = int(10 * tau_s / dt_s)  # ~10 time constants -> should be fully settled
    for _ in range(n_steps):
        p_sst_w = step_sst_power(p_sst_w, p_target_w, tau_s, dt_s)

    assert abs(p_sst_w - p_target_w) < 1e-3 * p_target_w


def test_sst_power_moves_toward_target_each_step():
    tau_s = 0.02
    dt_s = 1e-4
    p_sst_w = 0.0
    p_target_w = 100_000.0

    next_p = step_sst_power(p_sst_w, p_target_w, tau_s, dt_s)
    assert p_sst_w < next_p < p_target_w


def test_sst_losses_positive_for_efficiency_below_one():
    p_sst_w = 100_000.0
    efficiency = 0.97

    p_in_w, p_loss_w = compute_sst_losses(p_sst_w, efficiency)

    assert p_in_w > p_sst_w
    assert p_loss_w > 0.0
    assert abs(p_in_w - (p_sst_w + p_loss_w)) < 1e-9


def test_sst_losses_zero_at_zero_power():
    p_in_w, p_loss_w = compute_sst_losses(0.0, 0.97)
    assert p_in_w == 0.0
    assert p_loss_w == 0.0
