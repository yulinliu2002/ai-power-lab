"""PI DC-bus voltage controller with load feedforward.

Governing equation
-------------------
    e = V_ref - V_dc
    P_cmd = P_load + Kp * e + Ki * integral(e dt)

where P_load is used directly as the feedforward term (P_ff = P_load),
on the assumption that the controller has an instantaneous, perfect
measurement of load power. This is an idealization (Category B) that
removes most of the steady-state regulation burden from the PI terms,
leaving them to correct transient mismatch and model error.

Units
-----
    e                    : [V]
    P_cmd                : [W]
    Kp                   : [W/V]            (so Kp * e -> W)
    Ki                   : [W/(V*s)]        (so Ki * integral(e dt) -> W,
                                              since integral(e dt) is in V*s)
    integral_error_v_s   : [V*s]            (the controller's internal state)

Anti-windup
-----------
Simple conditional integration: the integral term is only updated when
the unsaturated command is NOT being clipped by the SST power limits.
If the command is saturated, the integrator is frozen for that step.
This is a deliberately simple scheme (vs. back-calculation) chosen for
readability, per the project's "keep V1 simple" direction. The
integrator state is also hard-clamped to [integral_min_v_s,
integral_max_v_s] as a secondary safeguard.

Assumptions
-----------
- Perfect, instantaneous load measurement for feedforward.
- No controller enable/disable or trip-driven integrator reset in
  Phase 1 (no protection state machine yet) -- the controller always
  runs.

Limitations
-----------
- Conditional-integration anti-windup is simpler than back-calculation
  and can be marginally slower to "unwind" after prolonged saturation,
  but is easier to reason about and verify.
- Gains are fixed (no gain scheduling); PI tuning here is illustrative,
  not a rigorously optimized controller.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ControllerState:
    """Mutable PI controller state carried between simulation steps."""

    integral_error_v_s: float = 0.0


def step_voltage_controller(
    state: ControllerState,
    v_dc_v: float,
    p_load_w: float,
    v_ref_v: float,
    kp_w_per_v: float,
    ki_w_per_v_s: float,
    integral_min_v_s: float,
    integral_max_v_s: float,
    p_min_w: float,
    p_max_w: float,
    dt_s: float,
) -> tuple[float, float]:
    """Compute one PI + feedforward control step and update the integrator.

    Args:
        state: controller state; `integral_error_v_s` is updated in place.
        v_dc_v: measured DC bus voltage [V].
        p_load_w: measured (feedforward) load power [W].
        v_ref_v: voltage reference [V].
        kp_w_per_v: proportional gain [W/V].
        ki_w_per_v_s: integral gain [W/(V*s)].
        integral_min_v_s: integrator lower clamp [V*s].
        integral_max_v_s: integrator upper clamp [V*s].
        p_min_w: minimum deliverable SST power, for saturation [W].
        p_max_w: maximum deliverable SST power, for saturation [W].
        dt_s: integration timestep [s].

    Returns:
        (p_cmd_w, p_target_w): unsaturated command and saturated target [W].
    """
    error_v = v_ref_v - v_dc_v

    candidate_integral = state.integral_error_v_s + error_v * dt_s
    candidate_integral = max(integral_min_v_s, min(candidate_integral, integral_max_v_s))

    p_cmd_w = p_load_w + kp_w_per_v * error_v + ki_w_per_v_s * candidate_integral
    p_target_w = max(p_min_w, min(p_cmd_w, p_max_w))

    if p_target_w == p_cmd_w:
        # Not saturated this step: commit the integral update.
        state.integral_error_v_s = candidate_integral
    # else: saturated -> freeze the integrator at its previous value.

    return p_cmd_w, p_target_w
