# 69 - The FPS option and the in-between pictures (an addition to stage J)

Asked for by the owner on 2026-11-24, after the questions of how to show the game at 60 pictures a second without changing its speed, pitch or logic. The Graphics Options (docs/68) get a third setting, **FPS**: how many pictures a second are shown. The **game itself never changes**: it takes one step every 1/59.92 s, driven by the sound device, exactly as in stage J; the FPS option only decides which moments of that game are shown. Source: `src/c/render/interp.[ch]` (the in-between pictures, portable C99, `ctest interp_check`), `src/c/render/render.[ch]` (the layers of a frame), `src/c/shell/menu.[ch]` (the option, `ctest menu_check`), `src/c/platform/win32/win_main.c` (the timing and the window).

## 1. The choices

| Choice | Pictures a second | |
|---|---|---|
| **Monitor** (the default) | the monitor's refresh rate (read from Windows: 180 on the owner's monitor), one picture each refresh (`DwmFlush`) | the menu shows it: `MONITOR (180 HZ)` |
| **Native** | **59.92**: the game's own pictures, one for each step of the game, as they have been shown since stage J | no in-between pictures; the picture is exactly the game's |
| **30, 60, 75, 90, 120, 144, 165, 180** | that many, on a timer | |
| **Uncapped** | as many as there are: a new picture whenever the picture would differ from the one before (the moving things are placed to a pixel of the picture shown), without spinning when nothing moves | |

Everything except Native uses the in-between pictures below, made **by this program**: no driver feature (frame generation, "smooth motion"), no variable-refresh monitor, no GPU is needed or used for them; a monitor that refreshes at 60 Hz gets 60 pictures, and the game is unchanged.

## 2. How an in-between picture is made (`render/interp.c`)

The game makes a picture of the screen every step. The picture at a moment between step A and step B (a fraction `phi` of the way) is made so that it is **the original's picture, not a mix of two**:

