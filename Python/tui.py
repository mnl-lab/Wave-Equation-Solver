"""Text-based user interface for configuring the wave equation solver.

Prompts the user for scenario selection (Dirichlet or Neumann), validates the
inputs, and forwards them to the Fortran runner. The time step ``dt`` is always
inferred from CFL guidance and is not entered manually. Unused fields are kept
minimal for now to match the current two-scenario setup.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import build_payload, compute_dt, get_scenario_defaults
from runner import run_solver
from visualize import auto_visualize_run


def _prompt_int(prompt: str, *, default: int, min_value: Optional[int] = None) -> int:
    """Prompt for an integer with optional lower-bound validation."""

    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if raw == "":
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                print("Please enter a valid integer.")
                continue
        if min_value is not None and value < min_value:
            print(f"Value must be >= {min_value}.")
            continue
        return value


def _prompt_float(
    prompt: str, *, default: float, min_value: Optional[float] = None
) -> float:
    """Prompt for a float with optional lower-bound validation."""

    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if raw == "":
            value = default
        else:
            try:
                value = float(raw)
            except ValueError:
                print("Please enter a valid number.")
                continue
        if min_value is not None and value < min_value:
            print(f"Value must be >= {min_value}.")
            continue
        return value


def _prompt_yes_no(prompt: str, *, default: bool = False) -> bool:
    """Prompt for a yes/no response with default fallback."""

    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{prompt} {suffix}: ").strip().lower()
        if raw == "" and default is not None:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _prompt_output_type(default: str) -> str:
    """Prompt for output type selection."""

    options = {"1": "ascii", "2": "csv", "3": "hdf5"}
    reverse = {v: k for k, v in options.items()}
    default_key = reverse.get(default, "1")
    while True:
        raw = input(
            "Select output type 1=ASCII, 2=CSV, 3=HDF5 " f"[{default_key}]: "
        ).strip()
        choice = raw or default_key
        if choice in options:
            return options[choice]
        print("Choose 1, 2, or 3.")


def _coerce_domain_length(nx: int, dx: float, L: float) -> float:
    """Ensure nx * dx matches L; adjust dx if needed with notification."""

    expected_dx = L / nx
    if abs(expected_dx - dx) > 1e-10:
        print(
            f"Adjusting dx to {expected_dx} so that Nx*dx equals domain length L={L}."
        )
        return expected_dx
    return dx


def _coerce_t_final_multiple(t_final: float, dt: float) -> float:
    """Ensure t_final is an integer multiple of dt; adjust if needed."""

    ratio = t_final / dt
    nearest = round(ratio)
    adjusted = nearest * dt
    if abs(adjusted - t_final) > 1e-12:
        print(f"Adjusting T_final to {adjusted} to be a multiple of dt.")
        return adjusted
    return t_final


def _prompt_scenario() -> int:
    """Ask the user for a scenario ID between 1 and 2."""

    while True:
        raw = input("Select scenario (1=Dirichlet, 2=Neumann): ").strip()
        try:
            scenario = int(raw)
        except ValueError:
            print("Scenario must be an integer between 1 and 2.")
            continue
        if scenario not in {1, 2}:
            print("Scenario must be between 1 and 2.")
            continue
        return scenario


def collect_parameters() -> Dict[str, Any]:
    """Collect and validate parameters from the user, merging with defaults."""

    scenario_id = _prompt_scenario()
    defaults = get_scenario_defaults(scenario_id)

    print("\nPress Enter to accept the default in brackets.")

    nx = _prompt_int("Number of spatial points Nx", default=defaults.nx, min_value=3)
    dx = _prompt_float("Spatial step dx", default=defaults.dx, min_value=1e-12)
    L = _prompt_float("Domain length L", default=defaults.L, min_value=1e-12)
    dx = _coerce_domain_length(nx, dx, L)

    cfl = _prompt_float("CFL number (lambda)", default=defaults.cfl, min_value=0.0)

    dt = compute_dt(
        scenario_id,
        dx,
        cfl,
        wave_speed=defaults.wave_speed,
        c_max=defaults.c_max,
    )
    print(f"Inferred time step dt from CFL: {dt}")

    t_final = _prompt_float(
        "Final time T_final", default=defaults.t_final, min_value=dt
    )
    t_final = _coerce_t_final_multiple(t_final, dt)
    gamma = 0.0  # damping not used in scenarios 1-2

    # Force CSV output to match visualization expectations
    output_type = "csv"
    output_frequency = _prompt_int(
        "Output frequency (save every N steps)",
        default=defaults.output_frequency,
        min_value=1,
    )
    logging_enabled = _prompt_yes_no(
        "Enable logging to timestamped folder?", default=defaults.logging_enabled
    )

    c_profile: List[float] | str = []  # variable c(x) not used in scenarios 1-2

    overrides: Dict[str, Any] = {
        "scenario_id": scenario_id,
        "nx": nx,
        "dx": dx,
        "L": L,
        "dt": dt,
        "t_final": t_final,
        "gamma": gamma,
        "cfl": cfl,
        "wave_speed": defaults.wave_speed,
        "c_max": defaults.c_max,
        "output_type": output_type,
        "output_frequency": output_frequency,
        "logging_enabled": logging_enabled,
        "c_profile": c_profile,
    }

    params = build_payload(scenario_id, overrides)

    return params


def main() -> None:
    """Entry point for the command-line TUI."""

    print("Wave Equation Solver — Parameter TUI")
    params = collect_parameters()

    print("\nParameters to be sent to the Fortran solver:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    # Placeholder: additional validation or pre-processing can be added here.
    result = run_solver(params)

    print("\nRun result summary:")
    for key in ["status", "run_dir", "input_path", "schema_version"]:
        print(f"  {key}: {result.get(key)}")

    if result.get("status") == "success":
        auto_visualize_run(result)


if __name__ == "__main__":
    main()
