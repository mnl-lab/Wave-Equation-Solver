## Wave-Equation-Solver

Numerical solver for the 1D wave equation with selectable boundary conditions, written in modern Fortran with a Python front-end for parameter collection, execution, and visualization. The goal is to provide a reproducible testbed that links theory (finite differences, CFL stability) to a lean, cache-friendly implementation suitable for teaching and quick experimentation.

![Demo](little_demo.gif)

---

### Mathematical Model and Discretization
- Governing PDE: $\partial_{tt} u = c^2\, \partial_{xx} u$ on $x \in [0, L]$, $t \ge 0$.
- Boundary conditions:
	- Dirichlet: $u(0, t) = u(L, t) = 0$ (fixed ends).
	- Neumann: $\partial_x u(0, t) = \partial_x u(L, t) = 0$ (free ends).
- Spatial discretization (second-order central difference): $\partial_{xx} u(x_i, t^n) \approx \dfrac{u_{i+1}^n - 2u_i^n + u_{i-1}^n}{\Delta x^2}$.
- Time integration (explicit, three-layer second-order scheme): $u_i^{n+1} = 2u_i^n - u_i^{n-1} + \lambda^2\,(u_{i+1}^n - 2u_i^n + u_{i-1}^n)$ with Courant number $\lambda = c\, \dfrac{\Delta t}{\Delta x}$.
- CFL stability requirement: $\lambda \le 1$; pick $\Delta t \le \dfrac{\Delta x}{c_{\max}}$, where $c_{\max}$ is the maximum wave speed used in a scenario.

### How the Theory Maps to the Code
- Three time layers: `u_prev`, `u_curr`, `u_next` in [Fortran/src/solver_core.f90](Fortran/src/solver_core.f90) implement the explicit update above; `u_next` is filled from the interior stencil, boundary conditions are applied, then the layers rotate (`u_prev <- u_curr`, `u_curr <- u_next`).
- Boundary conditions via a lightweight hook:
	- Dirichlet: [Fortran/src/bc_dirichlet.f90](Fortran/src/bc_dirichlet.f90) assigns endpoints to zero each step (fixed displacement).
	- Neumann: [Fortran/src/bc_neumann.f90](Fortran/src/bc_neumann.f90) mirrors the interior into ghost-like endpoints (`u(1)=u(2)`, `u(nx)=u(nx-1)`) to enforce zero gradient.
	- The solver calls an `apply_bc` interface after the interior stencil, keeping the time integrator independent of the boundary choice.
- Memory layout and performance choices (Fortran-side):
	- Arrays are statically sized within each time step (`u_next(nx)`) and allocated once per program in [Fortran/src/scenario1_dirichlet.f90](Fortran/src/scenario1_dirichlet.f90) and [Fortran/src/scenario2_neumann.f90](Fortran/src/scenario2_neumann.f90); no dynamic allocation occurs inside the main loop.
	- Contiguous `real(real64)` arrays and a single, stride-1 loop over `i=2..nx-1` keep the stencil cache-friendly.
	- Boundary handling is a small, separate pass to avoid branching inside the hot stencil loop.
- Initial conditions: [Fortran/src/initial_conditions.f90](Fortran/src/initial_conditions.f90) seeds both `u_prev` and `u_curr` with a sine profile and zero initial velocity.
- Diagnostics and I/O:
	- Snapshots every `snapshot_freq` steps: `write_snapshot` in [Fortran/src/solver_core.f90](Fortran/src/solver_core.f90) writes `x,u` CSV files.
	- Energy log: `compute_energy` and `append_energy` track discrete kinetic and potential energy in the same module.
	- Input overrides: [Fortran/src/input_io.f90](Fortran/src/input_io.f90) reads a minimal JSON file to update `nx`, `dx`, `dt`, `t_final`, `c`, and `snapshot_freq`.

### Repository Layout
- Core solver (Fortran)
	- [Fortran/src/solver_core.f90](Fortran/src/solver_core.f90): time integrator, snapshots, energy.
	- [Fortran/src/bc_dirichlet.f90](Fortran/src/bc_dirichlet.f90), [Fortran/src/bc_neumann.f90](Fortran/src/bc_neumann.f90): boundary hooks.
	- [Fortran/src/initial_conditions.f90](Fortran/src/initial_conditions.f90): initial wave shape.
	- [Fortran/src/input_io.f90](Fortran/src/input_io.f90): JSON-style parameter overrides.
	- [Fortran/src/scenario1_dirichlet.f90](Fortran/src/scenario1_dirichlet.f90), [Fortran/src/scenario2_neumann.f90](Fortran/src/scenario2_neumann.f90): scenario-specific drivers that select the boundary hook and allocate arrays.
