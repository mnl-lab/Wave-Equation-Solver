"""Configuration defaults for the wave equation scenarios.

This module centralizes default numerical and physical parameters so that both
the TUI and the runner import the same values. Defaults are intentionally
conservative (CFL <= 1) and serve as reasonable starting points for
experiments; users can override any of them via the TUI. It also exposes helpers
to assemble JSON-ready payloads with a stable schema version.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from typing import Any, Dict, List, Mapping


SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ScenarioDefaults:
    """Container for scenario default parameters."""

    scenario_id: int
    nx: int
    dx: float
    L: float
    wave_speed: float
    c_max: float
    cfl: float
    t_final: float
    gamma: float
    output_type: str
    output_frequency: int
    logging_enabled: bool
    c_profile: List[float]

    def to_dict(self) -> Dict[str, Any]:
        """Return defaults as a plain dictionary."""

        return asdict(self)


def _build_defaults() -> Dict[int, ScenarioDefaults]:
    """Define defaults for all supported scenarios (1-4)."""

    # These values are placeholders
    base_dx = 0.01
    base_L = 2.0
    base_nx = int(base_L / base_dx)  # ensures nx * dx matches L
    base_c = 1.0
    base_t_final = 1.0
    base_cfl = 0.9  # safely below the stability limit
    base_output_frequency = 10

    return {
        1: ScenarioDefaults(
            scenario_id=1,
            nx=base_nx,
            dx=base_dx,
            L=base_L,
            wave_speed=base_c,
            c_max=base_c,
            cfl=base_cfl,
            t_final=base_t_final,
            gamma=0.0,
            output_type="csv",
            output_frequency=base_output_frequency,
            logging_enabled=False,
            c_profile=[],
        ),
        2: ScenarioDefaults(
            scenario_id=2,
            nx=base_nx,
            dx=base_dx,
            L=base_L,
            wave_speed=base_c,
            c_max=base_c,
            cfl=base_cfl,
            t_final=base_t_final,
            gamma=0.0,
            output_type="csv",
            output_frequency=base_output_frequency,
            logging_enabled=False,
            c_profile=[],
        ),
        3: ScenarioDefaults(
            scenario_id=3,
            nx=base_nx,
            dx=base_dx,
            L=base_L,
            wave_speed=base_c,
            c_max=1.5,  # variable speed; max used for CFL
            cfl=0.8,
            t_final=base_t_final,
            gamma=0.0,
            output_type="csv",
            output_frequency=base_output_frequency,
            logging_enabled=False,
            c_profile=[],
        ),
        4: ScenarioDefaults(
            scenario_id=4,
            nx=base_nx,
            dx=base_dx,
            L=base_L,
            wave_speed=base_c,
            c_max=base_c,
            cfl=0.7,  # slightly stricter for damping tests
            t_final=base_t_final,
            gamma=0.05,
            output_type="csv",
            output_frequency=base_output_frequency,
            logging_enabled=False,
            c_profile=[],
        ),
    }


_SCENARIO_DEFAULTS = _build_defaults()


def list_scenarios() -> Dict[int, ScenarioDefaults]:
    """Return all scenario defaults keyed by scenario id."""

    return _SCENARIO_DEFAULTS


def get_scenario_defaults(scenario_id: int) -> ScenarioDefaults:
    """Fetch defaults for a scenario.

    Raises:
            KeyError: If the scenario is not defined.
    """

    if scenario_id not in _SCENARIO_DEFAULTS:
        raise KeyError(f"Unsupported scenario id {scenario_id}; choose 1–4")
    return _SCENARIO_DEFAULTS[scenario_id]


def compute_dt(
    scenario_id: int, dx: float, cfl: float, *, wave_speed: float, c_max: float
) -> float:
    """Compute a stable time step from CFL guidance.

    Scenario 3 uses the maximum wave speed; other scenarios use the provided
    wave_speed. The formulas mirror description.md.
    """

    if scenario_id == 3:
        return (cfl * dx) / c_max
    return (cfl * dx) / wave_speed


def build_payload(
    scenario_id: int,
    overrides: Mapping[str, Any],
) -> Dict[str, Any]:
    """Assemble a JSON-ready dictionary using defaults and caller overrides.

    All expected schema fields are populated; unused scenario fields are given
    safe placeholder values to keep the JSON shape stable.
    """

    defaults = get_scenario_defaults(scenario_id)
    merged_defaults = replace(
        defaults, **{k: v for k, v in overrides.items() if hasattr(defaults, k)}
    )

    payload: Dict[str, Any] = merged_defaults.to_dict()
    # Schema-level fields that might not be in the dataclass yet
    payload.update(
        {
            "schema_version": SCHEMA_VERSION,
            # Ensure placeholders exist even if not used by a scenario
            "output_type": payload.get("output_type", "ascii"),
            "output_frequency": payload.get("output_frequency", 1),
            "snapshot_freq": payload.get("output_frequency", 1),
            "logging_enabled": bool(payload.get("logging_enabled", False)),
            "c_profile": payload.get("c_profile", []),
        }
    )

    # Carry through overrides that are outside the dataclass (e.g., dt)
    for key, value in overrides.items():
        payload[key] = value

    # Placeholders for compatibility
    payload.setdefault("gamma", 0.0)
    payload.setdefault("c_profile", [])
    return payload
