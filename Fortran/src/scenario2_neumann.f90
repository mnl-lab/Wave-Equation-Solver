program scenario2_neumann
  ! Compile with bc_neumann.f90 to enforce Neumann boundaries.
  use iso_fortran_env, only: real64
  use initial_conditions
  use solver_core
  use input_io
  implicit none

  character(len=256) :: input_file
  integer :: nx, nsteps, snapshot_freq
  real(real64) :: dx, dt, c, t_final
  real(real64), allocatable :: u_prev(:), u_curr(:)

  nx = 201
  dx = 0.01_real64
  c = 1.0_real64
  dt = 0.005_real64
  t_final = 1.0_real64
  snapshot_freq = 50

  call get_command_argument(1, input_file)
  if (len_trim(input_file) == 0) input_file = 'input.json'

  call load_input(trim(input_file), nx, dx, dt, t_final, c, snapshot_freq)

  nsteps = int(t_final / dt)
  if (nsteps < 1) then
     print *, 'No steps to run. Check dt and t_final.'
     stop
  end if

  allocate(u_prev(nx), u_curr(nx))
  call set_initial_conditions(u_prev, u_curr, nx, dx)

  call run_wave(u_prev, u_curr, nx, dt, dx, c, nsteps, snapshot_freq)

  print *, 'Scenario 2 (Neumann) simulation finished.'
  deallocate(u_prev, u_curr)
end program scenario2_neumann
