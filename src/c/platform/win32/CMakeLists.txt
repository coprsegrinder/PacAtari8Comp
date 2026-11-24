# the Windows 11 front end (stage J, docs/67): a window, keyboard / XInput pad and the WASAPI sound device around the shell; only on Windows
add_executable(pacman_a8_play WIN32 win_main.c win_audio.c win_gl.c)
target_link_libraries(pacman_a8_play pm_shell pm_render pm_audio pm_assets pm_app pm_core pm_platform user32 gdi32 ole32 uuid mmdevapi opengl32)
