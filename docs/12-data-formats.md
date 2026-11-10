# 12 – Data Formats (Step C11, data labelling)

Written 2026-11-10. Every byte of the ROM that is not code (2,246 bytes) now belongs to a labelled region in
`src/asm/pacman.s`; the map lives in `tools/labels.py` (`DATA`). Rebuild check after the change: byte-identical.
Comments marked **hyp** are hypotheses; everything else is read from the code or checked by a test
(`tests/test_streams.py`, 5 tests). Decoders: `tools/decode_streams.py`
(`--dump` writes the decoded RAM images to `resources/decoded/`, which is not committed).

## The three compressed formats
`Start` expands compressed ROM data into RAM before the game runs. The formats were read from the code:

| Format | Code | Rule |
|---|---|---|
| **Type A** | `$A3BA` (inline in Start) | byte `c`: `c < $80` = literal `c`; `$80–$BF` = repeat the next byte `(c & $3F)+1` times; `$C0–$FE` = three bytes out: `c & $3F`, high nibble and low nibble of the next byte; `$FF` = end |
| **Type B** | `ExpandData` `$A668` | byte `c`: `$FF` = end; otherwise output `PixelPatternTable[c & $3F]` repeated `(c >> 6)+1` times |
| **Nibble split** | `$A40A` | each source byte gives its high nibble then its low nibble (256 bytes in, 512 out) |

Evidence that the decoders are right: the streams end exactly on the next boundary (`$A1E0`, `$A385` = the byte
before `Start`, `$BE74`), and the output sizes are whole structures (below).

