# 55 - Regression and edge cases (checklist stage 89)

Hand-written, 2026-11-23. Checklist stage 89: "Test unusual conditions and verify that subsequent modifications have not broken previously working functionality." Two halves: **edge cases** (inputs and conditions no earlier game produced, compared with the ROM) and **regression** (one command that re-runs the verification, so that a later change cannot break what was verified without being noticed).

## 1. Edge cases

`tools/make_rom_edge_replays.py` makes seeded replays, each stressing one thing; nothing is recorded from any port, the inputs are chosen and the game decides what happens. Each was played by the ROM on the concrete 6502 and by the C port, and compared frame by frame in the whole state, the ordered chip writes and the RANDOM reads (`tools/check_c_vs_rom.py`, `52`).

| Profile | What it does |
|---|---|
| `sticks` | all 16 stick values for both players, changing nearly every frame (diagonals, all four directions at once, none), the trigger at random; a two-player game |
| `console` | all 8 values of the console keys (START, SELECT, OPTION and every combination), in the title, in play and in the game-over countdown; the OPTION key sets the start level |
| `pause` | the space bar and other key codes at random times in every state, with the OS's three frames of key delay |
| `clock` | the OS clock starts at 250, 255 or 128, so it wraps in the middle of a game |
| `rnd0`, `rnd1`, `rndalt` | RANDOM always `$00`, always `$FF`, or alternating, in a normal game |
| `hold` | START held for 700 frames from the title, then the trigger and START held in play |
| `idle` | no input for 6,000 frames (the copyright screen, the title, the attract timers) with the attract colour values changing |
| `mixed` | one of the above every 40-200 frames |

**30 replays (10 profiles, 3 seeds, 6,000 frames): 180,000 frames, 0 differences.** (The three `mixed` games were regenerated in stage 90 when a fourth kind of input race was found and left out of the generator, `56`; the new versions were compared with the ROM in the sweep of that stage, and the golden digests of `edge-mixed-1` and `edge-mixed-2` were remade from them.) The nine of them that include the console, pause, hold, sticks and mixed games also pass the behaviour checks of `53` (54,000 frames: the frame classes, the changes of the 20 state variables and the whole state; 0 differences).

**The long games.** Stage 87's games stopped at the first board change. `tools/make_rom_bot_replay.py --stop-after-levels 3` plays on, so the later levels' tables (frightened time, ghost speeds, release timers, bonus items) run: one game for one player (16,160 frames, three boards cleared, 561 eaten-pause frames, 561 level-end frames) and one for two players (17,056 frames, three boards cleared, 627 eaten-pause, 374 level-end, 153 turn-control frames): **33,216 frames, 0 differences.**

## 2. What the edge cases showed: the C equals the ROM wherever the ROM has one answer

Every difference found was traced to its cause, and each was a **race of the original**, not a defect of the C (section 3). After the inputs that sit in those races were left out of the generator, all 30 replays and both long games match in every frame.

## 3. The races of the original (OV-73)

The main program of the game reads `CONSOL` in loops of two or three instructions, the vertical-blank handler counts `KeyDebounce` down in between, and a restart takes more than a frame. A console key that **changes in the frame after it was first seen, or while it is being handled**, is therefore read or not read depending on **which instruction the interrupt lands on**: on the real machine, on the clock cycle at which the key changes. The ROM harness (`tools/check_app.py`) runs the main program for a fixed budget of instructions after the handler, so its answer depends on where that budget ends. Four kinds were found, each shown by moving the budget by a few instructions (`analysis/evidence-edge-summary.txt` section 4):

1. **A one-frame press, or a change of key in the second frame** (`console-2`: console 0 in frame 0, 7 in frame 1): the key is taken in 5 of 14 neighbouring budgets (period three, the length of the debounce loop `$A511-$A516`).
2. **A change while the press is being handled** (`console-3`, frame 240: console 1, 1, then 6): the title menu or the game depending on the budget (period three).
3. **A change of the attract values (`DRKMSK`, `COLRSH`) in the frame a press starts** (`mixed-3`, frame 4832): the main program rewrites `DliColors` from them at the top of every pass; whether it does so before or after it reads the console decides whether `DliColors` is 0 or `$3A` for the next frames.

4. **A change of the attract values in the frame a trigger press starts a new game, or a key is read** (found by the final sweep of stage 90, `docs/56`: sweep game 23, frame 4273, and sweep game 25, frame 3059): the restart takes more than a frame and overlaps the pass that rewrites `DliColors`; after the frame the ROM's `DliColors` was `[0,0,0,0]`, `[58,68,0,0]`, `[58,68,42,0]` or all four colours for the budgets 802-803, 799, 800 and 801, and the C's was all four.

In each case the C takes one fixed answer, and it is **one of the answers the ROM gives** (the C equals the ROM for 9 of the 14 budgets in the first case, 4 of 10 in the second, 2 of 3 in the third); the other answers are equally right on the real machine. The generator therefore keeps the console out of these races (`tidy_console`): every key is held at least 3 frames and followed by at least 6 frames of nothing, and none is within 3 frames before or 8 after a change of the attract values (nor is a trigger press or a key there). **Quick console changes are not compared**; they are a property of the hardware's timing, not of the program, and a replay cannot express them (a replay has one value of `CONSOL` per frame).

## 4. Regression

`python -I tools/run_regression.py` (about 6 minutes) re-runs, in order: the replays are made (30, deterministic: the four sessions of the 79d vectors, the six seeded random games of `52`, the edge games of seeds 1 and 2); the build with gcc (strict C99, `-Werror`, 0 warnings); `ctest` (36 tests); **the golden games**: every replay is played with the renderer and the sound chip on and its **state hash, run digest, video digest and audio digest must equal the line of `analysis/golden-digests.txt`** (30 games, 214,917 frames); and the Python tests of the C port (shell, behaviour, C against ROM, correlation, regression). `--full` adds the same with clang, the C against the ROM on every golden replay (`tools/check_c_vs_rom.py`), and the Linux build and tests in WSL (`tools/build_test_posix.sh`, `54`), with the sanitizers; it takes much longer.

The golden file was made from a build that equals the ROM on every one of these games (section 1, `52`), so a difference in the golden games after a change means the change altered what was verified. **The check sees a change:** a one-line mutation of the dot-eating routine (a dot eaten between two cells in one frame in 256) makes the golden step fail on 6 of the 30 games at once (and `ctest` fails too). The mutation was undone and the run repeated: all steps pass.

## 5. What remains open

- **OV-71** (the routine call counts of the key loop, the new-game sequence and the display-list interrupts) is not closed by this stage; what it also named, longer games beyond the first board change, is (section 1).
- The games are samples: 6,000-17,000 frames each. Games to a high level, the 255-level wrap and the 8-bit counters of very long play are not run (a bot that survives that long is a project of its own).
- The golden digests are NTSC, of this build on three compilers and two operating systems (`54`); they do not cover macOS, MSVC or other machines (OV-72).
- The races are a limit of the comparison, not of the port; the way to compare them too would be to run the ROM at several interrupt phases and accept any of its answers, which needs the ROM and the C to continue from different states after a race (OV-73).

## 6. Files

`tools/make_rom_edge_replays.py`, `tools/run_regression.py`, `tests/test_regression.py`, `analysis/golden-digests.txt`, `analysis/evidence-edge-summary.txt`. Derived data in `build/c89/` and `build/regress/` (git-ignored): `python -I tools/make_rom_edge_replays.py build/c89 --frames 6000 --seeds 3`; `python -I tools/make_rom_bot_replay.py OUT.pmrp --seed 11 --frames 30000 --stop-after-levels 3`.
