# 68 - The pause menu, the graphics options and the help (an addition to stage J)

Asked for by the owner on 2026-11-24, after playing the stage J program (docs/67). `pacman_a8_play.exe` gets a pause menu on **Esc** and a graphics options page: the display mode and the resolution. Nothing of the game changes: while a menu is open the front end runs **no game frame at all**, so every gameplay process (movement, ghosts, timers, animation, sound) is stopped by not being called, and the World is never touched by the menu. Source: the portable model `src/c/shell/menu.[ch]` (`ctest menu_check`), and `src/c/platform/win32/win_main.c` (the window, the drawing and the keys).

## 1. What it does

| | |
|---|---|
| **Esc** | in the game: opens the **Pause Menu**; in the Pause Menu: resumes; in Graphics Options: back to the Pause Menu (on the item "Graphics Options") |
| **F1: the help** | from anywhere (in the game, in the Pause Menu, in the Graphics Options): shows **only what the function keys do**, no other controls: F1 this help, F2 start a new game, F3 one or two players, F4 starting level, F11 full screen / windowed. Like the menu it is a pause (no game frame runs). F1 again, or Esc, closes it and goes back to where it was (the game, or the menu on the same item); no other key does anything in it, except F11 |
| **Pause Menu** | Resume Game, Graphics Options, Quit Game |
| **Graphics Options** | **Display Mode**: Windowed / Borderless Fullscreen; **FPS** (added later, docs/69: native 59.92, 75 to 180, uncapped); **CRT Shader** (added later, docs/70: off, or one of three); **Resolution**: 20 standard resolutions, 5 of 4:3, 6 of 16:9, 5 of 16:10, 4 of 21:9 (640x480 ... 1600x1200; 1280x720 ... 3840x2160; 1280x800 ... 2560x1600; 2560x1080, 3440x1440, 3840x1600, 5120x2160). Nothing else (the FPS of docs/69 was added afterwards at the owner's request) |
| **Keys in the menu** | Up / Down (or W / S) move; Left / Right (or A / D) change a value; Enter or Space selects (and changes a value); Esc goes back. A pad: D-pad or left stick, A selects, B goes back; Start + Back together open the menu (a pad has no Esc) |
| **Changes** | take effect at once: the window changes mode and size while the menu is open, the game goes on where it was (the state hash is the same before the menu and after it: the tests) |
| **F11, Alt+Enter** | still toggle the display mode, in the game and in the menu (the menu shows the mode) |
| **Drawn** | into the 384 x 240 picture itself (the frame darkened, a panel, the text in the OS font of the renderer), so it scales with the picture |

**The display mode.** *Windowed*: a normal window whose client area is the selected resolution (as much of it as the monitor's work area has room for), centred on the monitor; the player can still drag and resize it, and the picture follows the client area. *Borderless fullscreen*: a frameless window over the whole monitor; the picture uses the **centred area of the selected resolution** (the monitor, when it is smaller than the selection), the rest is black. No video mode is switched (that is what "borderless" means), so changes are instant and cannot leave the screen in a wrong mode.

**The picture** (`display_fit`, tested for every list entry): the 384 x 240 image is 1.6 : 1 and **is never stretched**. In the available area it is drawn at the **largest whole-number scale** when that picture is at least **85 %** of the largest 1.6 : 1 picture that fits the area; otherwise it is scaled up (or down) **to fit** the area on the limiting side. It is centred in both directions, everything else is black, and the stretch is by nearest pixel (`StretchDIBits` with `COLORONCOLOR`: no smoothing, nothing blended). Examples: 1280 x 720 gives 3 x (1152 x 720); 1920 x 1080 gives 4 x (1536 x 960, 60 black lines top and bottom: 89 % of what fits); 1600 x 900 would give 3 x = 80 %, so it is fitted: 3.75 x (1440 x 900); 3440 x 1440 gives 6 x (2304 x 1440, black columns left and right); 640 x 480 is fitted at 1.66 x (640 x 400). With a fitted (non-whole) scale some source pixels are one screen pixel wider than others: the price of using the space. The 85 % is one constant (`MENU_FILL_PERCENT` in `menu.h`): 100 would use whole scales only (more black), a lower one fewer fitted scales.

**The game always starts in borderless fullscreen** (changed on 2026-11-24 at the owner's request), with the resolution of the list that is the monitor's size or the nearest to it (2560 x 1440 here: exactly the monitor's) and the FPS of docs/69 that is its refresh rate or the nearest. For the tests `--windowed` starts a window of 1280 x 720 (the list's 16:9 entry holding the 3 x picture), and `--windowed --scale N` a window of N x the picture (384N x 240N; "WINDOW" in the menu until a list entry is chosen). **Changed from stage J:** the picture was stretched to 4:3 (the shape of an Atari tube); it is now 1.6 : 1 as asked. **Esc no longer quits** (the menu's Quit Game or the window's close button do).

## 2. How it was checked

| Check | Where | Result |
|---|---|---|
| The key paths of the menu (open, resume, back, wrap-around, quit, mode, every resolution both ways) and the text it shows | `ctest menu_check` | pass |
| The list: no duplicate, each entry is the aspect it is filed under (16:9 with the usual 1366 x 768 panel), at least 3 of each | `menu_check` | pass |
| `display_fit` for **every** list entry as a client area: inside the area, centred, 1.6 : 1 to a pixel, a whole scale is exactly 1.6 : 1, it touches the area on one axis unless a whole scale is used; the worked examples above; an area smaller than the screen; an area bigger than the screen (clamped); a square area; an area smaller than the picture | `menu_check` | pass |
| **The real program** (`pacman_a8_play --menutest`, `tools/check_front_end.py`, gcc and clang from scratch, strict C99, -Werror): real key messages (Esc, arrows, Enter, F11, Alt+Enter) posted to the window while a game is being played; 71 checks | `analysis/evidence-front-end-summary.txt` | 71 passed, 0 failed, each compiler |
| **Frozen**: 700 ms with the menu open, and again after all the display changes: the frame count and the **hash of the whole state** equal what they were when the menu opened | `--menutest` | equal |
| **Resumed**: after Esc, and after Resume Game, the game runs again (the state changes) | `--menutest` | yes |
| Quit Game ends the program | `--menutest` | yes |
| **Every display mode and resolution**: for the 20 resolutions in windowed mode and the 20 in borderless fullscreen (45 pictures with the start-up and the F11 / Alt+Enter ones) the window's client size is what it should be (the resolution, or what the work area allows; the monitor in fullscreen), the window's pixels are **copied back out of the screen** and compared with the picture: nothing outside the picture rectangle is not black, every pixel inside is a pixel of the 384 x 240 image (for a whole scale: exactly the pixel the centre rule gives; for a fitted scale: one of the neighbouring source pixels at an edge, never a blend), aspect 1.6 : 1 to a pixel, centred | `--menutest` | all 45 |
| The mode: fullscreen = a window with no frame whose rectangle is the monitor's, windowed = a window with a frame inside the work area; F11 and Alt+Enter from both | `--menutest` | yes |
| **The menu adds nothing to the game**: the game recorded through the menu run by the headless `pacman_a8 run --video --audio` gives the same state, run, video and audio digests | `check_front_end.py` | equal |
| The rest of the front end: the stage J checks (22) again, and the 30 golden games | `check_front_end.py`, `run_regression.py` | pass |

**The help** (F1, added 2026-11-24): `menu_check` covers opening it from the game and from each menu, closing it with F1 and with Esc, that game keys do nothing in it, that every line of it is a function key's line (F1, F2, F3, F4, F11) and that no control word (arrows, WASD, fire, stick, Esc, Enter, Space, Ctrl, move, pause) is in it; `--menutest` presses the real F1 in the running game (frozen: the frame count and the state hash are unchanged over 500 ms; a game key does nothing; F1 again resumes) and in the Pause Menu (Esc closes it and the menu is as it was): 80 checks each compiler in all.

The pictures of the menu screens are made by the test (`logs/menu_main.ppm`, `logs/menu_graphics.ppm`, `logs/menu_help.ppm`).

## 3. Limits (OV-77)

- **One machine, one monitor** (2560 x 1440, 100 % scaling): the clamp of a resolution larger than the monitor is exercised (3840 x 2160, 5120 x 2160 and others on it: the window is made as large as the work area allows and the picture is fitted into that), but not with a monitor smaller than 1280 x 720, several monitors, or a Windows display scaling other than 100 % (the program is DPI-aware, so a scaled display gives real pixels).
- **A window larger than the monitor is clamped**, so on a monitor smaller than a resolution the menu shows the selected size but the window is the largest that fits.
- **The pad's menu keys were not tried** (no pad; the code path is the same `menu_event` the keyboard uses).
- **The menu was not looked at by a person** beyond the two pictures; how it feels is not measured.
- **The first run of the menu test (before `IsIconic` was handled)** ended with the window minimised in the middle of the resolution list (what minimised it was not found: an outside event such as a focus change is likely; the program now restores a minimised window before it sizes it); the 7 runs since (counting the two compilers of each full check) passed every check.
- The settings are **not saved** between runs (not asked for).
- **A decision for the owner**: the whole-number rule's 85 % (section 1): 1920 x 1080 uses 4 x with 60 black lines top and bottom rather than a fitted 4.5 x.
