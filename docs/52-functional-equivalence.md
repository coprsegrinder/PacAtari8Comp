# 52 - Functional equivalence: the C port against the ROM (checklist stage 86)

Hand-written, 2026-11-23. Checklist stage 86: "Compare the functionality of the reconstructed software against the original implementation." Stage 87 (behavioural equivalence) is the next one and is what closes OV-02.

## 1. What was missing

Until stage 85 the C port was tested against the **Python port** (vectors, sessions of 78d / 79d); the Python port was tested against the ROM (`44`, `tools/check_app.py`: 0 differences). That is a chain, and the sessions the C was replayed on were *made by the Python port*. Stage 86 puts the **C directly against the ROM**, with no Python port in between.

## 2. The method

`tools/check_c_vs_rom.py REPLAY`:

- **The ROM** runs on the concrete 6502 (`tools/cpu6502.py`, `RomApp` of `tools/check_app.py`): `Start` from the RUN address, then each frame the OS clock, the inputs of the frame, the vertical-blank handler `$A5FD` entering between two instructions of the main program, and the main program up to its next wait. The collision registers the ROM reads are computed from **the ROM's own memory** by the GTIA model (`50`), with the latch carried from frame to frame.
- **The C port** runs the same replay (`pacman_a8 run REPLAY --states FILE`): the same stick / trigger / console / key / clock values and the same RANDOM bytes of every frame. `--states` (new in this stage) writes, for each frame, the packed state (7,052 bytes: zero page, maze and its three copies, title screen, status rows, shadows, player-missile pages, the eight positions, the picture buffers), the ordered sound-chip writes, and the number of RANDOM bytes read.
- **Compared after every frame**: all of that. Excluded: the ROM's temporaries `$2A`, `$3C-$3F`, `$A5` (`check_ghost.SCRATCH`: scratch of the ROM routines that the port does not keep; the pictures the drawing makes are compared).
- **Not compared**: where the main program is inside its loop (a pass, the debounce, the release, the clock wait), which `check_app.py` compares for the Python port; the C dump does not carry it.

The comparison was shown to **see** a difference: a corrupted byte of the zero page, of the maze, of a chip write or of the RANDOM count in the C dump is reported at exactly the corrupted frame (`tests/test_c_vs_rom.py`).

## 3. The inputs

- the five recorded sessions of 79d (made by the Python port from seeded scripts: clock, keys, one-player game, two-player game, level (first 600 frames only; after that the recording pokes `LevelComplete`, which no input can do));
- six **new seeded games** (`tools/make_rom_fuzz_replays.py`, not made by any port): a random stick for each player changing every 8-40 frames, SELECT / START at fixed frames (two players on odd seeds), the trigger now and then, 64 random RANDOM bytes a frame, 12,000 frames each.

## 4. Result

**95,517 frames compared, 0 differences**: all 244,448 sound-chip writes in order, all RANDOM reads, the whole state after every frame (`analysis/evidence-c-vs-rom-summary.txt`). Run with the gcc 14.2 Release build for all 11 runs and with the clang 19.1 Release build for 3 of them (the 2P session, two seeded games): 0 differences.

13 of the 15 frame classes of `38` were visited by these 11 replays (the other two in section 5): copyright setup / wait, title menu, title after game, paused, board start, start idle, start tune, ready wait, turn control, play, death, game-over countdown.

## 5. The two frame classes not reached (OV-70) - closed in stage 87

The 11 replays of section 3 never reached the **level end** and the **eaten pause**: a random stick does not eat a power pellet and then a ghost, nor clear a board, and no recorded session does it by input (the level session reaches the level end by a poke, which the ROM harness cannot replay). **Stage 87 closed this** (`53`, section 1): `tools/make_rom_bot_replay.py` plays the ROM on purpose and records only its inputs; three such games (6,082, 6,560 and 9,741 frames, one of them for two players) reach the eaten pause (660 frames) and the level end (561 frames) and the C equals the ROM on all 22,383 frames, 0 differences. All 15 frame classes of `38` are now compared with the ROM directly.

Limits that remain: NTSC only; the collision model of `50` (checked against Altirra) stands in for the real GTIA; one start clock (0); the high score and options are not part of the run; the replays are games of at most 12,000 frames (about 3 minutes); no real hardware.

## 6. Files

`tools/check_c_vs_rom.py`, `tools/make_rom_fuzz_replays.py`, `tools/make_rom_bot_replay.py` (stage 87), `tests/test_c_vs_rom.py`, `src/c/shell/main.c` (`--states`), `analysis/evidence-c-vs-rom-summary.txt`.