## Regions
| ROM range | Label | Content | Evidence |
|---|---|---|---|
| `$A000–$A002` | UnreadHeader_A000 | 3 bytes `4A 4A 48` that **nothing uses** | section below: never read by the game; the OS reads `$A000` only in its RAM-size test, where the value is irrelevant; boot CRCs identical for five different contents |
| `$A003–$A1E0` | CharsetStream | type B → RAM `$3000`, 808 bytes = **101 glyphs** | DliHandler1 sets `CHBASE=$30`; 808 = 101 × 8 |
| `$A1E1–$A385` | MazeMapStream | type A → RAM `$0800`, 920 bytes = **23 × 40** | DisplayList1 has exactly 23 mode-4 rows of 40; Start copies it to `$0C00/$1000/$1400` |
| `$BAC0–$BAF1` | GhostShape0–4 | five ghost frames, 10 rows × 8 px | rendered bitmaps (see listing comments) |
| `$BAF2` | GhostEyesShape | eyes only | bitmap |
| `$BAFC–$BB55` | PacShape* | nine Pac-Man frames (full; open right ×2, left ×2, up ×2, down ×2) | bitmaps; pointer table `PacShapePtrs` at `$BB65` points to the first frame of each direction |
| `$BB55–$BB64` | PacMouthOffsets (`$BB55–$BB57` = `00 0A 00`), PacMouthFrame2Offset (`$BB56`), DeathPlotBytes (`$BB57–$BB64`) | chomp-animation offsets and the death-animation plot bytes | section below |
| `$BB65–$BB6E` | PacShapePtrs | 5 words: `$BAFC $BB06 $BB1A $BB2E $BB42` | verified by test |
| `$BB6F–$BB82` | ZeroPageInit80 | 20 bytes → zero page `$80–$93` | copy loop at `$ADE0` |
| `$BB83–$BB96` | JunctionYList, JunctionXList | the y (= 8·row+36) and x (= 4·col+46) coordinates of the 10 junction rows and 10 junction columns of the maze lattice | **confirmed**, nibble-map section |
| `$BB97–$BBAA` | JunctionRowPtrs | pointers to the 10 rows of `JunctionExits` in RAM (`$060E + 10·row`) | **confirmed** (631 live lookups) |
| `$BBAB–$BBE1` | ThresholdLists / ProfileList_BBD8 | `$FF`-terminated lists | `CMP #$FF / BEQ` loops |
| `$BBE2–$BBED` | ColorsGame, ColorsTitle | 8 + 4 colour bytes → `PCOLR0..COLOR3` / `COLOR0..3` | `LoadShadowColors`, `InitDisplay2` |
| `$BBEE–$BBF1` | ColorsDli | 4 colours for the DLIs, masked by `COLRSH`/`DRKMSK` | code at `$A4BC` |
| `$BBF2–$BBF7` | HouseReleaseTimers | `90 60 30 04 00 00`: ghost-house release timers, 3-byte windows chosen by the board | **confirmed live** (`14-levels.md`) |
| `$BBF8–$BC06` | FrightenFrames | 15 entries by `Level`: initial `FrightenCountdown` (frames of solid frightened colour); level 1 = `$FF` | **confirmed** live (`$FF` logged) |
| `$BC07–$BC4F` | StarShape, GhostScoreZeros, GhostScore200/400/800/1600Digits | 12-row shapes copied as 16 rows (4 pad bytes from the next table) | **ghost-eaten pop-ups: confirmed** (section below); StarShape's meaning is unknown |
| `$BC50–$BCCF` | TuneAudf1, TuneAudf2 | 2 × 64 sound values → `AUDF1`/`AUDF2`, one step per 4 jiffies | `$A7DF`; index stops at `$40` (**hyp**: start-up tune) |
| `$BCD0–$BCD7` | GhostScorePtrs | `$BC1F $BC2B $BC37 $BC43` | indexed `2*GhostsEaten` at `$A8CF` |
| `$BCD8–$BCE5` | AudfSweepDown/Up | two 7-byte pitch sweeps, 0-terminated | chosen by `zp_F6` |
| `$BCE6–$BCED` | StartRoutePtrs | pointers to the four ghost start routes in RAM | **confirmed** (864 live route reads) |
| `$BCEE–$BD0D` | PatrolStartPositions | 16 (x, y) junctions, one per patrol route; each route is a closed loop from its start | **confirmed** (16/16 loops) |
| `$BD0E–$BD15` | CornerPositions | (`$BE,$2C`) (`$3A,$2C`) (`$BE,$C4`) (`$3A,$C4`): the four corners | indexed by ghost number; same stores as RandomPositions |
| `$BD16–$BD25` | PatrolRouteOffsets | 16 start offsets of the patrol routes inside `PatrolRoutes` | **confirmed** (each route ends where the next begins) |
| `$BD26–$BD44` | BonusItemCodes | 31 glyph codes (first of a pair) | entries 0–12 = the bonus item of each level (maze `$0DF3`, level indicator); the falling half is read by the indicator for levels ≥ 6 (`14-levels.md`) |
| `$BD45–$BD79` | BonusScoreGlyphs, BonusScoreGlyphOffsets | 8 records × 5 codes, 13 offsets | indexed by level (`zp_30`, clamped to 12) |
| `$BD7A–$BDB8` | PixelPatternTable | 63 pattern bytes | used by type B; index 63 never occurs (test) |
| `$BDB9–$BDC6` | PacMoveDelayBase, GhostMoveDelayBase | 7 + 7 offsets into `MoveDelay` by `Level` (clamped to 6) | **confirmed** (5,451 live reloads) |
| `$BDC7–$BDD0` | TextHighScore | "HIGH SCORE" (10) | copy loop X=9..0 → `$200F`; shown on screen |
| `$BDD1–$BDD5` | DliChbaseTable | `$18 $E0 $30 $E0 $30` | `CHBASE` per DLI in DliHandler2 (**correction**: an earlier note had read this as text) |
| `$BDD6–$BDF6` | TextChangeDifficulty, TextPressStartTo | "CHANGE DIFFICULTY" (17), "PRESS START TO " (16), mode 6 screen codes | fixed-length copy loops to `$1D05`, `$1D56` |
| `$BDF7–$BE04` | TextCopyright | "(C) ATARI 1982" (14 bytes, ANTIC mode 6 screen codes, colour 3) | **confirmed on screen**, section below |
| `$BE05–$BE12` | LevelIconCodes | 14 entries by `StartLevel`: first glyph code of the icon shown in the middle of the menu | **confirmed on screen**, section below |
| `$BE13–$BE74` | TitleCharsetStream | type B → RAM `$1808`, 160 bytes = 20 glyphs | DliHandler2 sets `CHBASE=$18` |
| `$BE75–$BE94` | TitleCharsetTail | 32 bytes → `$18A8–$18C7` | copy loop at `$A443` |
| `$BE95–$BF80` | Nibbles… (8 regions) | the nibble map: 472 nibbles of constant tables, split by `Start` into RAM `$0600–$07D7` | **confirmed**, section below |
| `$BF81–$BFC5` | DisplayList2, DisplayList1 | ANTIC display lists | decoded; JVB targets point to themselves |
| `$BFC6–$BFF9` | TextPlayerGame, TextPressSelectFor, TextPressOptionTo, TextPlayGame | title-screen lines of 11, 16, 16, 9 bytes | fixed-length copy loops, lengths from the loop counts |
| `$BFFA–$BFFF` | cartridge header | RUN, flags, INIT | standard layout |

