module solver
  use boundaries
  implicit none
contains
  subroutine run_dirichlet(u_prev, u_curr, nx, dt, dx, c, nsteps, snapshot_freq)
    integer, intent(in) :: nx, nsteps, snapshot_freq
    real(8), intent(in) :: dt, dx, c
    real(8), intent(inout) :: u_prev(nx), u_curr(nx)
    real(8) :: u_next(nx)
    integer :: i, step
    real(8) :: coef, time, energy

    coef = (c*dt/dx)**2
    time = 0.0d0

    do step = 1, nsteps
        ! Interior points
        do i = 2, nx-1
            u_next(i) = 2.0*u_curr(i) - u_prev(i) + coef * &
                        (u_curr(i+1) - 2.0*u_curr(i) + u_curr(i-1))
        end do

        call apply_dirichlet(u_next, nx)

        ! Swap arrays
        u_prev = u_curr
        u_curr = u_next
        time = time + dt

        ! Write snapshot
          if (mod(step, snapshot_freq) == 0) then
            call write_snapshot(u_curr, nx, step, dx)
        end if

        ! Energy diagnostic (same cadence as snapshots)
        if (mod(step, snapshot_freq) == 0) then
            energy = compute_energy(u_next, u_curr, nx, dx, dt, c)

            call append_energy(step, time, energy)
        end if
    end do
  end subroutine run_dirichlet

  subroutine write_snapshot(u, nx, step, dx)
    integer, intent(in) :: nx, step
    real(8), intent(in) :: u(nx), dx
    character(len=50) :: filename
    integer :: i
    filename = 'snapshot_'//trim(adjustl(itoa(step)))//'.csv'
    open(unit=10, file=filename, status='replace')
    write(10,'(A)') 'x,u'
    do i = 1, nx
        write(10,'(F12.6,",",F12.6)') (i-1)*dx, u(i)
    end do
    close(10)
  end subroutine write_snapshot

  function compute_energy(u_next, u_curr, nx, dx, dt, c) result(E)
    integer, intent(in) :: nx
    real(8), intent(in) :: dx, dt, c
    real(8), intent(in) :: u_next(nx), u_curr(nx)
    real(8) :: E
    real(8) :: vel, dudx
    integer :: i

    E = 0.0d0

    ! Kinetic energy (velocity at half-step)
    do i = 2, nx-1
      vel = (u_next(i) - u_curr(i)) / dt
      E = E + 0.5d0 * vel*vel
    end do

    ! Potential energy (discrete gradient)
    do i = 1, nx-1
      dudx = (u_curr(i+1) - u_curr(i)) / dx
      E = E + 0.5d0 * c*c * dudx*dudx
    end do

    E = E * dx
  end function compute_energy


  subroutine append_energy(step, time, energy)
    integer, intent(in) :: step
    real(8), intent(in) :: time, energy
    logical, save :: initialized = .false.
    integer :: unit
    unit = 20
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
end module solver
