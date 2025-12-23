module input_io
  use iso_fortran_env, only: real64
  implicit none
  public :: load_input
contains
  subroutine load_input(filename, nx, dx, dt, t_final, c, snapshot_freq)
    character(len=*), intent(in) :: filename
    integer, intent(inout) :: nx, snapshot_freq
    real(real64), intent(inout) :: dx, dt, t_final, c
    character(len=256) :: line
    integer :: ios, unit

    unit = 11
    open(unit=unit, file=filename, status='old', action='read', iostat=ios)
    if (ios /= 0) then
       print *, 'Warning: input file not found. Using defaults.'
       return
    end if

    do
       read(unit,'(A)', iostat=ios) line
       if (ios /= 0) exit
       if (index(line, '"nx"') > 0) call read_number_after_colon(line, nx)
       if (index(line, '"dx"') > 0) call read_number_after_colon(line, dx)
       if (index(line, '"dt"') > 0) call read_number_after_colon(line, dt)
       if (index(line, '"t_final"') > 0) call read_number_after_colon(line, t_final)
       if (index(line, '"wave_speed"') > 0) call read_number_after_colon(line, c)
       if (index(line, '"snapshot_freq"') > 0) call read_number_after_colon(line, snapshot_freq)
       if (index(line, '"output_frequency"') > 0) call read_number_after_colon(line, snapshot_freq)
    end do

    close(unit)
  end subroutine load_input

  subroutine read_number_after_colon(str, value)
    character(len=*), intent(in) :: str
    class(*), intent(inout) :: value
    integer :: pos, ios_local

    pos = index(str, ':')
    if (pos <= 0) return

    select type (value)
    type is (integer)
       read(str(pos + 1:), *, iostat=ios_local) value
    type is (real(real64))
       read(str(pos + 1:), *, iostat=ios_local) value
    class default
       ! Unsupported type; ignore.
    end select
  end subroutine read_number_after_colon
end module input_io