## Confirmed: the pop-up shapes are the ghost-eaten scores 200 / 400 / 800 / 1600
Checked in `tests/test_ghost_score.py` (6 tests, all from ROM bytes), nothing assumed:
1. **Power pellet** (`PowerPelletEaten`, `$B3DE`, reached from three corner-position checks): stores 5 in the tens digit
   (`ScoreAdd10`) and calls `AddToScore` (+50), sets `GhostsEaten` (`$E9`) to `$FF`, and sets bit 7 of every ghost's state byte (`zp_CE,X`).
2. **Eating a ghost** (`GhostEaten`, `$A886`): reached only when that ghost's state bit 7 is set (`BMI` at `$A881`); it does `INC GhostsEaten`,
   so the first ghost after a pellet gives index 0 (`$FF` + 1), the fourth gives index 3.
3. The same index drives both results: `$A8CF` loads `GhostScorePtrs[2*index]` and copies that 16-row shape to the missile memory
   (`zp_39 = $23`: missiles at `$2300` with `PMBASE=$20`, single-line), plus `GhostScoreZeros` to the eaten ghost's player (`zp_3B = $24 + ghost`);
   `$A900–$A91E` sets the amount: index 0 → `ScoreAdd100 = 2`, 1 → 4, 2 → 8, 3 → `ScoreAdd1000 = 1` and `ScoreAdd100 = 6`, then `JMP AddToScore`.
4. `AddToScore` (`$B423`, decimal mode) adds the six digits `$94–$99` (`ScoreAdd100000`…`ScoreAdd1`; `Y = 5..0`) to the score digits at
   `$202A–$202F` (player 1) or `$2047–$204C` (player 2), chosen by `CurrentPlayer` (`$2B`).
   So the amounts are exactly **200, 400, 800, 1600**.
5. Drawn side by side (record = 8 px of missiles, then the shared zeros = 8 px of the player; positions set at `$A893–$A8A3`) the four shapes
   read **200**, **400**, **800** and **1600** (ASCII renders in the test).
**Live check (Altirra, 2026-11-10, `analysis/evidence-play-trace-summary.txt`):** after a power pellet (`GhostsEaten` was `$FF`), eating a ghost logged `INC` then pop-up index 0 (`GhostScorePtrs` read with Y = 0), and `AddToScore` received digits `000200`. Power pellets added `000050` and dots `000010`. A second session (power pellet held with a debugger refill of the countdown, ROM untouched) ate four ghosts in a row: `GhostsEaten` went `$FF → 0, 1, 2, 3`, `GhostScorePtrs` was read with Y = 0, 2, 4, 6, and `AddToScore` received `000200`, `000400`, `000800`, `001600`. So all four pop-ups are confirmed live.

