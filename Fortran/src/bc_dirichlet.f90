subroutine apply_bc(u, nx)
  use iso_fortran_env, only: real64
  implicit none
  integer, intent(in) :: nx
  real(real64), intent(inout) :: u(nx)

  u(1) = 0.0_real64
  u(nx) = 0.0_real64
end subroutine apply_bc
