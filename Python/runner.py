"""Runner that bridges the Python front-end with the Fortran solver.

This module accepts validated parameters, serializes them to JSON (versioned
schema), and invokes an external Fortran executable (placeholder name:
"wave_solver"). It also exposes placeholder hooks for scenario-specific
execution, diagnostics, and batch/multiprocess runs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from config import SCHEMA_VERSION


DEFAULT_INPUT_FILENAME = "input.json"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"


def _float_token(value: Any) -> str:
    """Short, filename-safe token for float-like values."""

    try:
        num = float(value)
    except (TypeError, ValueError):
        return "x"
    text = f"{num:.4g}"  # keep it short but informative
    return text.replace(".", "p").replace("-", "m")


def _sanitize_token(value: str) -> str:
    """Remove characters that are awkward in file or directory names."""

    token = re.sub(r"[^A-Za-z0-9_-]", "-", value)
    token = re.sub(r"-{2,}", "-", token).strip("-")
    return token or "run"


def _build_run_label(params: Dict[str, Any]) -> str:
    """Construct a concise label using scenario and key numerics."""

    parts: List[str] = []

    scenario = params.get("scenario_id")
    if scenario is not None:
        parts.append(f"s{scenario}")

    nx = params.get("nx")
    if nx:
        parts.append(f"nx{nx}")

    dx = params.get("dx")
    if dx is not None:
        parts.append(f"dx{_float_token(dx)}")

    dt = params.get("dt")
    if dt is not None:
        parts.append(f"dt{_float_token(dt)}")

    freq = params.get("output_frequency") or params.get("snapshot_freq")
    if freq:
        parts.append(f"f{freq}")

    label = "-".join(parts) or "run"
    return _sanitize_token(label)


def _ensure_run_directory(run_label: str) -> Path:
    """Select a unique run directory under outputs/ using label + timestamp."""

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = DEFAULT_OUTPUT_ROOT / f"run-{run_label}-{timestamp}"
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

    run_label = _build_run_label(params)
    run_dir = _ensure_run_directory(run_label)
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

    _rename_run_outputs(run_dir, run_label)
    outputs = parse_output_files(run_dir)
    result: Dict[str, Any] = {
        "status": "success",
        "schema_version": SCHEMA_VERSION,
        "run_label": run_label,
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


def _rename_run_outputs(run_dir: Path, run_label: str) -> None:
    """Attach the run label to solver-generated files to avoid clobbering."""

    # Snapshots
    for path in run_dir.glob("snapshot_*.csv"):
        if path.name.startswith(f"{run_label}_snapshot_"):
            continue
        stem = path.stem  # snapshot_10 -> snapshot_10
        suffix = stem.split("_", maxsplit=1)[-1]
        target = run_dir / f"{run_label}_snapshot_{suffix}.csv"
        path.rename(target)

    # Energy log
    energy_path = run_dir / "energy.csv"
    if energy_path.exists() and not energy_path.name.startswith(run_label):
        target = run_dir / f"{run_label}_energy.csv"
        energy_path.rename(target)


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