## Confirmed: `$BB55–$BB64` (was "SmallTable_BB56")
It was two different things that share bytes with their neighbours:
- **`PacMouthOffsets` `$BB55–$BB57` = `00 0A 00`** (3 entries; the first is the last row byte of `PacShapeDown2`, the third the first byte of `DeathPlotBytes`).
  `MovePacMan` (`$B179`) reads it at `$B2DC` as the Pac-Man mouth animation: `ChompPhase` (`$AB`) 0 shows `PacShapeFull`; phases 1, 2, 3 add offsets
  0, 10, 0 to the direction's pointer (`PacShapePtrs`), so the shown frame goes **full, frame 1, frame 2, frame 1, full …** (shapes are 10 bytes apart,
  hence `$0A`).
  Direction handling proves the Up/Down/Left/Right names of the shapes: `STICK0` is inverted (`EOR #$0F`) into bits 1 = up, 2 = down, 4 = left, 8 = right;
  the up handler does `DEC PacY` twice, down `INC PacY` twice, right `INC PacX`, left `DEC PacX`, and each loads pointer index 6, 8, 2, 4, which are the
  up, down, right and left shapes of `PacShapePtrs`.
- **`DeathPlotBytes` `$BB57–$BB64`** (14 bytes) are plotted one per step by `DeathAnimation` (`$AEF7`): frame 0 draws `PacShapeUp2`, frames 1–14 each write
  one byte `DeathPlotBytes[x]` at row `(nibble-map byte at $0600+x) − 1` of Pac-Man's missile memory, frame 15 draws `StarShape`, then the 16 rows are cleared and
  the animation flag is reset. Each frame lasts 8 ticks (`DeathAnimDelay` = 7). The animation runs only in the death sequence: a collision with a ghost
  that is **not** frightened (`$A923`) sets `DeathState` = 1; `DeathSequence` (`$AE3D`) reaches state 2 and does `INC DeathAnimActive` (`$AE76`); `$A82F`
  runs `DeathSequence` then `DeathAnimation` while `DeathState` is non-zero. Simulating the 15 frames from the ROM bytes shows the shape losing its top rows
  and shrinking, then the starburst (`tests/test_bb56_a000.py`).
  **Live check:** `ChompPhase` at `$B2DC` cycled 1, 2, 3, 1, 2, 3 … for 740 reads (phase 0 never reads the table, as predicted); the death animation read `DeathPlotBytes[0..13]`
  in order, each for exactly 8 redraws (112 reads = 14 × 8), then `StarShape` for 128 row reads (16 rows × 8 redraws) in frame 15.

## Confirmed: `$A000–$A002` are unused padding
Three bytes `4A 4A 48` (also the ASCII letters "JJH"; no evidence that this means anything). Verified three independent ways:
1. **Static audit of the cartridge** (test): no instruction has an absolute/indexed operand that can reach `$A000–$A002` (bases `$9F01–$A002`), no
   JSR/JMP goes there, and the only pointer ever loaded with high byte `$A0` is the charset stream (`SrcPtr = $A003` at `$A41B`); the other two
   `LDA #$A0` store to `zp_AD`, which is never used as a pointer. The six zero-page pointers used with `(zp),Y` (`$38 $3A $3C $3E $47 $80`) are only ever
   assigned ROM addresses ≥ `$A003` or RAM addresses.
2. **Dynamic trace** (Altirra tracepoint on reads of `$A000–$A002`, boot to title screen): the only reads are of `$A000`, by the **OS** RAM-size test at
   `$F257–$F276` (probes the first byte of each 4 KB step: read, invert, write back, compare; ROM ignores the write, so the compare fails and that marks RAM top).
   The value cannot matter: the test is `CMP` of the inverted value against the unchanged byte. `$A001` and `$A002` are never read
   (`analysis/evidence-boot-trace.txt`).
