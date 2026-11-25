# 73 - The settings kept between runs (an addition to stage J)

Asked for by the owner on 2026-11-25: every setting changed in the menu is remembered the next time, and it is portable: everything is written in the game's own folder.

Source: `src/c/shell/settings.[ch]` (portable, tested: `ctest settings_check`), the reading and writing in `src/c/platform/win32/win_main.c` (`settings_load`, `settings_save_if_changed`).

## 1. What is kept, and where

The file is **`save/settings.ini`** in the main folder (the folder that holds `original/Pac-Man.rom`, found from the program's own folder: the same folder as `save/highscore.pmo` and `logs/`). Nothing is written anywhere else (no registry, no AppData): copy or move the folder and the settings go with it. A text file, so it can be read and edited with the game closed; deleting it gives the defaults.

```
version=1
display_mode=windowed | fullscreen
resolution=1280x800            (one of the 20 of the Graphics page)
fps=native | 75 | 90 | ... | 180 | uncapped
crt_shader=off | guest | zfast | aperture
vibration=off | light | heavy
light_bar=off | light | heavy
volume=0 .. 100                (tenths)
mute=on | off
output_filter=off | soft | warm
```

**When it is written:** at once whenever one of the settings changes (a key in the menu, F11, Alt+Enter), and only then (nothing is written if nothing changed; a few lines, so every key press is cheap). **When it is read:** once, at the start, before the window is made, so the window opens in the mode and size that were left, with the shader, the FPS and the sound as they were.

**What wins over the file:** the command line (`--windowed`, `--fps`, `--crt`). **What a bad file does:** every line is checked on its own; a missing line, a value that is not one of the choices, a line the program does not know, a damaged or an empty file leaves the default for that setting and never stops the game from starting. A folder that cannot be written to is logged (`logs/shell.log`) and the game goes on without saving.

**Not kept (on purpose):** the game's own choices of 1 or 2 players (Select) and of the starting level (Option) are the original's: they are made on the title screen and are as on the real machine at each start. The high score has its own file (`save/highscore.pmo`). The light bar and vibration choices are kept even when no pad is connected (they are grayed out then, and come back with the pad). A window of a size of its own (the `--scale` test option) is not kept.

## 2. How it was checked

| Check | Where | Result |
|---|---|---|
| The text of the defaults gives the defaults back; every resolution and FPS choice (with the other settings varied) survives the round trip; empty, junk and damaged text change nothing; each bad value is refused (letters, negative, over 100, a resolution not in the list, an FPS not in the list, trailing characters); spaces, capitals, CR LF, comments and unknown keys are fine; the last good line wins; volume rounds to a tenth; a window of its own size is not written back as a resolution | `ctest settings_check` | pass |
| The real program: started on a file written by the checking script (windowed 1280 x 800, 90 FPS, no shader, vibration light, light bar off, volume 60 %, muted, warm) it starts with exactly that; then volume 60 to 50 % and unmuted by real keys in the menu are in the file afterwards and the other lines are unchanged | `check_front_end.py` (`--settingstest`) | see `analysis/evidence-front-end-summary.txt` |
| The other tests of the program do not read or write the file (so they are the same on every machine and never touch the player's file) | by construction (`settings_on` is off for them) | |

## 3. Limits

- A saved resolution and FPS come back as they were even if the monitor is not the same one (the first start still chooses the monitor's own; the saved values then win).
- The file is written in place (not through a temporary file): a power cut in the middle of a write can leave a short file; the parser takes what is valid and the rest are defaults.
- Not tried by the owner on their own machine yet.
