# 14 – What Changes With the Level

Written 2026-11-10 (step C11, follow-up to the patrol routes). **Levels above 1 are covered and verified**: every table the game
indexes with the level counter was recomputed from the ROM for all 256 values and compared with an unattended run of the real game
that played **levels 0–50, 99–109, 199–209 and 250–255 and the 8-bit wrap back to 0–50** (377,063 movement reloads, 106 power
pellets, 105 bonus items and 106 level indicators, **0 mismatches**), and later **every other level as well: 42–199 and 209–255 (and the wrap again to 0–24) in two further runs** (see "Levels 42–249" below).
**All 256 values of the counter have now been played live.** Names are in `tools/labels.py`; tests are `tests/test_levels.py`
(10 tests); the live numbers are in `analysis/evidence-levels-summary.txt`.

## The level counter
- `Level` (`$30` for player 1, `$31` for player 2; selected with `CurrentPlayer`) is an **8-bit, zero-based** counter: board *N* has `Level` = *N* − 1.
- At the start of a game both counters get `StartLevel` (`$A559` steps it with OPTION through 0, 1, 2, 4, 6, 8, 10, 12; `Sub_ADF1` copies it).
- When a board is cleared (the dot counter reaches 260, `$B39A`), the level-complete sequence runs `SetupBoard` (`$AE02`) **and then** `INC Level` (`AdvanceLevel`, `$AC75`).
  It has no upper limit: after 255 it wraps to 0 (verified: after the wrap the tables behaved exactly like boards 1, 2, 3 …).
- Only 12 instructions read or write the counter (`tests/test_levels.py` lists them), so everything level-dependent is in the table below.

## Everything the level changes
| What | Routine, table | Index | Clamp |
|---|---|---|---|
| Pac-Man's step delays | `InitBoard` / `MoveDelayTick` → `PacMoveDelayBase` → `MoveDelay` | Level | **6** |
| Ghosts' step delays | same → `GhostMoveDelayBase` → `MoveDelay` | Level | **6** |
| Frightened time (solid colour) | power pellet (`$B3F7`) → `FrightenFrames` | Level | **none** (15 entries) |
| Frightened flash length | `$AF71` → `FrightenEndPhase` | Level | **none** (20 entries) |
| Bonus item in the maze | `$B662` → `BonusItemCodes` | Level | **12** |
| Bonus score and its pop-up | `$A974` → `BonusScore`; `$A93F` → `BonusScoreGlyphOffsets` → `BonusScoreGlyphs` | Level | **12** |
| Level indicator (bottom row) | `DrawLevelIndicator` (`$AC93`) → `BonusItemCodes` | Level | 6 / 18 (see below) |
| Ghost-house release timers | `SetupBoard` → `SetReleaseTimers` (`$AE2B`) → `HouseReleaseTimers` | Level + 1 | **3** |

**Nothing else depends on the level**: the ghost state machine, the patrol and start routes, the maze and the sight test contain no read of the counter.
The aggression, patrol and corner logic of `13-ghost-patrols.md` is therefore the same on every board; only speed, frightened time, bonus items and the house timers change.
(Player 2's counter `$31` is indexed the same way through `CurrentPlayer`; verified in a real two-player game in `19-two-players.md`: levels 7-29, every table read equal to the ROM tables for the playing player's level.)

## Movement (`MoveDelay`, frames per step)
Each entity has a countdown reloaded from a four-step cycle in `MoveDelay`; the table is picked by `PacMoveDelayBase` / `GhostMoveDelayBase` (7 entries, so the level is clamped to 6).
A step moves 1 pixel sideways or 2 pixels up/down (`StepAndDrawEntity`). Lower delay = faster. Verified live for every level seen, on all five entities.