3. **Experiment**: booting copies of the ROM with `$A000–$A002` set to `00 00 00`, `FF FF FF` and `AA 55 AA` gives **identical** CRCs of the RAM the
   game builds at start-up (`$0600–$0FFF`, `$1000–$18C7`, `$3000–$3327`) to the original; a control copy with a stream byte (`$A004`) changed does change the
   `$3000` CRC, so the check can see differences (`analysis/evidence-boot-crc.txt`, `tools/boot_crc_check.ps1`). The same run shows that the Python
   decoder reproduces Altirra's RAM exactly (charset CRC-32 `$5E84E650`).
What they are for is not recoverable from the ROM (most likely a leftover from the build); they must be kept as they are for a byte-exact rebuild.
4. **Live play trace** (boot, Start, moving, 2 power pellets, 1 ghost eaten, 1 death; `analysis/evidence-play-trace-summary.txt`): `$A000` was read 3 times, all at boot by the OS RAM-size test (`pc=$F263/$F265`); `$A001`/`$A002` were never read, and nothing read any of the three during play.

## Confirmed: the title-screen codes (`$BDF7–$BE04`, `$BE05–$BE12`)
Checked from the code (`tests/test_title_text.py`, 7 tests) and on screen (Altirra screenshots, kept locally in `analysis/evidence-*.png`; images are not committed):
- **`TextCopyright`** is copied to `$1D57` by the start-up state of the title routine (`Sub_A6CC`, `zp_19` = 1) and shown on the **first title screen** (logo plus one line,
  for about four seconds, until `zp_1D` meets the jiffy clock); the menu text later overwrites it. Screen row 18 is ANTIC mode 6; decoding the 14 codes as mode 6
  gives **"(C) ATARI 1982"**, all colour register 3, and the screenshot shows exactly that line.
- **`LevelIconCodes` is not an animation.** `StartLevel` (`zp_1B`) is the starting level: pressing OPTION on the menu (`CONSOL` = `$03`, handler `LA559`) steps it
  `0 → 1 → 2 → 4 → 6 → 8 → 10 → 12 → 0`, and `Sub_ADF1` copies it into the level counters `Level` (`$30`/`$31`) when the game starts. Every frame the menu code
  writes glyph code `LevelIconCodes[StartLevel]` and the next code to `$1CC6/$1CC7` (row 11, ANTIC mode 4, game charset `$30`), which is the small icon in the middle of the screen.
  Forcing `StartLevel` to each value in the emulator showed: 0 = cherries, 1 = strawberry, 2 and 3 = the same orange-coloured round fruit, 4 = apple, 6 = green melon,
  8 = three green bars, 10 = bell-like icon, 12 and 13 = key. Values 2/3 and 12/13 look identical, as the table's duplicated entries predict; the odd entries 3, 5, 7, 9, 11, 13 other than
  the duplicates are unreachable with OPTION. I name icons only by appearance.

## Findings worth knowing
- The title text is not zero-terminated: `$00` is the **space** character, and every line has a fixed length given by the loop that copies it.
  The lines are ANTIC **mode 6** screen codes: the low 6 bits select the glyph (code + `$20` = ASCII), the top 2 bits select one of four colour registers
  (not inverse video, which an earlier version of this document wrongly assumed). The glyphs come from the OS ROM font (`CHBASE=$E0`, see `DliChbaseTable`);
  only the PAC-MAN logo uses the game's own title charset (`CHBASE=$18`) and the icon row uses the maze charset (`CHBASE=$30`).
- The maze is stored as a 23 × 40 character map in a run-length format and held in RAM three or four times (`$0800`, `$0C00`, `$1000`, `$1400`).
- The nibble map is not compressed graphics: it holds nine constant tables (below) that the game reads from RAM; nothing ever writes to `$0600–$07FF` after `Start`.

