# 53 - Behavioural equivalence: the C port against the ROM (checklist stage 87)

Hand-written, 2026-11-23. Checklist stage 87: "Compare execution paths, state transitions, outputs, and responses to identical inputs." Stage 86 (`52`) compared the *state* the two programs end each frame in. This chapter compares *how they behave*: the sequence of frame classes, the changes of the state variables, the routines that run, and the outputs. It also closes OV-70 (the two frame classes stage 86 did not reach).

## 1. Identical inputs, now reaching every frame class (OV-70)

Stage 86's inputs reached 13 of the 15 frame classes of `38`; the level end and the eaten pause need a player that plays on purpose. `tools/make_rom_bot_replay.py` is such a player. It is not a port and knows nothing of the C: it plays **the ROM** on the concrete 6502 and at every decision (every 6 frames) looks ahead by running the ROM itself (save the machine, hold each of the four stick directions for 22 frames, score what happened: dots eaten, a ghost eaten, a death, the distance to the nearest dot or, while the ghosts are frightened, to the nearest ghost; restore). Only the stick it chose is recorded, with the clock and the RANDOM bytes the run read; the replay is then an ordinary input-only replay.

| Replay | Frames | Players | Eaten-pause frames | Level-end frames |
|---|---|---|---|---|
| `bot1` (seed 1) | 6,082 | 1 | 99 | 187 |
| `bot2` (seed 2) | 6,560 | 1 | 165 | 187 |
| `bot3` (seed 3) | 9,741 | 2 | 396 | 187 |

Each plays until the board is cleared once (the first ghost is eaten at frame 960-1089, the level ends at frame 5,595-9,254) and then runs on into the next board. The C port against the ROM, by the method of `52` (`tools/check_c_vs_rom.py`): **22,383 frames, 0 differences**, 74,131 chip writes, 541 RANDOM bytes (`analysis/evidence-c-vs-rom-summary.txt`). With these, **all 15 frame classes** of `38` have been compared with the ROM directly. **OV-70 is closed.**

## 2. What is compared (`tools/check_behaviour.py`)

The same replays are run on the ROM (concrete 6502, the collision registers from its own memory) and on the C (`pacman_a8 run --states`). After each frame:

1. **Frame classes.** The class the C's own state selects for the next frame (`core_app.frame_class` on the dump of the C's state) equals the one the ROM's dispatcher chooses, in sequence.
2. **State transitions.** Each of the 20 state variables of `34` (`GameState`, `TwoPlayers`, `IntroRequest`, `CountdownActive`, `PlayStarted`, `StartTuneActive`, `TurnSwitchState`, `WaitState`, `LevelComplete`, `LevelEndStep`, `CurrentPlayer`, `Paused`, `BonusVisible`, `BonusScoreShown`, `PacFrozen`, `EatPause`, `DeathAnimActive`, `DeathState`, `FrightenPhase`, the four `GhostState`) has the same value after the frame in the C and the ROM, and every change from the previous frame is **a chain of the 68 rules of `34`** (or a clear of a bulk range): the rules of `tools/analyze_states.py` as a graph without program counters, because the C has no program counter, so a frame that applies two rules in a row (the ROM writes `DeathState` 1, then 2, then 3 in one frame) is one change that must be reachable by the chain.
3. **Execution paths** (section 3).
4. **Outputs.** The program's outputs are the display and player-missile memory, the shadows and positions, and the ordered chip writes; `42` classifies all 574 stores of the ROM into these regions (2,303,680 stores on the concrete 6502, none outside), so equal state and equal ordered writes after every frame **is** equal output. The check repeats the whole-state comparison on every frame.

## 3. Execution paths

The ROM side counts, for each routine, how often control **enters it from outside its own body** (a call, a jump, a branch, or the routine before falling in) **inside the vertical-blank handler** (`$A5FD`, so the idle passes of the main program that the harness runs between frames do not count). The routines are those the static call tree (`tools/comm_map.py`) reaches from the handler and from no other context. The C side is the call count of the function whose declaration carries the routine's address in a header comment (`Name $ADDR`), from `gcc --coverage` (`-O0`, so nothing is inlined) and `gcov`, over the same replays. For the ROM it also records which routine each entry came from; for the C, which function each call line belongs to.

**55 routines compared: 46 have the same call count in the ROM and the C.** The 9 that differ (`analysis/evidence-behaviour-summary.txt`) are differences of structure, not of behaviour, and every one is accounted for by number:

