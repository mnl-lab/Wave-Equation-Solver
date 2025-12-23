"""Visualization and diagnostics for wave solver outputs.

This module provides helper routines to load solver outputs (ASCII/CSV), plot
field snapshots with matplotlib, and compute / plot convergence metrics. It is
kept decoupled from the TUI and runner; you can import and call these functions
from notebooks, scripts, or future CLI commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation

# Use a non-interactive backend for automated runs
matplotlib.use("Agg")


@dataclass
class ErrorMetrics:
	"""Container for error norms."""

	l1: float
	l2: float
	linf: float


def load_snapshot(path: Path, *, delimiter: str = ",", skip_header: int = 0) -> Tuple[np.ndarray, np.ndarray]:
	"""Load a snapshot file.

	Supports:
	- two columns: x, u(x)
	- one column: u(x) with synthetic x = [0, 1, 2, ...]
	- auto-skips a single header line if needed
	"""

	def _try_load(skip: int) -> np.ndarray:
		return np.loadtxt(path, delimiter=delimiter, skiprows=skip)

	try:
		data = _try_load(skip_header)
	except Exception:
		data = _try_load(skip_header + 1)

	if data.ndim == 1:
		data = data.reshape(-1, 1)
	if data.shape[1] == 1:
		u = data[:, 0]
		x = np.arange(u.size, dtype=float)
		return x, u
	if data.shape[1] >= 2:
		return data[:, 0], data[:, 1]
	raise ValueError(f"Unexpected shape in {path}: {data.shape}")


def compute_error_metrics(u: np.ndarray, u_ref: np.ndarray) -> ErrorMetrics:
	"""Compute L1, L2, and Linf errors between solution and reference."""

	if u.shape != u_ref.shape:
		raise ValueError("u and u_ref must have the same shape")
	diff = np.abs(u - u_ref)
	l1 = float(np.mean(diff))
	l2 = float(np.sqrt(np.mean(diff**2)))
	linf = float(np.max(diff))
	return ErrorMetrics(l1=l1, l2=l2, linf=linf)


def convergence_rate(dx: Sequence[float], errors: Sequence[float]) -> float:
	"""Estimate convergence rate from dx and error arrays using log-slope.

	Uses the last two points; for a more robust fit, use polyfit on log-log.
	"""

	if len(dx) < 2 or len(errors) < 2:
		raise ValueError("Need at least two points to estimate convergence rate")
	x1, x2 = dx[-2], dx[-1]
	e1, e2 = errors[-2], errors[-1]
	if e1 <= 0 or e2 <= 0:
		raise ValueError("Errors must be positive for log-slope")
	return (log(e2) - log(e1)) / (log(x2) - log(x1))


def plot_snapshot(x: np.ndarray, u: np.ndarray, *, title: str = "Snapshot", save_path: Path | None = None) -> None:
	"""Plot a single field snapshot."""

	fig, ax = plt.subplots()
	ax.plot(x, u, label="u(x)")
	ax.set_xlabel("x")
	ax.set_ylabel("u")
	ax.set_title(title)
	ax.legend()
	ax.grid(True)
	if save_path:
		fig.savefig(save_path, bbox_inches="tight")
	else:
		plt.show()
	plt.close(fig)


def plot_error(x: np.ndarray, err: np.ndarray, *, title: str = "Error", save_path: Path | None = None) -> None:
	"""Plot pointwise error."""

	fig, ax = plt.subplots()
	ax.plot(x, err, label="|u - u_ref|")
	ax.set_xlabel("x")
	ax.set_ylabel("error")
	ax.set_title(title)
	ax.legend()
	ax.grid(True)
	if save_path:
		fig.savefig(save_path, bbox_inches="tight")
	else:
		plt.show()
	plt.close(fig)


def plot_convergence(dx: Iterable[float], errors: Iterable[float], *, title: str = "Convergence", save_path: Path | None = None) -> float:
	"""Plot error vs dx on log-log and return estimated rate (slope)."""

	dx_arr = np.array(list(dx), dtype=float)
	err_arr = np.array(list(errors), dtype=float)
	fig, ax = plt.subplots()
	ax.loglog(dx_arr, err_arr, "o-", label="error")
	ax.set_xlabel("dx")
	ax.set_ylabel("error")
	ax.set_title(title)
	ax.grid(True, which="both")
	rate = convergence_rate(dx_arr, err_arr)
	ax.legend(title=f"rate≈{rate:.2f}")
	if save_path:
		fig.savefig(save_path, bbox_inches="tight")
	else:
		plt.show()
	plt.close(fig)
	return rate


def plot_multiple_snapshots(snapshots: List[Tuple[np.ndarray, np.ndarray]], labels: List[str], *, title: str = "Snapshots", save_path: Path | None = None) -> None:
	"""Overlay several snapshots for comparison."""

	if len(snapshots) != len(labels):
		raise ValueError("snapshots and labels must have same length")
	fig, ax = plt.subplots()
	for (x, u), label in zip(snapshots, labels):
		ax.plot(x, u, label=label)
	ax.set_xlabel("x")
	ax.set_ylabel("u")
	ax.set_title(title)
	ax.legend()
	ax.grid(True)
	if save_path:
		fig.savefig(save_path, bbox_inches="tight")
	else:
		plt.show()
	plt.close(fig)


def auto_visualize_run(result: dict) -> None:
	"""Automatically visualize outputs after a successful run.

	Expectations (best-effort):
	- Snapshot files in run_dir matching patterns: snapshot*.csv, *.csv, *.dat, *.txt (two columns x,u).
	- Optional reference file: reference.csv in run_dir (two columns x,u_ref) to compute/plot errors.
	- Optional convergence file: convergence.csv in run_dir (two columns dx,error) to plot convergence rate.

	Plots are saved into run_dir as PNGs and metrics are printed to stdout.
	"""

	run_dir_val = result.get("run_dir")
	if not run_dir_val:
		print("[viz] No run_dir in result; skipping auto visualization.")
		return
	run_dir = Path(run_dir_val)
	if not run_dir.exists():
		print(f"[viz] run_dir {run_dir} does not exist; skipping.")
		return

	# Find snapshots
	snapshot_paths: List[Path] = []
	patterns = ["snapshot*.csv", "*.csv", "*.dat", "*.txt"]
	for pat in patterns:
		snapshot_paths.extend(sorted(run_dir.glob(pat)))
	# Filter out non-snapshot files
	snapshot_paths = [
		p
		for p in snapshot_paths
		if "reference" not in p.name.lower()
		and "convergence" not in p.name.lower()
		and "energy" not in p.name.lower()
		and "input" not in p.name.lower()
	]

	if snapshot_paths:
		snap_path = snapshot_paths[0]
		try:
			x, u = load_snapshot(snap_path, delimiter=",")
			out_path = run_dir / "snapshot_plot.png"
			plot_snapshot(x, u, title=f"Snapshot ({snap_path.name})", save_path=out_path)
			print(f"[viz] Saved snapshot plot to {out_path}")
		except Exception as exc:  # pylint: disable=broad-except
			print(f"[viz] Failed to plot snapshot {snap_path}: {exc}")
		# Attempt animation if multiple snapshots
		if len(snapshot_paths) >= 2:
			try:
				anim_path = run_dir / "animation.mp4"
				create_animation(snapshot_paths, save_path=anim_path)
				print(f"[viz] Saved animation to {anim_path}")
			except Exception as exc:  # pylint: disable=broad-except
				print(f"[viz] Failed to create animation: {exc}")
	else:
		print("[viz] No snapshot files found to plot.")

	# Reference-based error plot if available
	ref_path = run_dir / "reference.csv"
	if ref_path.exists():
		try:
			x_ref, u_ref = load_snapshot(ref_path, delimiter=",")
			if snapshot_paths:
				x, u = load_snapshot(snapshot_paths[0], delimiter=",")
				if x.shape == x_ref.shape:
					metrics = compute_error_metrics(u, u_ref)
					err = np.abs(u - u_ref)
					err_plot_path = run_dir / "error_plot.png"
					plot_error(x, err, title="Pointwise error", save_path=err_plot_path)
					print(f"[viz] Error metrics L1={metrics.l1:.3e}, L2={metrics.l2:.3e}, Linf={metrics.linf:.3e}")
					print(f"[viz] Saved error plot to {err_plot_path}")
				else:
					print("[viz] Snapshot and reference shapes differ; skipping error plot.")
		except Exception as exc:  # pylint: disable=broad-except
			print(f"[viz] Failed to compute error with reference: {exc}")

	# Convergence plot if a convergence.csv exists
	conv_path = run_dir / "convergence.csv"
	if conv_path.exists():
		try:
			data = np.loadtxt(conv_path, delimiter=",")
			if data.ndim == 2 and data.shape[1] >= 2:
				dx = data[:, 0]
				err = data[:, 1]
				conv_plot_path = run_dir / "convergence_plot.png"
				rate = plot_convergence(dx, err, title="Convergence", save_path=conv_plot_path)
				print(f"[viz] Estimated convergence rate: {rate:.2f}")
				print(f"[viz] Saved convergence plot to {conv_plot_path}")
			else:
				print("[viz] convergence.csv has unexpected shape; skipping.")
		except Exception as exc:  # pylint: disable=broad-except
			print(f"[viz] Failed to plot convergence: {exc}")

	# Energy plot if energy.csv exists
	energy_path = run_dir / "energy.csv"
	if energy_path.exists():
		try:
			data = np.loadtxt(energy_path, delimiter=",", skiprows=1)
			if data.ndim == 1:
				data = data.reshape(1, -1)
			if data.shape[1] >= 3:
				steps = data[:, 0]
				times = data[:, 1]
				energy = data[:, 2]
				fig, ax = plt.subplots()
				ax.plot(times, energy, label="energy")
				ax.set_xlabel("time")
				ax.set_ylabel("energy")
				ax.set_title("Energy vs time")
				ax.grid(True)
				ax.legend()
				out_path = run_dir / "energy_plot.png"
				fig.savefig(out_path, bbox_inches="tight")
				plt.close(fig)
				print(f"[viz] Saved energy plot to {out_path}")
			else:
				print("[viz] energy.csv has unexpected shape; skipping energy plot.")
		except Exception as exc:  # pylint: disable=broad-except
			print(f"[viz] Failed to plot energy: {exc}")


def create_animation(snapshot_paths: List[Path], *, save_path: Path) -> None:
	"""Create an MP4 animation from ordered snapshot CSVs."""

	frames: List[Tuple[np.ndarray, np.ndarray]] = []
	for path in sorted(snapshot_paths, key=lambda p: p.name):
		x, u = load_snapshot(path, delimiter=",")
		frames.append((x, u))

	if not frames:
		raise ValueError("No frames to animate")

	fig, ax = plt.subplots()
	line, = ax.plot(frames[0][0], frames[0][1])
	ax.set_xlim(frames[0][0].min(), frames[0][0].max())
	ax.set_ylim(min(f[1].min() for f in frames), max(f[1].max() for f in frames))
	ax.set_xlabel("x")
	ax.set_ylabel("u")
	ax.set_title("Wave propagation")
	ax.grid(True)

	def init():
		line.set_data(frames[0][0], frames[0][1])
		return (line,)

	def update(frame_idx: int):
		x, u = frames[frame_idx]
		line.set_data(x, u)
		return (line,)

	anim = animation.FuncAnimation(
		fig,
		update,
		init_func=init,
		frames=len(frames),
		interval=150,
		blit=True,
	)

	# Try to save MP4; fallback to GIF if ffmpeg unavailable
	try:
		anim.save(save_path, writer="ffmpeg", dpi=120)
	except Exception:
		gif_path = save_path.with_suffix(".gif")
		anim.save(gif_path, writer="pillow", dpi=120)
	plt.close(fig)