## Confirmed: the nibble map (ROM `$BE95`, RAM `$0600–$07D7`)
`Start` splits 256 source bytes into 512 nibbles at RAM `$0600–$07FF`. Only the first 236 bytes ($BE95–$BF80, 472 nibbles) are data; RAM `$07D8–$07FF` is the first
20 bytes of `DisplayList2` that the copy loop reads past the end (checked in `tests/test_nibble_map.py`). The 472 nibbles partition exactly into nine tables, and the code
never writes to them:

| RAM | Nibbles | Name | What it is | How it was checked |
|---|---|---|---|---|
| `$0600` | 14 | DeathPlotRows | row written by each death-animation frame | live: frames 1–14 read X = 0..13 |
| `$060E` | 100 | JunctionExits | 10×10 direction masks (1 up, 2 down, 4 left, 8 right) at the lattice points of the maze | all 90 non-zero entries equal the maze's open-neighbour mask; every maze corner/crossing is in it (56/56); left-right mirror-symmetric; 631 live lookups (Pac-Man and 4 ghosts) used the cell of the entity's position and the table value |
| `$0672` | 20 | FrightenEndPhase | by `Level`: the `FrightenPhase` value at which frightened mode ends | live: the end test read 11 while the phase counted 1 to 11 (24 frames per step), then frightened mode ended |
| `$0686` | 40 | StartRoutes | four ghost start routes (13, 8, 8, 11 nibbles, each ended by `$F`): the direction to take at each successive junction | valid walks over `JunctionExits`; live: 864 reads match, and ghosts 0–2 passed exactly the predicted junctions |
| `$06AE` | 230 | PatrolRoutes | 16 zero-terminated routes, again one direction per junction | started at `PatrolStartPositions[i]`, **all 16 are valid walks and all 16 return to their start**; live: all 16 selected, 75,452 reads match, 6,097 scripted steps followed with no exception, every wrap landed on the start junction (`13-ghost-patrols.md`) |
| `$0794` | 26 | BonusScore | 13 (thousands, hundreds) pairs by `Level`: 100 300 500 500 700 700 1000 1000 2000 2000 3000 3000 5000 | the bonus routine adds the pair to the score; live: the level-1 bonus item added `000100` |
| `$07AE` | 24 | MoveDelay | frames per movement step, as four-step cycles selected by `PacMoveDelayBase` / `GhostMoveDelayBase` | live: 5,451 reloads, none differs; level 1 Pac-Man 2,2,2,3, ghosts 3,3,3,3 |
| `$07C6` | 9 | NoReverseMask | indexed by direction 1,2,4,8: all exits except the reverse (`D E 7 B`) | live: 3,789 filtered masks, the reverse bit never survived |
| `$07CF` | 9 | ReverseDir | direction → opposite direction (`2 1 8 4`) | live: the power pellet reversed all four ghosts, `4 → 8` |

How the game uses them: an entity's position is looked up in `JunctionYList` / `JunctionXList` (`Sub_B48E`); if it stands on a lattice point the `JunctionExits` mask
gives the allowed exits, filtered by `NoReverseMask`; ghosts follow `StartRoutes` when leaving the house and `PatrolRoutes` later, and a pellet flips their direction with `ReverseDir`.
Movement speed comes from the `MoveDelay` cycles. Evidence is in `analysis/evidence-nibble-map-summary.txt`.
Patrol routes: **all 16 verified live** (`13-ghost-patrols.md`). Not covered by a live run: levels above 1 (the table entries for them are verified by code and values only).

## Still unknown
Purpose of the remaining small tables (`ThresholdLists`, `ProfileList_BBD8`, `ByteTable`-style lookups in `$BBAB–$BBF7`), of `StarShape`'s artwork
beyond its use as the last death frame, the meaning of each ghost frame, and which game events switch ghosts between the start route, patrol route and chase behaviour
(`GhostState`, zero-page `$CE`). These need tracing in Stage D/E.
