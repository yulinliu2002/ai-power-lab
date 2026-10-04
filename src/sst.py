"""Average-value Solid-State Transformer (SST) power-response model.

Governing equation
-------------------
    dP_sst/dt = (P_target - P_sst) / tau_sst

where:
    P_sst    = actual SST output power delivered to the DC bus [W]
    P_target = commanded power after saturation to SST limits [W]
    tau_sst  = SST power response time constant [s]

Convention
----------
P_sst is OUTPUT-referenced: it is the power the SST delivers to the
800 VDC bus, not the power it draws from the grid. Grid-side input
power and losses are derived from P_sst and a constant efficiency:

    P_in   = P_sst / efficiency
    P_loss = P_in - P_sst = P_sst * (1 - efficiency) / efficiency

P_target saturation (to the SST's rated/min power, further reduced by
any active derating or grid-availability limit) is performed by the
caller's controller, not inside this module -- see
src/controller.py:step_voltage_controller.

Assumptions
-----------
- Average-value model: no switching ripple, no individual device
  behavior, no PWM dynamics. Represents only the aggregate, filtered
  power response of the conversion stage.
- Single first-order lag approximates the combined dynamics of the
  SST's internal control loops. This is an engineering modeling
  assumption (Category B), not a physics-derived relationship.
- Efficiency is constant, independent of loading level or temperature.

Limitations
-----------
- Cannot represent switching transients, inrush current, or any
  sub-time-constant electrical behavior.
- Constant efficiency is inaccurate near very light or very heavy
  loading, where real converters typically show higher relative losses.
- Grid availability / voltage dependence is handled by the caller
  (via the P_target saturation limit), not inside this module.
"""

from __future__ import annotations


def step_sst_power(p_sst_w: float, p_target_w: float, tau_sst_s: float, dt_s: float) -> float:
    """Advance SST output power by one explicit-Euler step.

    Implements: P_sst[k+1] = P_sst[k] + dt * (P_target[k] - P_sst[k]) / tau_sst

    Args:
        p_sst_w: current SST output power [W].
        p_target_w: commanded (saturated) power target for this step [W].
        tau_sst_s: SST time constant [s].
        dt_s: integration timestep [s].

    Returns:
        Updated SST output power [W].
    """
    d_p_dt = (p_target_w - p_sst_w) / tau_sst_s
    return p_sst_w + dt_s * d_p_dt


def compute_sst_losses(p_sst_w: float, efficiency: float) -> tuple[float, float]:
    """Compute grid-side input power and losses from delivered output power.

    Args:
        p_sst_w: SST output power delivered to the bus [W].
        efficiency: constant conversion efficiency in (0, 1].

    Returns:
        (p_in_w, p_loss_w): grid-side input power [W] and dissipated
        loss power [W].
    """
    p_in_w = p_sst_w / efficiency
    p_loss_w = p_in_w - p_sst_w
    return p_in_w, p_loss_w
