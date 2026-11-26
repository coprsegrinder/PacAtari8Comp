# 74 - Achievements (an addition to stage J)

Asked for by the owner on 2026-11-25. There is no RetroAchievements set for this game (and that system needs an emulator host, which this native port is not), so the port has its own: **27 achievements earned by playing**, found by watching the game's state after each frame (nothing is written into the game: its digests are unchanged), shown with a **toast**, a **chime** and a **gold flash and pulse on a DualShock 4 / DualSense**, listed on an **Achievements page** of the pause menu, kept in a **sealed file** in the game's folder.

The owner's decisions: score and level achievements do not count in a game started above level 1 (Option key); the file is protected against hand-editing; all the proposed achievements; the notification exactly as proposed (toast, sound, pad flash); a separate page after Controls.

Source: portable and tested (`src/c/shell/achieve.[ch]`, `sha256.[ch]`, `ctest achieve_check`), the Windows part (`win_toast.[ch]`, `win_main.c`), the chime (`sound.c`), the pad flash (`haptics.c`).

## 1. The list

| # | Name | Earned by | Notes |
|---|---|---|---|
| 1 | First Bite | eat a dot | |
| 2 | Power Up | eat a power pellet | |
| 3 | Ghost Buster | eat a ghost | |
| 4-6 | Double Trouble, Triple Threat, Ghost Sweep | eat 2, 3, all 4 ghosts with one power pellet | the game's own combo counter |
| 7 | Clean Sweep | clear a board without dying | a death on that board spoils it |
| 8 | Close Call | eat a ghost while another ghost that can still catch Pac-Man (not frightened, not eyes) is within 12 position units | Pac-Man is caught at a distance of 2 (measured: the death frames of a bot's games), so 12 is a little over two squares |
| 9 | Fruit Salad | eat the bonus fruit on 3 different boards in one game | two fruits on one board count once |
| 10 | Bonus Life | earn the extra life (at 10,000 points) | score achievement |
| 11-13 | High Roller, Six Figures, Arcade Legend | score 50,000 / 100,000 / 250,000 | score achievements |
| 14 | New Record | beat the high score, when it was over 1,000 at the start of the game | score achievement |
| 15-18 | Warming Up, Five Alive, Veteran, Unstoppable | reach level 3 / 5 / 8 / 12 | level achievements (level 1 is the first board) |
| 19 | Marathon | play one game for 15 minutes (53,928 frames; paused frames and the menu do not count) | |
| 20 | Survivor | clear 3 boards in a row without dying | a death ends the streak |
| 21-22 | Dot Collector, Dot Hoarder | 1,000 / 10,000 dots in total | progress shown; power pellets are not dots |
| 23 | Ghost Hunter | 100 ghosts in total | progress shown |
| 24 | Regular | finish 10 games | a game is finished when the game-over countdown starts; a game left for the title is not |
| 25 | Two's Company | finish a two-player game | |
| 26 | Pellet Popper (hidden) | eat all 4 power pellets of one board | |
| 27 | Quick Draw (hidden) | eat a ghost within 2 seconds of a power pellet | |

**The owner's rule.** A game started with a starting level above the first (the Option key: 0 is level 1; the others 1, 2, 4, ...) is "assisted": its score and level achievements (10-18, and New Record) do not count, in that game only. Everything else counts. A hidden achievement shows as `???` and "HIDDEN ACHIEVEMENT" until it is earned.

**What counts as a game.** Play begins when the game's `PlayStarted` is set (after the start tune); a new game, from the title or by Start in the middle of a game, clears it, so both begin a new watched game (found with a bot playing through the real game: a Start in the middle of a game does not pass through the title). Frames of the game-over countdown, a turn being handed to the other player, and the first frame after a change of player produce no events.

## 2. Notification

- **Toast.** A box drawn **into the game's own picture** (`win_toast.c`): the game's 8-pixel font, a dark box with a gold rim, a gold cup, "ACHIEVEMENT UNLOCKED", the name and the description, at the top left of the picture, faded in and out, 4.5 s, queued when several come together. It is drawn after the game and before the picture goes to the screen, in every way the program shows the picture (the plain one, the in-between pictures of the FPS option, the CRT shaders, which then treat it as part of the picture). **History, so that it is not repeated:** the first three versions were windows of their own over the game window (owned, then topmost, then in the free bar beside the picture): the program put them on the desktop (a screen capture of the desktop showed them, and the log said "shown") but **the owner never saw one**: a full screen OpenGL picture can reach the display without the desktop compositor, which is where such a window is drawn. A toast in the picture is on the display whatever the display does. The cost, said plainly: it is **over the game's picture** (the top left of it), not clear of it, because a notice in the picture cannot be outside the picture (the owner's request for a place clear of the picture could not be kept with this; it was asked for before the toast was found not to appear at all).
- **Chime.** Four rising notes (C6, E6, G6, C7) of about 0.44 s, added to the speaker's sound before the master volume and the mute, so both apply to it.
- **Pad.** On a DualShock 4 or DualSense (and a pulse on any pad that can rumble) the light bar flashes gold and a lighter gold for 1.5 s and the motors pulse once; a death's red goes first; the Light Bar and Vibration settings apply.

## 3. The page

