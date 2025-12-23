program main
  use iso_fortran_env, only: int32, real64
  use initial_conditions
  use solver
  implicit none

  ! JSON parsing variables
  character(len=256) :: line
  character(len=256) :: filename
  integer :: ios
  integer :: nx, nsteps, snapshot_freq
  real(real64) :: dx, dt, c, t_final
  real(real64), allocatable :: u_prev(:), u_curr(:)

  ! Default / placeholder values in case JSON fails
  nx = 201
  dx = 0.01
  c = 1.0
  dt = 0.005
  t_final = 1.0
  snapshot_freq = 50

  ! JSON input file
   filename = 'input.json'

  ! --- Simple JSON parsing ---
  open(unit=10, file=filename, status='old', action='read', iostat=ios)
  if (ios /= 0) then
     print *, "Warning: input.json not found, using defaults"
  else
     do
        read(10,'(A)', iostat=ios) line
        if (ios /= 0) exit
      if (index(line, '"nx"') > 0) call read_number_after_colon(line, nx)
      if (index(line, '"dx"') > 0) call read_number_after_colon(line, dx)
      if (index(line, '"dt"') > 0) call read_number_after_colon(line, dt)
      if (index(line, '"t_final"') > 0) call read_number_after_colon(line, t_final)
      if (index(line, '"wave_speed"') > 0) call read_number_after_colon(line, c)
      if (index(line, '"snapshot_freq"') > 0) call read_number_after_colon(line, snapshot_freq)
     end do
     close(10)
  end if

  ! Compute number of time steps
  nsteps = int(t_final / dt)

  ! Allocate arrays
  allocate(u_prev(nx), u_curr(nx))

  ! Initialize
  call set_initial_conditions(u_prev, u_curr, nx, dx)

  ! Run Dirichlet solver
  call run_dirichlet(u_prev, u_curr, nx, dt, dx, c, nsteps, snapshot_freq)

   print *, 'Scenario 1 simulation finished!'
   deallocate(u_prev, u_curr)

contains

   subroutine read_number_after_colon(str, value)
      ! Parse the substring after the first ':' using list-directed read.
      character(len=*), intent(in) :: str
      class(*), intent(inout) :: value
      integer :: pos, ios_local

      pos = index(str, ':')
      if (pos <= 0) return

      select type (value)
      type is (integer)
          read(str(pos+1:), *, iostat=ios_local) value
      type is (real(real64))
          read(str(pos+1:), *, iostat=ios_local) value
      class default
          ! Unsupported type; no-op
      end select
   end subroutine read_number_after_colon

end program main
