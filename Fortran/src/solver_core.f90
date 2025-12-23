module solver_core
  use iso_fortran_env, only: real64
  implicit none
  private
  public :: run_wave, write_snapshot, compute_energy, append_energy

  ! Explicit interface to the boundary condition hook.
  interface
     subroutine apply_bc(u, nx)
       import :: real64
       integer, intent(in) :: nx
       real(real64), intent(inout) :: u(nx)
     end subroutine apply_bc
  end interface

contains

   subroutine run_wave(u_prev, u_curr, nx, dt, dx, c, nsteps, snapshot_freq)
      integer, intent(in) :: nx, nsteps, snapshot_freq
    real(real64), intent(in) :: dt, dx, c
    real(real64), intent(inout) :: u_prev(nx), u_curr(nx)
    real(real64) :: u_next(nx)
      real(real64) :: coef, time, energy
      integer :: i, step, snap_stride

    u_next = u_curr
    coef = (c * dt / dx) ** 2
    time = 0.0_real64

   snap_stride = max(1, snapshot_freq)

   do step = 1, nsteps
       ! Interior finite-difference stencil.
       do i = 2, nx - 1
          u_next(i) = 2.0_real64 * u_curr(i) - u_prev(i) + coef * &
                      (u_curr(i + 1) - 2.0_real64 * u_curr(i) + u_curr(i - 1))
       end do

       call apply_bc(u_next, nx)

       u_prev = u_curr
       u_curr = u_next
       time = time + dt

       if (mod(step, snap_stride) == 0) then
          call write_snapshot(u_curr, nx, step, dx)
          energy = compute_energy(u_next, u_curr, nx, dx, dt, c)
          call append_energy(step, time, energy)
       end if
    end do
  end subroutine run_wave

  subroutine write_snapshot(u, nx, step, dx)
    integer, intent(in) :: nx, step
    real(real64), intent(in) :: u(nx), dx
    character(len=64) :: filename
    integer :: i

    filename = 'snapshot_' // trim(adjustl(itoa(step))) // '.csv'
    open(unit=10, file=filename, status='replace')
    write(10,'(A)') 'x,u'
    do i = 1, nx
       write(10,'(F12.6,",",F12.6)') real(i - 1, real64) * dx, u(i)
    end do
    close(10)
  end subroutine write_snapshot

  function compute_energy(u_next, u_curr, nx, dx, dt, c) result(E)
    integer, intent(in) :: nx
    real(real64), intent(in) :: dx, dt, c
    real(real64), intent(in) :: u_next(nx), u_curr(nx)
    real(real64) :: E
    real(real64) :: vel, dudx
    integer :: i

    E = 0.0_real64

    do i = 2, nx - 1
       vel = (u_next(i) - u_curr(i)) / dt
       E = E + 0.5_real64 * vel * vel
    end do

    do i = 1, nx - 1
       dudx = (u_curr(i + 1) - u_curr(i)) / dx
       E = E + 0.5_real64 * c * c * dudx * dudx
    end do

    E = E * dx
  end function compute_energy

  subroutine append_energy(step, time, energy)
    integer, intent(in) :: step
    real(real64), intent(in) :: time, energy
    logical, save :: initialized = .false.
    integer, parameter :: unit = 20

    if (.not. initialized) then
       open(unit=unit, file='energy.csv', status='replace')
       write(unit,'(A)') 'step,time,energy'
       initialized = .true.
    else
       open(unit=unit, file='energy.csv', status='old', position='append')
    end if

    write(unit,'(I10,",",F18.10,",",F18.10)') step, time, energy
    close(unit)
  end subroutine append_energy

  function itoa(i) result(str)
    integer, intent(in) :: i
    character(len=20) :: str
    write(str,'(I0)') i
  end function itoa

end module solver_core
