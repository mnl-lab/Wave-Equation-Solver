"""Runner that bridges the Python front-end with the Fortran solver.

This module accepts validated parameters, serializes them to JSON (versioned
schema), and invokes an external Fortran executable (placeholder name:
"wave_solver"). It also exposes placeholder hooks for scenario-specific
execution, diagnostics, and batch/multiprocess runs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from config import SCHEMA_VERSION


DEFAULT_INPUT_FILENAME = "input.json"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"


def _ensure_run_directory(logging_enabled: bool) -> Path:
    """Select a run directory under outputs/ to keep artifacts separate from code."""

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S") if logging_enabled else "latest"
    run_dir = DEFAULT_OUTPUT_ROOT / f"run-{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_input_file(
    params: Dict[str, Any], *, output_dir: Optional[Path] = None
) -> Path:
    """Serialize parameters to a JSON file consumable by the Fortran solver."""

    target_dir = output_dir or Path(__file__).resolve().parent
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(params)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    output_path = target_dir / DEFAULT_INPUT_FILENAME
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    return output_path


def run_solver(
    params: Dict[str, Any],
    *,
    executable: str = "wave_solver",
    executable_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Write parameters and invoke the Fortran solver.

    Returns a result dictionary with stdout/stderr and discovered outputs.

    Raises:
        FileNotFoundError: If the solver executable cannot be located.
        RuntimeError: If the solver process exits with a non-zero status.
    """

    run_dir = _ensure_run_directory(bool(params.get("logging_enabled", False)))
    input_path = write_input_file(params, output_dir=run_dir)

    solver_candidate = _resolve_executable(executable, executable_path)

    try:
        completed = subprocess.run(
            [str(solver_candidate), str(input_path)],
            check=True,
            capture_output=True,
            text=True,
            cwd=run_dir,
        )
    except subprocess.CalledProcessError as exc:
        err_msg = (
            "Fortran solver failed; see stderr for details. "
            f"stdout: {exc.stdout!r} stderr: {exc.stderr!r}"
        )
        raise RuntimeError(err_msg) from exc

    outputs = parse_output_files(run_dir)
    result: Dict[str, Any] = {
        "status": "success",
        "schema_version": SCHEMA_VERSION,
        "input_path": str(input_path),
        "run_dir": str(run_dir),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "outputs": outputs,
    }
    return result


def _resolve_executable(executable: str, executable_path: Optional[Path]) -> Path:
    """Resolve the solver executable path.

    Resolution order:
    1) Explicit executable_path argument (relative paths resolved from this file's directory).
    2) Environment variable WAVE_SOLVER_EXE.
    3) If 'executable' contains a path separator, resolve it relative to this file.
    4) Fallback to PATH lookup via shutil.which.
    """

    base_dir = Path(__file__).resolve().parent

    candidates: List[Path] = []

    if executable_path is not None:
        p = Path(executable_path)
        candidates.append(p if p.is_absolute() else (base_dir / p).resolve())

    env_val = os.getenv("WAVE_SOLVER_EXE")
    if env_val:
        p = Path(env_val)
        candidates.append(p if p.is_absolute() else (base_dir / p).resolve())

    if any(sep in executable for sep in ("/", "\\")):
        p = Path(executable)
        candidates.append(p if p.is_absolute() else (base_dir / p).resolve())

    which = shutil.which(executable)
    if which:
        candidates.append(Path(which))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    tried = " | ".join(str(p) for p in candidates) or executable
    raise FileNotFoundError(
        "Solver executable could not be resolved. "
        f"Tried: {tried}. "
        "Set WAVE_SOLVER_EXE, pass executable_path, or add to PATH."
    )


def parse_output_files(run_dir: Path) -> Dict[str, Any]:
    """Placeholder parser for solver outputs (ASCII/CSV/HDF5).

    TODO: implement actual parsing once the Fortran solver writes outputs.
    """

    # For now, return discovered files with basic metadata.
    artifacts: List[str] = []
    for path in run_dir.glob("*"):
        if path.is_file():
            artifacts.append(path.name)
    return {
        "artifacts": artifacts,
        "energy": None,  # hook for energy diagnostics
        "cfl_diagnostics": None,
        "timing": None,
    }


def run_scenario1(params: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder runner for scenario 1 (Dirichlet).

    TODO: replace this with a dedicated call into the Fortran solver when the
    scenario-specific entry point is available.
    """

    return run_solver(params)


def run_batch(parameter_sets: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run multiple scenarios sequentially; hook for future multiprocessing."""

    results: List[Dict[str, Any]] = []
    for params in parameter_sets:
        results.append(run_solver(params))
    return results


def compute_energy_placeholder(output: Dict[str, Any]) -> None:
    """Placeholder for post-processing energy diagnostics across scenarios."""

    # TODO: parse outputs and compute energy metrics here.
    return None
