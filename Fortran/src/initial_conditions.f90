module initial_conditions
  use iso_fortran_env, only: real64
  implicit none
contains
  subroutine set_initial_conditions(u_prev, u_curr, nx, dx)
    ! Simple initial wave: u(x,0) = sin(pi*x/L)
    integer, intent(in) :: nx
    real(real64), intent(in) :: dx
    real(real64), intent(out) :: u_prev(nx), u_curr(nx)
    integer :: i
    real(real64) :: x, L

    L = dx * real(nx - 1, real64)

    do i = 1, nx
        x = real(i - 1, real64) * dx
        u_curr(i) = sin(3.141592653589793_real64 * x / L)
        u_prev(i) = u_curr(i)  ! initial velocity = 0
    end do
  end subroutine set_initial_conditions
end module initial_conditions
