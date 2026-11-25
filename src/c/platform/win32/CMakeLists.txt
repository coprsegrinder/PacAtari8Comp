# the Windows 11 front end (stage J, docs/67): a window, keyboard / XInput pad and the WASAPI sound device around the shell; only on Windows
add_executable(pacman_a8_play WIN32 win_main.c win_audio.c win_gl.c win_pad.c win_toast.c)
# the application manifest (UTF-8 code page, Windows 10 / 11, no elevation): compiled with windres run in this folder (the resource compiler of CMake passes the include folders unquoted, and the main folder's name has spaces)
find_program(PM_WINDRES NAMES windres llvm-windres)
if(PM_WINDRES)
  set(PM_RC_OBJ ${CMAKE_CURRENT_BINARY_DIR}/pacman_a8_play_rc.o)
  add_custom_command(OUTPUT ${PM_RC_OBJ} COMMAND ${PM_WINDRES} -O coff -i pacman_a8_play.rc -o ${PM_RC_OBJ} WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                     DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/pacman_a8_play.rc ${CMAKE_CURRENT_SOURCE_DIR}/pacman_a8_play.manifest VERBATIM)
  target_sources(pacman_a8_play PRIVATE ${PM_RC_OBJ})
else()
  message(WARNING "windres not found: the program is built without its manifest (paths with characters outside the system's ANSI code page will not work)")
endif()
target_link_libraries(pacman_a8_play pm_shell pm_render pm_audio pm_assets pm_app pm_core pm_platform user32 gdi32 ole32 uuid mmdevapi opengl32 hid setupapi comdlg32)