| Level | Pac-Man cycle | Ghost cycle | Pac-Man mean | Ghost mean | Ghost speed vs Pac-Man |
|---|---|---|---|---|---|
| 0 | 2,2,2,3 | 3,3,3,3 | 2.25 | 3.00 | 75 % |
| 1 | 2,2,2,3 | 3,2,3,2 | 2.25 | 2.50 | 90 % |
| 2 | 2,2,2,3 | 2,2,2,3 | 2.25 | 2.25 | 100 % |
| 3 | 2,2,2,2 | 2,2,2,3 | 2.00 | 2.25 | 89 % |
| 4 | 2,2,2,1 | 2,2,2,2 | 1.75 | 2.00 | 88 % |
| 5 and up | 1,2,1,2 | 2,2,2,1 | 1.50 | 1.75 | 86 % |

## Frightened mode (power pellet)
Two numbers, both indexed by `Level` **without a clamp**: `FrightenFrames[Level]` (frames of solid frightened colour, loaded into `FrightenCountdown`) and
`FrightenEndPhase[Level]` (the `FrightenPhase` value at which it ends; the phase starts at 1 and steps every 24 frames, flashing on alternate steps).
Measured live for seven different end-phase values: the end test runs **(phase − 2) × 24 + 2 frames** (1 frame for phase 1, 2 for phase 2), so

> total frightened frames = `FrightenFrames[Level]` + (`FrightenEndPhase[Level]` − 2) × 24 + 2

- **Levels 0–14** use the designed table: solid `255 192 128 64 0 192 0 0 0 192 0 0 0 64 0`; end phase `11` (flash 218 frames) except `7` on levels 8, 11, 12, 13, 15 (122 frames) and `1` on levels 18, 19.
- **Past the tables** the lookups simply run on into whatever bytes follow: `FrightenFrames` (15 entries) into the shape and sound data at `$BC07…`, `FrightenEndPhase` (20 entries) into the start and patrol routes in RAM.
  So from board 16 on the frightened time is effectively scrambled but fully determined: e.g. levels 15–19 have no solid phase (`0`), level 20 has `146` frames and end phase `4`, level 21 `84`/`4`, level 22 `0`/`2`, level 23 `198`/`4`.
  All of this was observed live (every level from 20 to 255 matches the formulas).
