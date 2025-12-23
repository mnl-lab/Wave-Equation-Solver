subroutine apply_bc(u, nx)
  use iso_fortran_env, only: real64
  implicit none
  integer, intent(in) :: nx
  real(real64), intent(inout) :: u(nx)

  if (nx < 2) return

  u(1) = u(2)
  u(nx) = u(nx - 1)
end subroutine apply_bc
