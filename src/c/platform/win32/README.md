# platform/win32 - the Windows 11 front end (stage J, docs/67)

`pacman_a8_play.exe`: a window, the keyboard and XInput pads, and the sound device around the same `Shell`, renderer and sound model as the headless `pacman_a8`. Plain Win32 (owner decision, 2026-11-24): `user32`, `gdi32`, WASAPI through `ole32` and `mmdevapi`; no third-party library. Windows only (`if(WIN32)` in `platform/CMakeLists.txt`).

| File | What |
|---|---|
| `win_main.c` | `WinMain`: the window (1.6 : 1 picture, whole-number scale where it fits, black around it, F11 / Alt+Enter full screen), the pause menu and graphics options (docs/68), keys and pads to `FrontKeys`, the frame clock (the sound device's buffer, or the system timer with `--no-audio`), the replay recorder (`--record`), the self test (`--selftest FRAMES`, `--menutest`) |
| `win_gl.[ch]` | the CRT shaders (docs/70): an OpenGL 4.5 context in a child window and the runtime of the libretro slang presets (the passes, framebuffers, feedback, lookup textures); `render/slang.[ch]` and `render/png.[ch]` read the presets, the shaders and the PNG tables |
| `win_audio.[ch]` | WASAPI shared mode at 44,100 Hz (`wa_*`), and the loopback capture the self test measures with (`wl_*`: this process's sound only, Windows 10 2004 and later; the endpoint's whole mix otherwise) |

The input logic (what keys become the joystick, console and pause key of the Atari) is portable C99 in `shell/frontend.[ch]`, tested by `ctest frontend_check`. `tools/check_front_end.py` runs the whole front end against the headless shell.

```
pacman_a8_play [--root DIR] [--fps N|native|uncapped] [--crt off|guest|zfast|aperture] [--no-audio] [--seed N] [--record FILE] [--ppm FILE]
```

The game **always starts in borderless fullscreen**, at the resolution of the list (docs/68) that is the monitor's size or the nearest to it, and at the FPS (docs/69) that is its refresh rate or the nearest number. Test options: `--windowed [--scale N]`, `--trace FILE`, `--selftest FRAMES`, `--menutest`, `--startuptest`, `--crttest`, `--exact`.

Keys: arrows / WASD stick; Ctrl, Z, X, Enter fire (Enter is also START); F1 help (what the function keys do); F2 START, F3 SELECT, F4 OPTION; Space or P pause; Alt+Enter or F11 full screen; Esc the pause menu (Resume Game, Graphics Options with Display Mode, Resolution and FPS, Quit Game: docs/68, docs/69). Pads: D-pad or left stick; A / B fire; Start = START, Back = SELECT, X / Y = OPTION; pad 2 is player 2; the keyboard drives both ports. In the menu the pad's D-pad or stick moves, A selects, B goes back; Start + Back together open it.

Windows keeps a mute and a volume for each program **by its name** in the volume mixer. If `pacman_a8_play.exe` is muted there it is silent whatever it plays; the program writes a line to `logs/shell.log` when it finds that, and never changes the player's mixer. The self test therefore runs under its own name (`tools/check_front_end.py` copies the program to `pacman_a8_selftest.exe`) and at a low volume.
