module initial_conditions
  implicit none
contains
  subroutine set_initial_conditions(u_prev, u_curr, nx, dx)
    ! Simple initial wave: u(x,0) = sin(pi*x/L)
    integer, intent(in) :: nx
    real(8), intent(in) :: dx
    real(8), intent(out) :: u_prev(nx), u_curr(nx)
    integer :: i
    real(8) :: x, L
    L = dx * (nx-1)

    do i = 1, nx
        x = (i-1) * dx
        u_curr(i) = sin(3.141592653589793*x/L)
        u_prev(i) = u_curr(i)  ! initial velocity = 0
    end do
  end subroutine set_initial_conditions
end module initial_conditions
