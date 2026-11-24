# 67 - The Windows 11 front end (stage J)

Stage J of `PROGRESS.md`: "Native Windows 11 port" - the playable program. `pacman_a8_play.exe` is a window, keyboard and pad input, and a sound device around the **same** game the headless `pacman_a8` runs. Owner decision of 2026-11-24 (decision D3 left the library to this stage): **plain Win32**, no third-party library (`user32`, `gdi32`, WASAPI through `ole32` / `mmdevapi`). Source: `src/c/platform/win32/` (`win_main.c`, `win_audio.[ch]`) and the portable input logic `src/c/shell/frontend.[ch]`. Nothing here changes the game: the front end only does what the Atari's hardware and OS did around it.

## 1. What it does

| Part | How |
|---|---|
| **Input** (`shell/frontend.c`, portable, `ctest frontend_check`) | Keys and pads of the moment become the `FrameInput` of the frame: the stick is four switches (a direction and its opposite together give neither), the trigger and the console keys are 0 when pressed, the pause key is a **press** (the OS keyboard interrupt stores `$21` in `CH` once and sets `KEYDEL` = 3, which counts down once a frame; the game accepts it at 0 and clears `CH` itself: docs/41, docs/45), the OS clock counts one a frame, attract mode never engages, RANDOM comes from the model with a seed taken from the clock (`--seed` fixes it) |
| **Frame clock** | **The sound device**: the game runs a frame whenever the device has less than about two frames (1,500 samples) queued, so picture and sound cannot drift apart; the pace is the original's 59.92 frames a second (44,100 Hz / 735.99 samples a frame). With `--no-audio`, or when there is no device: the system timer at 59.9227 Hz |
| **Picture** | The renderer's 384 x 240 pixels, drawn with `StretchDIBits` (no smoothing) at the 4:3 shape of the original's picture, centred with black bars; `--scale N`, `--fullscreen`, F11 / Alt+Enter |
| **Sound** | WASAPI shared mode, float, 44,100 Hz, a 100 ms buffer, the mono sound on both channels; Windows converts when the mix format differs |
| **Pads** | XInput, loaded when the program starts (no import library, no failure without it); pad 1 is player 1, pad 2 player 2; the keyboard drives both ports (hot-seat play on one keyboard) |
| **Save and record** | The high score under `save/` through `platform/fs.c` like the headless shell; `--record FILE` writes the game played as a replay |

Keys: arrows / WASD stick; Ctrl, Z, X, Enter fire (Enter is also START); F2 START, F3 SELECT, F4 OPTION; Space or P pause; Alt+Enter or F11 full screen; Esc quit. Pads: D-pad or left stick, A / B fire, Start = START, Back = SELECT, X / Y = OPTION.

## 2. How it was checked (`tools/check_front_end.py`, `analysis/evidence-front-end-summary.txt`)

The self test (`--selftest 1200 --exact`) plays a scenario by **posting real key messages to its own window** (START, the four directions with the arrows and with WASD, the pause key twice), for 1,200 frames, with the real sound device as the clock, and records the game it played. For each compiler (gcc 14.2, clang 19.1) built from scratch (strict C99, `-Werror`, 0 warnings):

| Claim | Result |
|---|---|
| **The front end adds nothing to the game, the picture or the sound**: the recorded game, run by the headless `pacman_a8 run --video --audio`, gives the same final state hash, run digest, video digest and audio digest | equal, both compilers, both clocks |
| **The window shows the frame**: the window's own pixels, copied back out of the screen, equal the frame | 0 of 92,160 differ |
| **The device never ran dry**; no gap between pictures over 40 ms | 0 underruns, 0 gaps (mean interval 19 ms: the loop draws once a batch) |
| **The pace is the original's** | 60.06 to 60.08 frames/s on the sound clock (the first two frames are the queue's lead), 59.90 on the timer; the original runs at 59.923 |
| **The device really played the sound it was given** (sound by measurement, owner rule): WASAPI loopback of this process alone, at a volume of 0.3 | loudness curves of 10 ms blocks correlate 0.985 to 0.991 (delay 40-50 ms: the device's queue), 1,629 of the 1,635 blocks with sound were played, level 0.996 of what was handed over |
| **The pause key** | recorded as exactly two presses (`CH` = `$21`); in the game, the pause starts exactly `KEYDEL` = 3 frames after the press and the resume likewise (`frontend_check`), and the recorded game replays to the same state |
| **The input logic** | `ctest frontend_check`: every stick value, opposite directions, buttons, console, `CH` / `KEYDEL` countdown, the clock wrap, START to a running game, pause and resume, record and replay |

## 3. What was found on the way

1. **A race in my own code, found by repetition.** The loopback measurement's activation handler lived on the caller's stack; Windows could still be inside it after the call returned. About one run in eight crashed at start-up. The handler is now heap-allocated with a reference count and freed by the last release; 40 runs in a row did not crash.
2. **Windows keeps a mute and a volume for each program by its name** in the volume mixer. The program name `pacman_a8_play.exe` was muted there (not by this project's code), so that program was silent whatever it played, and its own loopback saw zeros. The program now looks at its own mixer state when it starts and writes a line to `logs/shell.log` when it is muted; it **never changes the player's mixer**. The self test runs a byte-identical copy under its own name (`pacman_a8_selftest.exe`) at a low volume, so a mute the player set for the game does not disable the test, and the test does not blast the speakers. (Windows volume scalars are an audio taper: a scalar of 0.3 is an amplitude of 0.09, which the measurement allows for.)
3. **A loopback of the whole endpoint is not a measurement of the game**: other programs' sound is in it (the first attempts correlated at 0.47 to 0.59 for that reason). The measurement uses the process-only loopback (Windows 10 version 2004 and later) and says in its report which scope it had.

## 4. Limits (OV-75, OV-76)

- **No person played it.** Everything above is measured from the program's own signals and a loopback capture; how it feels in the hand, and what the speakers make of the sound, is not measured.
- **No pad was tried** (none is attached here): the XInput path loads and reports no pad; the button mapping is from the code.
- **Full screen** (F11, Alt+Enter) and window sizes other than the exact 384 x 240 were not measured; the 4:3 stretch is by nearest pixel, so at most scales some pixel columns are one pixel wider than others (the original's pixels were not square either).
- **One unexplained observation**: the first self test of the session had 8,916 of 92,160 window pixels differing from the frame; the 24 later runs (all of `check_front_end`'s and the manual ones) had 0. A partly covered window at start is the likely cause; it was not reproduced and not proved.
- NTSC only (as the whole port); Windows 11 on one machine, one sound device; gcc and clang (MinGW-w64 / WinLibs), not MSVC.
- The self test needs a display, a sound device and a Windows that has the process loopback; the game itself does not need the loopback.
