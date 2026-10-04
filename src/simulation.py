"""Full V1 simulation loop: electrical core + thermal + protection + grid.

Update order per step (causality notes)
----------------------------------------
At step k, V_dc, E_dc, P_sst, T, and the controller/protection state all
hold the values that were in effect during [t_{k-1}, t_k) (or the
initial condition, for k = 0). Each step:

  1. Evaluate the load and grid profiles at t_k   -> P_load[k], grid_voltage_pu[k],
                                                      grid_available[k]
  2. Compute this step's available power limit from the CURRENT
     protection derate_factor (set by the previous step's protection
     evaluation) and the CURRENT grid condition:
         P_available_max[k] = rated_power_w * derate_factor * grid_factor
  3. Run the controller using the CURRENT V_dc and P_load[k], saturating
     to P_available_max[k]                        -> P_cmd[k], P_target[k]
  4. Compute SST losses from the CURRENT P_sst
     (power actually delivered during this step)   -> P_input[k], P_loss[k]
  5. Record telemetry for step k using the CURRENT state (V_dc, E_dc,
     P_sst, T, protection state) and this step's inputs/commands.
  6. Advance state to k+1 using explicit Euler:
       P_sst -> first-order lag toward P_target[k]
       E_dc  -> power balance using CURRENT P_sst[k] and P_load[k]
       V_dc  -> recovered algebraically from new E_dc
       T     -> thermal balance using CURRENT P_loss[k]
  7. Evaluate protection using the FRESHLY INTEGRATED T[k+1] -> this
     updates derate_factor/operating_state/trip, which will be used as
     the "CURRENT" protection state at step k+1 (back to step 2).

This realizes the causal chain: electrical load -> SST power -> loss ->
temperature -> protection -> available power -> electrical response,
with protection evaluated once per step, after thermal integration. A
single post-integration evaluation point is preferred over separate
pre/post checks because a trip condition is physically defined on
measured plant state (V_dc, T), which only exists after integration;
the one-step lag before enforcement is also physically realistic
(real sensors/relays have response latency).

Numerical method: explicit (forward) Euler, fixed timestep, per
CLAUDE.md's "keep V1 simple" direction.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from src.config import Config
from src.controller import ControllerState, step_voltage_controller
from src.dc_bus import energy_from_voltage, step_dc_bus_energy, voltage_from_energy
from src.grid import grid_power_availability_factor
from src.protection import ProtectionState, step_protection
from src.sst import compute_sst_losses, step_sst_power
from src.telemetry import Telemetry
from src.thermal import step_thermal_temperature


def _constant_grid(t_s: float) -> tuple[float, bool]:
    """Default grid condition: always nominal and available."""
    return 1.0, True


def run_simulation(
    config: Config,
    load_power_fn: Callable[[float], float],
    grid_fn: Callable[[float], tuple[float, bool]] = _constant_grid,
    initial_p_sst_w: float = 0.0,
    initial_integral_error_v_s: float = 0.0,
) -> Telemetry:
    """Run the full V1 simulation (electrical + thermal + protection).

    Args:
        config: validated simulation configuration.
        load_power_fn: callable mapping time [s] to P_load [W].
        grid_fn: callable mapping time [s] to (grid_voltage_pu, grid_available).
            Defaults to a constant nominal, always-available grid.
        initial_p_sst_w: SST output power at t=0 [W]. Defaults to 0.0
            (a cold start). A scenario that wants to begin at a
            particular steady-state operating point -- to isolate a
            later disturbance from the startup transient -- should
            pass the matching P_load(0) here instead.
        initial_integral_error_v_s: controller integrator state at
            t=0 [V*s]. Defaults to 0.0, which is the consistent
            equilibrium value whenever V_dc(0) = V_ref and
            initial_p_sst_w already equals P_load(0).

    Returns:
        Telemetry with one sample per timestep (see module docstring
        for exactly which instant each sample represents).
    """
    dt_s = config.simulation.timestep_s
    n_steps = int(round(config.simulation.duration_s / dt_s))

    sst_cfg = config.sst
    bus_cfg = config.dc_bus
    ctrl_cfg = config.controller
    thermal_cfg = config.thermal
    protection_cfg = config.protection

    v_dc_v = bus_cfg.initial_voltage_v
    e_dc_j = energy_from_voltage(v_dc_v, bus_cfg.capacitance_f)
    p_sst_w = initial_p_sst_w
    temperature_c = thermal_cfg.initial_temperature_c
    controller_state = ControllerState(integral_error_v_s=initial_integral_error_v_s)
    protection_state = ProtectionState()

    time_arr = np.empty(n_steps)
    grid_voltage_arr = np.empty(n_steps)
    grid_available_arr = np.empty(n_steps, dtype=bool)
    p_load_arr = np.empty(n_steps)
    p_cmd_arr = np.empty(n_steps)
    p_target_arr = np.empty(n_steps)
    p_sst_arr = np.empty(n_steps)
    p_input_arr = np.empty(n_steps)
    p_loss_arr = np.empty(n_steps)
    e_dc_arr = np.empty(n_steps)
    v_dc_arr = np.empty(n_steps)
    voltage_error_arr = np.empty(n_steps)
    integral_arr = np.empty(n_steps)
    temperature_arr = np.empty(n_steps)
    operating_state_arr = np.empty(n_steps, dtype=object)
    derate_factor_arr = np.empty(n_steps)
    trip_active_arr = np.empty(n_steps, dtype=bool)
    trip_reason_arr = np.empty(n_steps, dtype=object)

    for k in range(n_steps):
        t_s = k * dt_s
        p_load_w = load_power_fn(t_s)
        grid_voltage_pu, grid_available = grid_fn(t_s)

        p_available_max_w = (
            sst_cfg.rated_power_w
            * protection_state.derate_factor
            * grid_power_availability_factor(grid_voltage_pu, grid_available)
        )

        p_cmd_w, p_target_w = step_voltage_controller(
            state=controller_state,
            v_dc_v=v_dc_v,
            p_load_w=p_load_w,
            v_ref_v=ctrl_cfg.voltage_reference_v,
            kp_w_per_v=ctrl_cfg.kp_w_per_v,
            ki_w_per_v_s=ctrl_cfg.ki_w_per_v_s,
            integral_min_v_s=ctrl_cfg.integral_min_v_s,
            integral_max_v_s=ctrl_cfg.integral_max_v_s,
            p_min_w=sst_cfg.min_power_w,
            p_max_w=p_available_max_w,
            dt_s=dt_s,
        )
        # step_voltage_controller already saturates p_target_w to
        # [sst_cfg.min_power_w, p_available_max_w] internally -- no second
        # clip needed here.

        p_input_w, p_loss_w = compute_sst_losses(p_sst_w, sst_cfg.efficiency)
        voltage_error_v = ctrl_cfg.voltage_reference_v - v_dc_v

        time_arr[k] = t_s
        grid_voltage_arr[k] = grid_voltage_pu
        grid_available_arr[k] = grid_available
        p_load_arr[k] = p_load_w
        p_cmd_arr[k] = p_cmd_w
        p_target_arr[k] = p_target_w
        p_sst_arr[k] = p_sst_w
        p_input_arr[k] = p_input_w
        p_loss_arr[k] = p_loss_w
        e_dc_arr[k] = e_dc_j
        v_dc_arr[k] = v_dc_v
        voltage_error_arr[k] = voltage_error_v
        integral_arr[k] = controller_state.integral_error_v_s
        temperature_arr[k] = temperature_c
        operating_state_arr[k] = protection_state.operating_state.value
        derate_factor_arr[k] = protection_state.derate_factor
        trip_active_arr[k] = protection_state.trip_active
        trip_reason_arr[k] = protection_state.trip_reason

        p_sst_next = step_sst_power(p_sst_w, p_target_w, sst_cfg.time_constant_s, dt_s)
        e_dc_next = step_dc_bus_energy(e_dc_j, p_sst_w, p_load_w, dt_s, bus_cfg.min_energy_j)
        v_dc_next = voltage_from_energy(e_dc_next, bus_cfg.capacitance_f)
        temperature_next = step_thermal_temperature(
            temperature_c,
            p_loss_w,
            dt_s,
            thermal_cfg.thermal_capacitance_j_per_c,
            thermal_cfg.thermal_resistance_c_per_w,
            thermal_cfg.ambient_temperature_c,
        )

        step_protection(
            protection_state,
            temperature_next,
            dt_s,
            protection_cfg.thermal_derate_start_c,
            protection_cfg.thermal_trip_c,
            protection_cfg.thermal_trip_time_s,
            protection_cfg.derate_factor_min,
        )

        p_sst_w = p_sst_next
        e_dc_j = e_dc_next
        v_dc_v = v_dc_next
        temperature_c = temperature_next

    return Telemetry(
        time_s=time_arr,
        grid_voltage_pu=grid_voltage_arr,
        grid_available=grid_available_arr,
        p_load_w=p_load_arr,
        p_cmd_w=p_cmd_arr,
        p_target_w=p_target_arr,
        p_sst_w=p_sst_arr,
        p_input_w=p_input_arr,
        p_loss_w=p_loss_arr,
        e_dc_j=e_dc_arr,
        v_dc_v=v_dc_arr,
        voltage_error_v=voltage_error_arr,
        controller_integral_v_s=integral_arr,
        temperature_c=temperature_arr,
        operating_state=operating_state_arr,
        derate_factor=derate_factor_arr,
        trip_active=trip_active_arr,
        trip_reason=trip_reason_arr,
    )