- **No frightened time at all** (solid 0 and end phase 1 → the pellet's frightened state ends after one frame) on **29 of the 256 levels**, the first being levels 16, 18, 19, 24, 38, 39.
- **Practically endless frightened state:** with end phase **0** the phase counter has to wrap through 256 before it equals the table value, i.e. about 6,100 frames (over 100 s) of flashing after the solid phase.
  This occurs on levels 70, 81, 92, 103, 110, 117, 124, 131, 142, 155, 168, 187, 212 and 241; **all fourteen were seen live** (the phase reached 29–39 and was still running when the 1,536-frame cycle ended; on every other level the frightened state ended exactly when the phase equalled the table value).
- The finite maximum is level 0 (board 1) at 473 frames. Computed table for the first boards:

| Board | Level | Pac delays | Ghost delays | Solid (frames) | End phase | Flash (frames) | Total | Bonus | Item codes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | `2223` | `3333` | 255 | 11 | 218 | 473 | 100 | `3A 3B` |
| 2 | 1 | `2223` | `3232` | 192 | 11 | 218 | 410 | 300 | `3C 3D` |
| 3 | 2 | `2223` | `2223` | 128 | 11 | 218 | 346 | 500 | `3E 3F` |
| 4 | 3 | `2222` | `2223` | 64 | 11 | 218 | 282 | 500 | `3E 3F` |
| 5 | 4 | `2221` | `2222` | 0 | 11 | 218 | 218 | 700 | `40 41` |
| 6 | 5 | `1212` | `2221` | 192 | 11 | 218 | 410 | 700 | `40 41` |
| 7 | 6 | `1212` | `2221` | 0 | 11 | 218 | 218 | 1000 | `42 43` |
| 8 | 7 | `1212` | `2221` | 0 | 11 | 218 | 218 | 1000 | `42 43` |
| 9 | 8 | `1212` | `2221` | 0 | 7 | 122 | 122 | 2000 | `46 47` |
| 10 | 9 | `1212` | `2221` | 192 | 11 | 218 | 410 | 2000 | `46 47` |
| 11 | 10 | `1212` | `2221` | 0 | 11 | 218 | 218 | 3000 | `4A 4B` |
| 12 | 11 | `1212` | `2221` | 0 | 7 | 122 | 122 | 3000 | `4A 4B` |
| 13 | 12 | `1212` | `2221` | 0 | 7 | 122 | 122 | 5000 | `4C 4D` |
| 14 | 13 | `1212` | `2221` | 64 | 7 | 122 | 186 | 5000 | `4C 4D` |
| 15 | 14 | `1212` | `2221` | 0 | 11 | 218 | 218 | 5000 | `4C 4D` |
| 16 | 15 | `1212` | `2221` | 0 | 7 | 122 | 122 | 5000 | `4C 4D` |
| 17 | 16 | `1212` | `2221` | 0 | 1 | 1 | 1 | 5000 | `4C 4D` |
| 18 | 17 | `1212` | `2221` | 0 | 7 | 122 | 122 | 5000 | `4C 4D` |
| 19 | 18 | `1212` | `2221` | 0 | 1 | 1 | 1 | 5000 | `4C 4D` |
| 20 | 19 | `1212` | `2221` | 0 | 1 | 1 | 1 | 5000 | `4C 4D` |
| 21 | 20 | `1212` | `2221` | 146 | 4 | 50 | 196 | 5000 | `4C 4D` |
| 22 | 21 | `1212` | `2221` | 84 | 4 | 50 | 134 | 5000 | `4C 4D` |
| 23 | 22 | `1212` | `2221` | 0 | 2 | 2 | 2 | 5000 | `4C 4D` |
| 24 | 23 | `1212` | `2221` | 198 | 4 | 50 | 248 | 5000 | `4C 4D` |
| 25 | 24 | `1212` | `2221` | 0 | 1 | 1 | 1 | 5000 | `4C 4D` |

`python -I tools/describe_levels.py N` prints the same table for any range (all 256 levels are available).

## Bonus item, bonus score and the level indicator
- **Item:** appears when the dot counter reaches `$50` and again at `$A0` (`BonusItemUpdate`, `$B658` / `$B65C`); its two glyph codes come from `BonusItemCodes[min(Level, 12)]`
  and are written to the maze at `$0DF3/$0DF4` (maze row 12). The codes `$3A …` are glyph pairs of the maze charset (cherries, strawberry, … key); levels 12 and up all show `4C 4D` (a key).
  Note the title screen's icon list (`LevelIconCodes`) differs from `BonusItemCodes` on levels 6–9 (`44/48` against `42/46`).
- **Score:** `BonusScore[min(Level, 12)]` as thousands and hundreds digits → `AddToScore`: 100, 300, 500, 500, 700, 700, 1000, 1000, 2000, 2000, 3000, 3000, 5000 (levels 12+ always 5000).
- **Pop-up:** `BonusScoreGlyphs` (8 records of 5 glyph codes, one per distinct score, picked through `BonusScoreGlyphOffsets`) is copied to `$0DF1…$0DF5`, shown for 64 frames (`$40`, counted down once per frame by `BonusItemUpdate`) and cleared.
  The glyphs, rendered from the maze charset, draw the digits 100, 300, 500, 700, 1000, 2000, 3000, 5000.
- **Indicator** (`DrawLevelIndicator`, bottom row `$0F86–$0F93`): for levels 0–5 it draws `Level + 1` items, each a glyph pair from `BonusItemCodes[0..Level]`: item 0 at the right end (`$0F92/$0F93`) and every later item two cells further left, so the current level's item is the leftmost;
  for levels ≥ 6 it draws seven items read from `BonusItemCodes` starting at index `30 − min(Level, 18)` (so it stops changing at level 18; for levels 18+ it shows seven keys).
  Verified live on all 106 board starts (only the bytes the routine writes are compared).

## Ghost-house release (`HouseReleaseTimers`)
Ghosts 1–3 wait in the house with a timer in `GhostTimer` (`zp_CA+ghost`); `Sub_B7A5` decrements it **every 4th jiffy** (the patrol/chase timers of `13-ghost-patrols.md` tick every 8th).
`SetupBoard` sets the three timers through `SetReleaseTimers` from the 6-byte table `90 60 30 04 00 00` using `Y = old Level + 1` (clamped to 3), where "old Level" is the value *before* `INC Level`:

| Board | Timers ghost 1, 2, 3 | Meaning |
|---|---|---|
| 1 and 2 | `04 30 60` or `30 60 90` | chosen by bit 7 of `RTCLOK2` at the moment (the code treats old level 0 specially), so either set can occur (a game started on a later level uses the same rule with its start level; not exercised) |
| 3 | `00 04 30` | |
| 4 and up | `00 00 04` | ghosts 1 and 2 leave at once, ghost 3 after 16 frames |

Verified live on all 30 board starts of the release run (every observed set was one the table allows). Release time of ghost *k* (frame when it passes the door, state 1):
`release(k) = release(1) + 4 × (timer_k − timer_1) + 48` for *k* = 2 and 3; the constant 48 frames is the sideways walk of ghosts 2 and 3 to the door column (12 steps x 4 frames; house movement is paced by `RTCLOK2`, which is why it does not change with the level) - corrected in `18-frightened-eaten-house.md`, where the walk was traced step by step; this held for **58 of 58** checked releases
(for example board 1: timers 04/30/60 → releases at frames 354, 578, 770). The first board of a game also has about 240 frames of introduction before the first release.

## Every entry of every level-indexed table, read live
`tools/level_table_coverage.py` works out from the logs which table entries the real game actually read (`analysis/evidence-level-table-coverage.txt`). **No entry was left unread**, and every logged value equals the ROM.

| Table (entries) | How it is indexed | Entries read live | Notes |
|---|---|---|---|
| `FrightenFrames` (15) | `Level`, unclamped | all 15 | and the bytes after the table at levels 15–50, 100–109, 200–209, 251–255 |
| `FrightenEndPhase` (20) | `Level`, unclamped | all 20 | and the bytes after the table at levels 20–50, 100–109, 200–209, 251–255 |
| `BonusScore` (13 pairs) | `min(Level, 12)` | all 13 | |
| `BonusScoreGlyphOffsets` (13) → `BonusScoreGlyphs` (8 records) | `min(Level, 12)` | all 13 and all 8 | |
| `BonusItemCodes` (31) | bonus item: `min(Level, 12)`; level indicator: `0..Level` (levels < 6) or `30 − min(Level, 18)` and the 6 after it | all 31 | entries 12–30 are reached only through the indicator |
| `PacMoveDelayBase`, `GhostMoveDelayBase` (7 each) | `min(Level, 6)` | all 7 and all 7 | |
| `MoveDelay` (24) | base + step 0–3 | all 24 | |
| `HouseReleaseTimers` (6 bytes) | window `Y = min(old Level + 1, 3)` | all 6 (windows 0–3) | |
| `LevelIconCodes` (14) | `StartLevel` (title menu) | all 14 | OPTION reaches only 0, 1, 2, 4, 6, 8, 10, 12; the other six were forced with the debugger (`tools/altirra_titleicons.cmd`, 23,524 draws, 0 differences) |

### What the entries mean (understanding, not just values)
- **The designed part of the frightened tables is the first 15–20 entries.** Solid-colour time `255 192 128 64 0 192 0 0 0 192 0 0 0 64 0` frames plus an end phase of **11, 7 or 1** gives
  0.4 s – 8 s per pellet: the end phase sets the flash length, `(phase − 2) × 24 + 2` frames, and the colour flips every 24 frames, so 11 means five blue/white cycles, 7 three, and 1 none
  (the colour rule is read from the code at `$AFBE`; the lengths were measured). Board 1 gives the most (473 frames ≈ 7.9 s); boards 17, 19 and 20 give none (1 frame).
  Everything after those entries is not designed data but the neighbouring bytes (see above); it is deterministic and verified, just not meaningful.
- **Speed grows in five steps and then stops:** the delay tables have only five different rows (Pac-Man: `2223 2222 2221 1212`, ghosts `3333 3232 2223 2222 2221`), selected by `min(Level, 6)`.
- **Bonus items advance two boards at a time** (cherry, strawberry, then pairs of boards), saturating at board 13 where the key and 5000 points repeat forever; the indicator then shows seven keys.
- **The ghosts' house timers shrink to almost nothing by board 4** (`00 00 04`).

## How it was verified
`tools/run_patrol_trace.ps1 -Cmd altirra_levels.cmd` runs the real ROM in Altirra unattended, with a private settings copy at 800 % speed. Only the **emulated** machine is touched, never the ROM:
a ghost touching Pac-Man does not kill him; the game is started by jumping to its own start-game code; every 1,536 frames the level-complete flag is set (the game's own advance code runs);
the dot counter is set to `$50` (the game's own test shows the bonus item); Pac-Man is moved onto the bonus item and onto a power pellet (the game's own collision and pellet tests fire);
at cycles 30, 40 and 50 the counter is jumped to 99, 199 and 250 at the moment of the advance so that the game's own setup runs with the new value.
`tools/analyze_levels_log.py` recomputes every value from the ROM tables and compares. (An earlier attempt to inject PC jumps and stack pushes every frame slowed the emulator too much and was dropped for plain memory pokes.)

## Levels 42–249 (played live)
`tools/altirra_levels_42_199.cmd` and `tools/altirra_levels_210_249.cmd` (the same aids as `altirra_levels.cmd`, but no level jumps: the counters start at `$29` = 41 and `$D1` = 209 and the game's own `AdvanceLevel` adds 1 per cycle; the debugger reads numbers as hex, which is why the first run started at 41, not 29).
`analysis/evidence-levels-high-summary.txt` has the full numbers:
- **Run 1: levels 42–199 (158 consecutive boards)**: 582,350 movement-delay reloads, 158 bonus items, 158 level indicators, 159 power pellets, 18,546 frightened-end checks, 158 release-timer sets and 316 of 316 checked ghost releases that follow `release(k) = release(1) + 4 x (timer_k - timer_1) + 48`; **0 mismatches against the tables**.
- **Run 2: levels 209–255 and the wrap to 0–24 (71 boards)**: 256,464 reloads, 71 bonus items, 7,122 end checks, 138 of 138 releases; **0 mismatches**.
- The frightened state ended exactly at the table value on 147 of the 159 levels of run 1 and 70 of 72 of run 2; the other 14 are the endless-frightened levels listed above, all seen with the phase still running (levels 70, 81, 92, 110, 117, 124, 131, 142, 155, 168, 187 in run 1; 212 and 241 in run 2; 103 earlier).
- The clamped tables are constant from level 18 on (`tests/test_levels.py`, `HighLevels`): the speeds, the bonus item and its score and the indicator do not change on any of these boards; only the two unclamped frightened lookups and the release timers (which clamp at 3) vary or not.

## Not covered
- (Player 2's counter and the two-player alternation: now covered in `19-two-players.md`.)
- (Levels 51–98, 110–198 and 210–249 were first covered by the formulas only; they have now all been played live, see Levels 42–249 above. Every one of the 256 values of the counter has been read live.)
- ~~Real play to boards 16 and beyond by a human~~ **done 2026-11-11**: a person played boards 16-20 at normal speed (levels 15-20 zero-based, 5 level advances by the game's own code, Pac-Man invulnerable, no other aids; `tools/play_level_test.ps1`). 49,769 log lines, 35,350 movement reloads, 988 frightened-end checks, 10 bonus appearances, 21 ghost releases (10 of 10 on the release model): 0 mismatches against the tables (`analysis/evidence-human-play-summary.txt`). A second human session on **board 71 (counter 70, the first endless-frightened level)**, played to the end of the board by the game's own advance code (3,718 frames, 4 power pellets): all 2,687 frightened-end checks read table value 0 and the phase counter restarted at 1 with every pellet and climbed to 41 without the frightened state ever ending; 8,273 movement reloads, bonus item (2 appearances), release timers and releases matched the tables, 0 mismatches (`analysis/evidence-human-play-endless-summary.txt`). Pac-Man was caught on 5 frames running late in the board while the phase was running: **explained and verified, including in a second human-played game that logged ghost states: see "Catches while the frightened phase runs" in docs/18-frightened-eaten-house.md**.
