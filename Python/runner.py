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
from typing import Any, Dict, Iterable, List, Optional, Sequence

from config import SCHEMA_VERSION


DEFAULT_INPUT_FILENAME = "input.json"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"
EXECUTABLE_DIR = Path(__file__).resolve().parent.parent / "Fortran" / "src"
SCENARIO_EXECUTABLES: Dict[int, str] = {
    1: "solver_dirichlet.exe",
    2: "solver_neumann.exe",
}
SCENARIO_SOURCES: Dict[int, List[str]] = {
    1: [
        "solver_core.f90",
        "input_io.f90",
        "initial_conditions.f90",
        "bc_dirichlet.f90",
        "scenario1_dirichlet.f90",
    ],
    2: [
        "solver_core.f90",
        "input_io.f90",
        "initial_conditions.f90",
        "bc_neumann.f90",
        "scenario2_neumann.f90",
    ],
}


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


def _extract_scenario_id(params: Dict[str, Any]) -> int:
    """Obtain a scenario id from the parameter dictionary."""

    candidate = params.get("scenario_id") or params.get("scenario")
    if candidate is None:
        raise ValueError("scenario_id is required to choose the solver executable.")

    try:
        return int(candidate)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"scenario_id must be an integer; received {candidate!r}."
        ) from exc


def run_solver(
    params: Dict[str, Any],
    *,
    executable_map: Optional[Dict[int, str]] = None,
    executable_override: Optional[str] = None,
    executable_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Write parameters, pick the scenario executable, and invoke the solver."""

    run_label = _build_run_label(params)
    run_dir = _ensure_run_directory(run_label)
    input_path = write_input_file(params, output_dir=run_dir)

    scenario_id = _extract_scenario_id(params)
    exe_map = executable_map or SCENARIO_EXECUTABLES
    executable = executable_override or exe_map.get(scenario_id)
    if executable is None:
        raise ValueError(
            f"No executable configured for scenario {scenario_id}. "
            "Add it to SCENARIO_EXECUTABLES or pass executable_override."
        )

    solver_candidate = _ensure_executable(
        executable,
        scenario_id=scenario_id,
        executable_path=executable_path,
    )

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


def _resolve_executable(
    executable: str,
    executable_path: Optional[Path],
    *,
    search_dirs: Optional[Sequence[Path]] = None,
) -> Path:
    """Resolve the solver executable path.

    Resolution order:
    1) Explicit executable_path argument (relative paths resolved from this file's directory).
    2) Environment variable WAVE_SOLVER_EXE.
    3) If 'executable' contains a path separator, resolve it relative to this file.
    4) Fallback to PATH lookup via shutil.which.
    5) Additional search_dirs (e.g., the Fortran build output folder).
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

    for search_dir in search_dirs or []:
        candidates.append(Path(search_dir) / executable)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    tried = " | ".join(str(p) for p in candidates) or executable
    raise FileNotFoundError(
        "Solver executable could not be resolved. "
        f"Tried: {tried}. "
        "Set WAVE_SOLVER_EXE, pass executable_path, or add to PATH."
    )


def _ensure_executable(
    executable: str,
    *,
    scenario_id: int,
    executable_path: Optional[Path],
) -> Path:
    """Resolve the solver binary; auto-compile if missing.

    The build uses a simple gfortran invocation with sources defined per
    scenario in SCENARIO_SOURCES. Compiler and flags can be overridden via
    environment variables WAVE_SOLVER_FC and WAVE_SOLVER_FFLAGS.
    """

    try:
        return _resolve_executable(
            executable, executable_path, search_dirs=[EXECUTABLE_DIR]
        )
    except FileNotFoundError:
        pass

    sources = SCENARIO_SOURCES.get(scenario_id)
    if sources is None:
        raise FileNotFoundError(
            f"Missing executable {executable} and no sources registered "
            f"for scenario {scenario_id}."
        )

    output_path = (
        Path(executable_path)
        if executable_path is not None
        else EXECUTABLE_DIR / executable
    )

    _build_executable(output_path, sources)

    return _resolve_executable(
        str(output_path), executable_path=None, search_dirs=[EXECUTABLE_DIR]
    )


def _build_executable(output_path: Path, sources: Sequence[str]) -> None:
    """Compile Fortran sources into an executable if missing."""

    compiler = os.getenv("WAVE_SOLVER_FC", "gfortran")
    extra_flags = os.getenv("WAVE_SOLVER_FFLAGS", "-O2").split()

    src_dir = EXECUTABLE_DIR
    cmd = [compiler, *extra_flags]
    cmd.extend(str(src_dir / src) for src in sources)
    cmd.extend(["-o", str(output_path)])

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(cmd, check=True, cwd=src_dir, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Automatic build failed. "
            f"Command: {' '.join(cmd)}\nstdout: {exc.stdout}\nstderr: {exc.stderr}"
        ) from exc


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
    """Run the Dirichlet boundary executable (scenario 1)."""

    return run_solver(params, executable_override=SCENARIO_EXECUTABLES[1])


def run_scenario2(params: Dict[str, Any]) -> Dict[str, Any]:
    """Run the Neumann boundary executable (scenario 2)."""

    return run_solver(params, executable_override=SCENARIO_EXECUTABLES[2])


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