- Python front-end
	- [Python/config.py](Python/config.py): default parameters, CFL-based `dt` computation, schema versioning.
	- [Python/tui.py](Python/tui.py): text UI to collect parameters, enforce CFL, and call the runner.
	- [Python/runner.py](Python/runner.py): writes `input.json`, builds the correct Fortran executable if missing, runs it, and organizes outputs under `outputs/`.
	- [Python/visualize.py](Python/visualize.py): snapshot/energy plotting, optional animations and convergence plots.
	- [Python/input.json](Python/input.json): example parameter file (Dirichlet, CFL=0.9, dx=0.01).
- Reports and figures
	- [Python/outputs/](Python/outputs/) contains timestamped run artifacts (snapshots `*snapshot_*.csv`, energy logs `*energy*.csv`, generated plots/animations); add `little_demo.gif` here when available.

### Dependencies
- Fortran toolchain: `gfortran` (or compatible) on PATH to build solver executables.
- Python 3.10+ packages: `numpy`, `matplotlib`, `pillow` (visualization and GIF fallback). Install via:
```sh
 `pip install numpy matplotlib pillow`.
- Optional: `ffmpeg` on PATH for MP4 animation output; if missing, GIFs are produced via Pillow.
```
### Building and Running
Prerequisites: gfortran (or a compatible Fortran compiler), Python 3.10+ with numpy/matplotlib for visualization.

**Recommended: Python TUI + runner (auto-build if needed):**
```sh
cd Python
python tui.py
```

**Build Fortran executables (manual):**
```sh
cd Fortran/src
gfortran -O2 solver_core.f90 input_io.f90 initial_conditions.f90 bc_dirichlet.f90 scenario1_dirichlet.f90 -o solver_dirichlet.exe
gfortran -O2 solver_core.f90 input_io.f90 initial_conditions.f90 bc_neumann.f90 scenario2_neumann.f90 -o solver_neumann.exe
```

**Run a scenario directly (for a prepared input file):**
```sh
./solver_dirichlet.exe input.json   # or .\solver_dirichlet.exe on Windows
```
Steps performed:
1) Prompt for scenario (1=Dirichlet, 2=Neumann) and numerical parameters.
2) Enforce CFL guidance and adjust `t_final` to be an integer multiple of `dt`.
3) Write a schema-stable `input.json` into a timestamped `outputs/run-...` folder.
4) Build the appropriate Fortran executable if it is not present, then run it.
5) Auto-visualize snapshots/energy if produced.

Outputs location: after each run, all artifacts (input copy, snapshots, energy CSV, plots) are placed under [Python/outputs/](Python/outputs/) in a timestamped subfolder such as `run-s1-nx200-dx0p01-dt0p009-f10-YYYYMMDD-HHMMSS/`.

**Programmatic run (bypassing the TUI):**
```python
from runner import run_solver
params = {"scenario_id": 1, "nx": 200, "dx": 0.01, "cfl": 0.9, "wave_speed": 1.0, "t_final": 1.0}
result = run_solver(params)
print(result["run_dir"], result["outputs"])
```

### Configuring Parameters
- Key fields (JSON/TUI): `scenario_id` (1=Dirichlet, 2=Neumann), `nx`, `dx`, `L`, `wave_speed` (or `c_max`), `cfl`, `t_final`, `output_frequency`/`snapshot_freq`.
- Time step: `dt` is inferred from CFL in the Python front-end (`dt = cfl * dx / c_max` or `wave_speed`); if you edit `dt` manually in `input.json`, ensure $c\, dt / dx \le 1$.
- Outputs: snapshots every `snapshot_freq` steps; energy log when snapshots are taken.
- Run folders: created as `outputs/run-s<scenario>-nx<...>-dx<...>-dt<...>-f<freq>-YYYYMMDD-HHMMSS/` with input and generated CSVs inside.

### Visualization and Diagnostics
- Snapshots: CSV files `*snapshot_*.csv` with columns `x,u`; use [Python/visualize.py](Python/visualize.py) or the auto-visualizer triggered by the TUI.
- Energy: `*energy.csv` holds `(step,time,energy)`; the visualizer plots energy vs time if present.
- Animation: when multiple snapshots exist, `visualize.create_animation` builds an MP4 or GIF.
- CFL reporting: choose `cfl <= 1`; the Python front-end reports the implied `dt` and coerces `t_final` to align with the time grid.

### Extensibility
- The solver is structured for additional scenarios: higher-order stencils, variable material properties, source terms, damping models, or different boundary operators can be added by supplying new `apply_bc` hooks and scenario drivers.

### Reproducibility Notes
- Deterministic: no random sources; outputs depend only on the input JSON.
- Fixed precision: all computations use `real(real64)`.
- Minimal side effects: no dynamic allocation inside time loops; boundary hooks and diagnostics are isolated for clarity and performance.