Pause menu: Resume Game, Graphics Options, Controls, **Achievements**, Sound, Quit Game. Eight to a page; Up / Down move (round), Left / Right a page, Esc back (on Achievements). The one under the cursor is described below the list with the date it was earned (or its progress, or "NOT YET EARNED"). The page says that score and level count from level 1 only.

## 4. The file, and its protection

`save/achievements.pma` in the game's folder (no registry, nothing outside it; portable). 164 bytes: `PMAC`, version, the number of achievements, a bit per achievement, the three lifetime counts (dots, ghosts, games finished), the time each was earned, and a **32-byte HMAC-SHA-256 seal** over all of that. It is written at once when something is earned, every 10 seconds of play while counts change (at most), when the pause menu opens and at exit.

**Against hand-editing:** a file whose seal is not right (a byte changed, a bit set, a count raised, a file from elsewhere, a damaged or short one) is **not taken**: it is put aside, unchanged, as `save/achievements.bad`, a line is written to `logs/shell.log`, and the achievements start again. (A plain editor cannot make a file the seal accepts.) **The limit, said plainly:** the key is in the source, so someone who reads the source can seal a forged file; this keeps out editing by hand, not a determined cheat, and this is a single-player game with no board to cheat on.

## 5. How it was checked

| Check | Where | Result |
|---|---|---|
| SHA-256 and HMAC-SHA-256 against the standard vectors (empty, "abc", the two-block message, 1,000 bytes, RFC 4231 cases 1, 2, 6) | `ctest achieve_check` | pass |
| Every event from hand-made game states: dots and power pellets (and a pellet is not a dot, a new board's reset and a jump are not dots), the ghost combos, Close Call (near, far, frightened and eyes do not count), Quick Draw (inside and outside 2 s), Clean Sweep, Survivor (a death ends it), Fruit Salad, Pellet Popper, the score and level tiers, the extra life, New Record, Marathon (a pause does not count), games finished (the countdown once; abandoned games not), Two's Company, the turn change, the lifetime tiers, the queue | `achieve_check` | pass |
| The owner's rule: a game started at level 4 earns no score, level, extra-life or New Record achievement even with 300,000 points and level 12, still earns First Bite; the next game from level 1 counts again; the old level left over from the last game before a new game has set its own is not play | `achieve_check` | pass |
| The file: round trip; every single byte changed (one bit) is refused and leaves the achievements as they were; too short, too long, empty; a bit past the last achievement with a right seal | `achieve_check` | pass |
| The detection against the real game: a bot playing 400,000 frames through the real shell (`ach_step` after every frame) earned First Bite, Power Up, Dot Collector, Ghost Buster, Quick Draw ... with sensible counts, and Marathon and Pellet Popper were first found to fire wrongly across a Start in the middle of a game (the reason for the "what counts as a game" rule above); fixed, then gone | a scratch program, not kept | looked at |
| The real program (`--achtest`): the game played, the first dot earned, the toast made, the file written, sealed right (read back by the program), the Achievements page up | `check_front_end.py` | see the summary |
| A file with one bit changed is put aside as `achievements.bad` byte for byte, and the achievements start again; a file sealed by **Python's own HMAC** (so the C and the Python agree on the format and the seal) is read, kept, and added to | `check_front_end.py` | see the summary |
| The chime sounds 0.44 s once, at the volume set (a half volume is a quarter of the amplitude), silent when muted, and changes nothing when it is not started | `ctest sound_check` | pass |
| The gold flash and pulse: 90 frames of two golds, a pulse, then yellow again, a death's red goes first, a menu puts everything at rest | `ctest controls_check` | pass |
| **The toast is in the picture the display gets** (the owner could not see the window versions): `--achtest` with the zfast shader in fullscreen reads the picture back from the OpenGL window while the toast is up and again after it has gone; at the toast's place about a quarter of the pixels differ and gold is there (27 % and 9,159 gold pixels, 1176 x 252 region at 2304 x 1440), and a picture of that region was looked at (the box, the cup, the text, through the shader) | `check_front_end.py` (`--achtest --crt zfast`) | pass |
| The menu: the sixth item, the page's cursor round and by pages, F1 from it, Esc back on Achievements | `ctest menu_check`, `--menutest` | pass |
| The other tests of the program do not read or write the achievements file | by construction (`ach_on` is off for them) | |

## 6. Limits (OV-83)

- **The toast's look was seen by me, in a picture** (the region of the picture read back through the zfast shader), **not by the owner**: the owner has not yet confirmed that it appears now. It is at the top left of the picture and covers part of the game (the score line) for 4.5 s.
- **Close Call's distance (12 units), the chime, and the gold flash on a real pad** are choices and were not tried by the owner; the flash on a real DualShock 4 / DualSense was not seen.
- **A game is counted at its end** by the game-over countdown; a game left by Start, Select or Option, or by closing the window, is not counted. The lifetime counts are written every 10 seconds at most, so a crash can lose a few seconds of counts (not an unlock: that is written at once).
- The achievements are not tied to a replay: only live play is watched. The owner's own, earlier game progress is not looked for.


## 7. The pictures of the README (2026-11-26)

`--achtest` also writes `logs/toast_full.ppm`, the whole picture read back from the OpenGL window while the toast is up; `tools/make_screenshots.py` turns it into `docs/images/achievement-toast.png`.
