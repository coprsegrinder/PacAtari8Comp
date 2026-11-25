# 11 – Labelling and Naming (Step C11, first pass)

> **`src/asm/pacman.s` is not stored in this repository (decision of 2026-11-26).** It is the cartridge program in assembler text - assembling it gives the ROM byte for byte - so it is made, on the machine of someone who owns the ROM, from `original/Pac-Man.rom` by `python -I tools/make_asm.py` (with this project's own names and notes, `tools/labels.py`). The result is the same file every time. The tools and tests that read it (`tools/asm_source.py`) make it first when it is not there. Everything in this chapter that names it assumes it has been made.

Written 2026-11-10. Covers checklist stages 29–30 as far as evidence allows. This is a **first pass**:
the rest of the naming belongs to the analysis stages (D), where behaviour is traced and understood.
Every change in this step was checked with `tools/build_rom.py` (**byte-identical** after each regeneration).

## How the listing is produced now
`tools/make_asm.py` (entry points, structures) + `tools/labels.py` (names) regenerate `src/asm/pacman.s`;
never hand-edit that file. Names are cosmetic and cannot change the bytes.

## What was added to `src/asm/pacman.s`
| Item | Count | Evidence / rule |
|---|---|---|
| Hardware register names (GTIA, POKEY, ANTIC) | 50 used | Standard 400/800 register names; stores use the write name, other accesses the read name (e.g. `$D000` store = `HPOSP0`, load = `M0PF`) |
| OS variables (shadow registers, `VDSLST`, `SDLSTL`, `STICK0`, `CH` ...) | 13 | Standard names at standard addresses, used in the standard way |
| OS zero page: `POKMSK` $10, `RTCLOK2` $14, `ATRACT` $4D, `DRKMSK` $4E, `COLRSH` $4F | 5 | Standard names; `$14` is waited on for a tick, `$10` is ORed then stored to `IRQEN`; $4D–$4F appear together |
| Game zero page: `SrcPtrL/H` $3C/$3D, `DstPtrL/H` $3E/$3F | 4 | Used as `(zp),Y` read/write pointers by the copy/expand helpers and by `Start` |
| Other zero page | rest | **since checklist stage 3 (2026-11-18) the names of the variable catalogue** (`25`, `tools/zp_catalogue.py`; a byte that is not the first of its variable is `Name+k`); this chapter and the chapters written before it use the `zp_xx` of their time: the key is section 5 of `25` (83 old names) |
| Subroutines (JSR targets) | 66 | `Sub_xxxx` for the 53 still unnamed; the other 13 have real names (below) |
| Data labels | 43 | `D_xxxx` at every ROM address the code reads as data |
| Display lists | 2 | Decoded ANTIC instructions with comments; `DisplayList1` ($BFA3, 29 instructions, jumps to itself), `DisplayList2` ($BF81, 26 instructions) |
| Text | 3 runs | Atari screen codes decoded in comments; strings seen on the title screen: HIGH SCORE, CHANGE DIFFICULTY, PRESS, PLAYER, GAME, [select], [option], TO, PLAY |
| Cartridge header | 4 lines | `.word Start`, present byte, option byte, `.word Init` |

## Named routines and the reason for each name
| Address | Name | Evidence |
|---|---|---|
| $A386 | Start | cartridge RUN vector |
| $A6B4 | Init | cartridge INIT vector; a single `RTS` |
| $A5FD | VbiHandler | installed with SETVBV (A=7); ends with `JMP XITVBV` |
| $A573 / $A5CE | DliHandler1 / 2 | installed into VDSLST by SetDisplayList at $A49B / $A621; both end with `RTI` |
| $A6B5 | SetDisplayList | writes SDLSTL/H, DLISTL/H and VDSLST from X, Y and constant $BF/$A5 |
| $A610 | InitDisplay2 | clears HPOSP0–7 and AUDF1–AUDC4 area, installs `DisplayList2` + `DliHandler2`, loads four colours |
| $A668 | ExpandData | reads a stream via SrcPtr and writes via DstPtr (decompressor; **working name**) |
| $A69C / $A69E | ReadSrcByte / AdvanceSrcPtr | `LDA (SrcPtr),Y` falling into a 16-bit pointer increment |
| $A6A5 | WriteDstByte | `STA (DstPtr),Y` then 16-bit increment of DstPtr |
| $A6AE | ReadSrcHighNibble | `LDA (SrcPtr),Y` then four `LSR` |
| $B0E6 | ClearPokeyRegisters | stores 0 to $D200–$D207 |
| $B113 | LoadShadowColors | copies 8 bytes from `D_BBE2` into $02C0–$02C7 |
| $B11F / $B13D / $B15B | Copy0800To0C00 / Copy0C00To1000 / Copy0C00To1400 | each copies four 256-byte pages between fixed RAM blocks |

`Start` shows the game expands compressed ROM data into RAM at start-up: it copies 10 bytes ("HIGH SCORE")
to $200F, clears zero page, and decodes streams from `$A1E1` into $0800.. and from `$BE95` into $0600..
through `ExpandData`. So much of the "data" in ROM is compressed source for RAM tables (stage D will decode it).

## Not done yet (and why)
- The 53 unnamed subroutines and all zero-page game variables: meaning not yet established; names need
  traced behaviour (Stage D/E). `analysis/routine-catalog.txt` lists each with size, call count, hardware touched
  and callees, to prioritise. Sizes in it are approximate (nearest preceding label).
- Data: **now fully labelled** (every non-code byte); see `12-data-formats.md` for formats, evidence and what is still unknown.
- Screen codes `$00–$3F` = ASCII $20–$5F (verified on the title screen); codes with bit 7 are inverse video.

## The 39 routine names of 2026-11-14 (stage 35, 40)

Until then 39 subroutines were called `Sub_XXXX`. They were named from their role (the reads and writes in `23-function-table.md`, the chapters 13-22, the order in `24-function-relationships.md`); the **chapters 12-22 and the evidence summaries still use the old names** (an old name is `Sub_` and the address). `tools/labels.py` keeps the old label in the comment of each name; the ROM still rebuilds byte for byte.

Checked by reading the code on the same day: the names `EyesReturningSound` (was `Sub_B02C`: first proposed as 'ghost eaten pause', which was wrong - the pause block at `$B049` is reached by a jump from `FrameDispatch` and is now its own label `GhostEatenPause`), `HouseLeaveGhost2` / `HouseLeaveGhost3` (`Sub_B76D` / `Sub_B777`: each walks one ghost to the door column and then up; they differ only in the direction, right for ghost 2, left for ghost 3) and `ChaseTimerSirenSight` (`Sub_B5C7`: three jobs in one routine).

| Address | Old label | Name | Role |
|---|---|---|---|
| `$A632` | `Sub_A632` | `TitleClearScores1P` | clear the scores to '00' in title state 3 (one player) |
| `$A64E` | `Sub_A64E` | `TitleClearScores2P` | the same for two players (also draws both labels) |
| `$A6CC` | `Sub_A6CC` | `FrameDispatch` | the deferred VBI routine - title states 1-4 (draw), and in state 0 the whole game frame |
| `$AA2D` | `Sub_AA2D` | `TurnControl` | after a death or at the READY wait - switch players, load / save mazes, game over |
| `$AB26` | `Sub_AB26` | `CompareHighScore` | copy the player's score to the high score when it is larger (game over) |
| `$AB48` | `Sub_AB48` | `ClipEntitiesOnTunnelRow` | for each entity on y = $74 call the clip |
| `$AB57` | `Sub_AB57` | `ClipEntityAtTunnel` | mask the picture at the tunnel edges and wrap X (docs/16, OV-31) |
| `$ABC9` | `Sub_ABC9` | `BonusSound` | the bonus-eaten sound |
| `$AD0E` | `Sub_AD0E` | `DrawReadyScreen` | Pac-Man and ghosts in place, lives drawn |
| `$AD15` | `Sub_AD15` | `DrawLives` | the lives icons of the player on turn |
| `$AD42` | `Sub_AD42` | `LifeIcon2` | store X into the second lives cell(s) |
| `$AD45` | `Sub_AD45` | `LifeIcon1` | store X into the first lives cell |
| `$AD49` | `Sub_AD49` | `DrawAllInPlace` | draw the four ghosts and Pac-Man without moving them (zp_AE = 1) |
| `$AD5E` | `Sub_AD5E` | `ClearReadyText` | clear the READY! row ($0DED) |
| `$AD69` | `Sub_AD69` | `BlinkPlayerLabel` | blink the label of the player on turn every 16th jiffy |
| `$AD87` | `Sub_AD87` | `DrawLabel2UP` | draw '2UP' at $2021 |
| `$AD9F` | `Sub_AD9F` | `DrawLabel1UP` | draw '1UP' at $2004 |
| `$ADF1` | `Sub_ADF1` | `NewGameInit` | lives 3, Level := StartLevel, first board of a game |
| `$AE02` | `Sub_AE02` | `NewBoardInit` | copy the original maze, reset the counters and release timers for the player's level |
| `$AE1E` | `Sub_AE1E` | `ClearPlayerCounters` | dots eaten, pellets, bonus counter of player X |
| `$AF54` | `Sub_AF54` | `FrightenedTick` | the frightened clock, flashing and the end of the time |
| `$AFD7` | `Sub_AFD7` | `FrightenedSound` | the sound of the frightened phase |
| `$B02C` | `Sub_B02C` | `EyesReturningSound` | the sound of the eaten ghosts on their way home: AUDF2 steps 13..23 (`zp_F3`), AUDC2 $A4; played by `EyesAndHousePerFrame` while any eyes are returning (`zp_F2`) |
| `$B0BC` | `Sub_B0BC` | `DotSoundSweep` | the dot-eaten sweep |
| `$B0F1` | `Sub_B0F1` | `ClearPlayerMemory` | clear the player / missile pages |
| `$B100` | `Sub_B100` | `FillPlayerPages` | fill the five pages $2300-$27FF with A |
| `$B33A` | `Sub_B33A` | `EatDotAtPacMan` | the dot or pellet in Pac-Man's cell: clear, count, score, sound |
| `$B39F` | `Sub_B39F` | `PowerPelletCheck` | is Pac-Man on one of the four power-pellet squares whose flag is set (then `PowerPelletEaten`) |
| `$B54F` | `Sub_B54F` | `BlinkPowerPellets` | show / hide the four power-pellet cells |
| `$B55A` | `Sub_B55A` | `ShowPowerPellets` | set the four cells from the player's pellet flags |
| `$B5C7` | `Sub_B5C7` | `ChaseTimerSirenSight` | three per-frame jobs: ChaseTimer falls every 8th jiffy; the siren step 2..5 and, late in the board (dots eaten >= $E0 / $F0), `ForceChase`; the sight test of every ghost in state $08 / $10 |
| `$B616` | `Sub_B616` | `ForceChase` | late board - ghosts into chase, ChaseTimer = $FF |
| `$B69E` | `Sub_B69E` | `EyesAndHousePerFrame` | every frame: each eaten ghost (bit 6, not yet at the door, not the one in the pop-up) steers to the door square (124,100) and steps, state $44 at the door; `EyesReturningSound` while any are returning; then the ghosts in house states walk: $44 entering every frame (`HouseEnterStep`), $04 leaving every 4th jiffy |
| `$B738` | `Sub_B738` | `HouseLeaveStep` | up the door column, state $01 at the door row |
| `$B76D` | `Sub_B76D` | `HouseLeaveGhost2` | ghost 2 leaving the house (it starts left of the door): if X = $7C then `HouseLeaveStep` (up), else one step right; chosen by `HouseWaitingTick` and `EyesAndHousePerFrame` by the ghost number |
| `$B777` | `Sub_B777` | `HouseLeaveGhost3` | ghost 3 leaving the house (it starts right of the door): if X = $7C then `HouseLeaveStep` (up), else one step left |
| `$B781` | `Sub_B781` | `HouseEnterStep` | an eaten ghost ($44) inside the house, every frame: down the door column to y = $74, then sideways to its own x (ghost 2: $70, ghost 3: $88; ghosts 0 and 1 stay at $7C), then state $04 and its colour back ($B760) |
| `$B7A5` | `Sub_B7A5` | `HouseWaitingTick` | ghosts 1-3 waiting in the house (state $00 / $80), every 4th jiffy: the release timer falls and the ghost bobs (`HouseBobStep`); at 0 it leaves: ghost 3 `HouseLeaveGhost3`, ghost 2 `HouseLeaveGhost2`, ghost 1 `HouseLeaveStep` |
| `$B7D6` | `Sub_B7D6` | `HouseBobStep` | the bobbing step |