| Routine | ROM | C | Why (checked by number in `--paths`) |
|---|---|---|---|
| `junction_lookup` | 142,358 | 68,198 | Callers in the ROM: MovePacMan 74,160, GhostBehaviour 65,851, EyesAndHousePerFrame 2,347. The C has Pac-Man's version as the pure `ref_junction_exits` (74,160 calls from `move_pacman`), the ghosts' as `junction_lookup`: 65,851 from the five functions that split GhostBehaviour, and 2,347 from `eyes_and_house_per_frame`. **All three equal.** |
| `step_entity` | 109,435 | 109,111 | GhostBehaviour 65,662 = the C's ghost functions (65,662); DeathSequence 22,116; HouseBobStep 15,770; HouseLeaveStep 3,216 (`set_dir_step`); EyesAndHousePerFrame 2,347: **all equal**. The remaining 324 are `DrawAllInPlace` calling `StepEntity` in the ROM; the C's `draw_all_in_place` draws directly. The 324 is exactly the difference. |
| `draw_ready_screen` | 78 | 45 | The C writes the same three steps inline in `start_tune_step` at tune step `$28` (33 times); 45 + 33 = 78. |
| `copyright_wait` | 6,018 | 1,786 | The ROM's `$A70D` serves the copyright wait and runs on into the title menu; the C keeps them apart: 1,786 + 4,232 = 6,018. |
| `ghost_start_route`, `ghost_patrol`, `ghost_chase` | 341, 53, 48 | 21,323, 5,414, 18,671 | The ROM's GhostBehaviour is one state machine that enters these labels only when a ghost changes state; the per-frame work is inside its body. The C has one function per state, called every frame. The work is equal (the `junction_lookup` and `step_entity` sums above are over exactly these functions). |
| `vbi_play_frame` | 117,300 | 0 | `$A5FD` is the handler itself (once a frame); the C's frame is `app_frame` / `frame_dispatch` and `vbi_play_frame` is only the test form. |
| `table_rom` | 137 | 2,988,102 | A table read of the ROM window, not a routine. |

**Not covered here**: the routines of the key loop, the new-game sequence and the display-list interrupts (the harness runs the main program until it settles, so a ROM-side call count for them would count idle passes, not behaviour). Their behaviour is covered by the whole-state and transition checks, not by call counts (OV-71).

## 4. Result

**117,300 frames on 13 replays** (the four 79d sessions, six seeded random games, three games played on purpose):

- frame-class sequence: **0 differences**, all 15 classes seen (copyright setup 13, copyright wait 1,786, title menu 1,353, title after game 2,879, paused 60, board start 35, start idle 35, start tune 8,502, ready wait 2,925, turn control 356, play 74,142, death 20,108, eaten pause 660, level end 561, game-over countdown 3,885);
- state variables: **3,963 changes in the 20 variables, 0 differences between the C and the ROM, 0 changes without a chain of rules**; **65 of the 68 rules seen**; the three not seen are the boot rule (`Start` clears the zero page before frame 0: no frame can show it) and the two steps `DeathState` 1 to 2 and 2 to 3, which the ROM always makes in the same frame (the net change 1 to 3 is seen and is a chain of the two);
- whole state, chip writes, RANDOM reads: **0 differences** in every frame;
- paths: 46 of 55 routines equal, the 9 others explained above, 10 of 10 numerical explanations hold.

The comparison was shown to **see** a difference: a changed `GameState` in the C's dump is reported as a transition difference at that frame, a whole-state difference, and a frame-class difference one frame later (`tests/test_behaviour.py`).

## 5. A finding: six wrong addresses in the C headers

Building the path comparison showed that six comments in the C headers (`Name $ADDR` after a declaration) named an address 1-4 bytes away from the label of the routine in `src/asm/pacman.s`: `EyesAndHousePerFrame $B69D` (label `$B69E`), `ShowPowerPellets $B551` (`$B55A`), `BlinkPowerPellets $B54B` (`$B54F`), `ClearPokeyRegisters $B0E7` (`$B0E6`), `GhostEatenPause $B04D` (`$B049`), `DeathSequence $AE3E` (`$AE3D`). They were comments only: no behaviour was affected, but a reader following them would have landed in the middle of another routine. They are corrected, and `tests/test_behaviour.py` now checks every `Name $ADDR` comment of `src/c` against the assembly labels.

## 6. Limits

- Samples, not a proof: 13 replays of up to 12,000 frames; the 79d sessions and the seeded games use the same stick scripts as the earlier stages, the three games played on purpose are the only ones that reach the eaten pause and the level end (about 650 and 560 frames); no game goes past the first level change, so levels 1 and above and the bonus items at later levels are covered by the earlier model checks (`44`) and not by a C-against-ROM replay beyond the first board change; the second extra life, the game over from a high level, and a full 255-level wrap are not run.
- The routine paths of the handler only (OV-71); the C side is one compiler (gcc `-O0`, to avoid inlining).
- NTSC; the GTIA collision model of `50` stands in for the real chip; one start clock (0); no real hardware.
- Where the main program is inside its loop is not compared (the dump does not carry it).

## 7. Files

`tools/make_rom_bot_replay.py`, `tools/check_behaviour.py`, `tests/test_behaviour.py`, `analysis/evidence-behaviour-summary.txt`, `analysis/evidence-c-vs-rom-summary.txt` (the three games played on purpose), the corrected comments in `src/c/core/frame.h`, `play.h`, `sound.h`. The replays are derived data in `build/c86/` and `build/c87/` (git-ignored): `python -I tools/make_rom_fuzz_replays.py build/c86 1 2 3 4 5 6`, `python -I tools/make_rom_bot_replay.py build/c87/botN.pmrp --seed N --frames 16000 [--two]`.