- **The playfield** (the maze, the dots, the text, the status rows) is **the nearer frame's**: it is not moved and not blended, so a dot disappears, a pellet blinks and the score changes at the moments the game did it.
- **The objects that move** are the four ghosts (the players of the Atari's graphics chip) and Pac-Man with the pop-up score (drawn with the missiles). Each is found in the two frames (from the layers the renderer already had: `render_frame_layers`), the move between them is **measured by matching its pixels** (a shift of up to 8 pixels), and the object of the nearer frame is drawn `phi` (or `phi - 1`) of that move away from its own place.
- **An object that is in one frame only, jumped more than 8 pixels (a ghost through the tunnel, back at the house, Pac-Man after a death), or does not match, is not moved**: it is the nearer frame's.
- **The picture is made at the size it is shown at** (the window or screen size of docs/68), so a sprite can stand a fraction of a game pixel off the place the game put it, and its pixels stay square blocks of the same size: nearest pixel, never smoothed. **No pixel is a mix of colours**: every pixel is a colour that GTIA's own rules give it (the priority between players and playfields, the colour registers of that line).
- `phi = 0` is exactly the nearest-pixel picture of frame A, `phi = 1` that of frame B.
- The move of an object is a whole number of pixels **of the picture shown**, so two moments that put the objects on the same pixels make the same picture, and the program does not draw it again (what makes Uncapped useful and cheap).

## 3. Which moment is shown (timing)

- **The speed is the game's.** The game steps are made as before: whenever the sound device has less than about two frames of sound queued. 59.92 steps a second, 735.99 samples a step, no resampling: speed and pitch are the original's.
- **The picture follows the sound.** The time of the picture to show (in game steps) is the position of the sound device: the steps handed to it minus what it still holds. That position is read in steps, so it goes through a slow filter (a model that runs at exactly 59.9227 steps a second and is pulled to the device's position with a time constant of 0.25 s): the picture moves smoothly, picture and sound are one (before, the picture was about two frames ahead of the sound), and the speed of the picture cannot differ from the game's. With `--no-audio` the system timer is the clock, two steps ahead of the picture.
- **Ticks.** Monitor: one picture a refresh (`DwmFlush`). The numbers: a timer with the system timer resolution raised to 1 ms, the last millisecond waited for by yielding. Uncapped: no wait.
- **The game steps ahead of the picture** by about 1 to 2 steps (the sound's queue), which is what gives the picture its second frame (B) to move towards: **an in-between picture shows a moment at most one step older than the newest one**, which costs no more delay than the sound already had.
- **The menu and the help** (docs/68) pause as before; the picture behind them is the frame that was shown; when the game goes on the time model starts again from the sound's position.

## 4. How it was checked

| Check | Where | Result |
|---|---|---|
| The option: the list (monitor first, native, 30 to 180, uncapped), the default, the monitor's rate in the text, stepping both ways round, the other items untouched | `ctest menu_check` | pass |
| The in-between pictures, from 900 frames of a played game: `phi = 0` and `phi = 1` equal the nearest-pixel pictures of frames A and B **to the pixel** (an independent implementation); an object that moved 2 pixels is a quarter, half and three quarters of the way at `phi` = 0.25, 0.5, 0.75 (the centre of its colour, measured on the picture: on the straight line from A to B to within a pixel of the game); nothing is mixed: every pixel of an in-between picture is one of the game's colours (a picture of 2 to 12 colours); an object that jumps 40 pixels or vanishes is not moved (the picture is exactly the nearer frame's); the same moment again changes nothing; what is reported changed covers all that changed | `ctest interp_check` | pass |
| **The real program**, with real key messages (`--menutest`, `tools/check_front_end.py`): every FPS choice set through the menu, then **measured for two seconds in the running game** | `analysis/evidence-front-end-summary.txt` | see below |
| Native: the game runs at 59.92 (within 2 %), about 60 pictures a second, no in-between pictures | `--menutest` | yes |
| 30, 60, 75, 90, 120, 144, 165, 180: the pictures made a second are the number chosen (within 6 %), and the game still runs at 59.92 | `--menutest` | yes, each |
| The monitor's rate (180 Hz here): 178 pictures a second | `--menutest` | yes |
| Uncapped: 289 different pictures a second in that game, the game at 59.92 | `--menutest` | yes |
| The game is the same: the game recorded through all of this (menu, display changes, every FPS choice) replays headless to the same state, run, video and audio digests | `check_front_end.py` | equal |
| The cost | `--menutest`, `interp_check` | the process uses 5 to 21 % of one core in every choice in the optimized builds (gcc 10 to 21 %, clang 5 to 18 %; up to 34 % in an unoptimized build); a picture of 2304 x 1440 needs 1.8 ms when the nearer frame changes and well under 1 ms otherwise (unoptimized) |

## 5. Limits (OV-78)

- **No person looked at it.** What it looks like in your hand is not measured: the pictures are exact to the rules above, and the motion is smooth when a sprite moves, but a sprite in the original moves in steps of 2 pixels at uneven frames (the game's own speed pacing), and the in-between pictures glide through each step: the pace of the steps is the game's.
- **The picture is one game step older than the newest at most**, and in the in-between choices **the playfield changes at the nearest of two frames** (up to half a step early or late against a sprite that is gliding past it).
- **The match of an object is by pixels**: a shape that changes at once with a move (Pac-Man's mouth, a ghost's feet) is matched by what the two shapes share; a few frames of the death or the ghost-eaten scenes may not be moved (they are the nearer frame's: never wrong, only not smoothed).
- **Limits of the measurement**: one machine, one monitor (180 Hz, 2560 x 1440); the pictures were counted, not looked at on the screen or timed with a camera; the 144 and 165 Hz choices on a monitor that is not 144 or 165 Hz are timer-paced, and are not locked to its refresh (so a repeated or skipped refresh is possible); the monitor choice relies on `DwmFlush`.
- **The first run of the test where three choices measured 0 pictures a second** (once in 8 runs): the window had been made small by something outside the program (likely a focus change); the test now restores it and says so (`NOTE` in `logs/menutest.txt`).
- The settings are not saved between runs.
