module boundaries
  implicit none
contains
  subroutine apply_dirichlet(u, nx)
    integer, intent(in) :: nx
    real(8), intent(inout) :: u(nx)
    u(1) = 0.0
    u(nx) = 0.0
  end subroutine apply_dirichlet
end module boundaries
