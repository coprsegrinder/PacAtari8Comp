# 20 - Pac-Man's Pictures and the Death Sequence

Written 2026-11-11. Covers Pac-Man's nine pictures and how the game picks and draws them, and the whole death sequence: what Pac-Man, the four ghosts, the screen and the sound registers do from the moment a ghost touches him until the turn passes on.
Evidence: the code (`tests/test_death.py`, 9 tests), **a real game in Altirra in which the ghosts really killed Pac-Man 44 times and Pac-Man was drawn 27,181 times** (`analysis/evidence-death-summary.txt`; harness `tools/altirra_death.cmd`, analyzer `tools/analyze_death_log.py`), and **pixel-exact screenshots of Altirra's own window** for all nine pictures, the freeze, all 16 death-animation frames and the end state (`analysis/evidence-pacman-screenshots-summary.txt`; `tools/run_pacman_shots.ps1`, `tools/altirra_pacshots.cmd`, `tools/check_pacman_screenshots.py`). Second part (zp_AE, the restart, game over): `tools/altirra_afterdeath.cmd`, `tools/altirra_gameover.cmd`, `tools/analyze_afterdeath_log.py`, `analysis/evidence-afterdeath-summary.txt`, `analysis/evidence-gameover-summary.txt`, and three more screenshot targets in the same checker. The screenshots themselves are not committed.

## Pac-Man's pictures
Pac-Man is not a player but the four **missiles** (`GPRIOR` = `$11` makes them a fifth player in the colour of `COLPF3`, register `COLOR3` `$02C7` = `$2A`, rendered gold (210, 163, 58)). Each missile is two colour clocks wide and holds 2 bits of each memory byte, so the picture is 8 pixels wide: bit 7 at x = PacX ... bit 0 at x = PacX + 7 (missiles M3, M2, M1, M0 at `HPOSM3` = PacX, +2, +4, +6, `$B31B-$B32D`), one memory byte per scanline in the single-line missile memory at `$2300 + PacY`.
**Nine shapes** (`$BAFC-$BB54`, 10 rows each, `PacShapePtrs` `$BB65`): Full (a disc), and a first and second frame for Right, Left, Up and Down; the second frame is 10 bytes after the first (`PacMouthOffsets` `00 0A 00`).
**Drawing** (`MovePacMan` `$B179`, `$B2E9-$B339`): the 10 rows of the chosen shape go to the staging area `$0403-$040C` (the rows around them are 0), then 16 rows are copied to `$2300 + PacY` and the four `HPOSM` registers are set.
**Which picture** (all counts live, 27,181 draws; 27,181 of 27,181 staged byte strings equal the ROM shape `PacShapePtrs[Y] + X`, and 27,181 of 27,181 copies in missile memory equal the staged shape):
- The direction picks the shape: `PacDirection` up -> index 6, down 8, left 4, right 2 (20,833 of 20,833 direction pictures matched).
- **Moving** (`$B2D3`): `ChompPhase` (`$AB`) cycles; the pictures follow **Full, first frame, second frame, first frame, Full, ...** (consecutive pictures in the log: Full -> first 7,345, first -> second 7,344, second -> first 7,345, first -> Full 7,346). Phase 0 shows Full.
- **Standing** (stopped at a wall or waiting): the second frame of the direction, drawn again every frame (`LDA #$0A` at `$B2CA`; second -> second 2,264 times).
- **No direction yet** (start of a board): Full.
Pixel check (27 pictures, 3 captures each; 78 views of a non-empty picture): **the pixels equal the bitmap in every view**: set cells show the gold or, where a ghost, wall or dot has priority over the missiles, another colour (123 of 2,556 set cells); clear cells never show the gold; the column and row on the screen are exactly the game's (PacX, row), no offset needed.

## The death, frame by frame
Trigger (`$A923`): a ghost whose state has bit 7 and bit 6 clear touches Pac-Man (`18-frightened-eaten-house.md`; the killing ghosts seen: `$01` start route 20, `$02` chase 20, `$08` 3, `$10` 1). The code sets `zp_AA` bit 7 (the game's "Pac-Man frozen" flag: `MovePacMan` returns at once), silences the sound chip (`ClearPokeyRegisters`), `zp_AE` := 1 ("draw only, do not move", see below), **`DeathState` := 1** and **`zp_EE` := `$60`**. From then on `$A82F` calls `DeathSequence` and `DeathAnimation` once per frame instead of the normal game step.
A software model of the two routines, translated from the code, was run against the per-frame variables of all 44 deaths: **15,532 frame-to-frame steps, every variable (DeathState, zp_EE, DeathAnimActive/Frame/Delay, zp_F0/EF/F1, zp_24) equal, 0 mismatches**. One death takes **354 frames (5.9 s)** from `DeathState` 1 until `zp_24` becomes 1:

| Frames | DeathState | What happens |
|---|---|---|
| 97 | 1 | **Freeze.** The 96 frames count `zp_EE` down. Every frame `ToggleLegPhase` is called (the feet only change when `RTCLOK2 AND $0F` = 0, so six times) and all four ghosts are redrawn with their own direction (`StepAndDrawEntity`): **nothing moves** (16,896 redraws: 0 changed position or state), the pictures are the direction pictures, or the frightened/eyes picture of the ghost's state (16,896 of 16,896), the feet alternate (6 changes per ghost per death). Pac-Man keeps the picture he had. The 97th frame falls through into state 2. |
| first frame of the 59 | 2 | **The ghosts disappear: `HPOSP0-3` := 0** (the four ghosts are moved off the left edge; their pictures stay in memory and are never drawn again: **0 draws of a ghost after this point in 44 deaths**, and 51 of 51 screenshots show no ghost-coloured pixel on the playfield). `zp_F0` = `zp_EF` = `$35`, `zp_F1` = 0, `DeathAnimFrame` = 0, `DeathAnimActive` := 1, `DeathAnimDelay` = 7. |
| 59 + 60 + 9 | 3, 4, 5 | **Sound** (`AUDC1` = `$A8`, `AUDF1` as below); runs at the same time as the animation. |
| 129 | 6 | Silent wait of `$80` frames, then `zp_24` := 1: the turn handling takes over (`19-two-players.md`: lives, the other player, new board or game end). |

**The animation** (`DeathAnimation` `$AEF7`, runs in every one of those frames; each picture is held for 8 frames, `DeathAnimDelay` 7 counting down to 0):
- frame 0 (7 frames): `PacShapeUp2` (mouth open upwards), written over rows 3-12;
- frames 1-14 (8 frames each): one byte of `DeathPlotBytes` (`$BB57`) is written at row `DeathPlotRows[k-1] - 1` - the shape loses its top rows one by one and shrinks to a pillar and a base;
- frame 15 (8 frames): **`StarShape`** (`$BC07`, 16 rows): eight short rays around an empty centre, a "pop";
- then the 16 rows are cleared and the animation flag is reset (1 frame). The missile memory of the 17 frozen machines equals this simulation (17 of 17), and the screen equals the memory (48 of 48 views; the cleared end state: no gold in the cells, 3 of 3).

```
    frame 0       frame 3       frame 9       frame 12      frame 15
    ........      ........      ........      ........      ........
    ........      ........      ........      ........      ........
    ........      ........      ........      ........      ........
    ........      ........      ........      ........      ........
    ........      ........      ........      ........      ........
    #.....#.      ........      ........      ........      #..#..#.
    ##...##.      ........      ........      ........      .#.#.#..
    ###.###.      ###.###.      ........      ........      ........
    ###.###.      ###.###.      ...#....      ...#....      ##...##.
    #######.      #######.      #######.      ..###...      ........
    #######.      #######.      #######.      ..###...      .#.#.#..
    .#####..      .#####..      .#####..      .#####..      #..#..#.
    ..###...      ..###...      ..###...      ..###...      ........
    ........      ........      ........      ........      ........
    ........      ........      ........      ........      ........
    ........      ........      ........      ........      ........
```

**Sound registers** (the values written; no audio was listened to): `AUDC1` = `$A8` throughout; `AUDF1` follows, in every death exactly the model's 129 writes (44 of 44 deaths): four steps up by 8 from `$35` (53, 61, 69, 77), four steps down (85, 77, 69, 61), then the base is raised by 4 and the same up-down again (57, 65, 73, 81, 89, 81, ...), 15 cycles in all until the base is `$6D`; then 9 steps down by 8 from `$6D` to `$25`. It is a rising warble that glides lower at the end.

## zp_AE: "draw only, do not move" (verified)
`StepAndDrawEntity` (`$B902`) is the routine that moves a ghost one step in its direction and draws it. `zp_AE` is a flag that turns the moving off: in each of the four direction cases the code reads `zp_AE` (`$B906`, `$B916`, `$B926`, `$B934`) and skips the coordinate change when it is not 0 (up/down: `EntityY` -/+ 2, left/right: `EntityX` -/+ 1); the picture is drawn in any case. These are the only reads of `zp_AE` in the whole ROM (`test_every_access_to_zp_ae`). It is set to 1 by the death trigger (`$A92E`, so that the freeze can redraw the ghosts without moving them) and by `Sub_AD49` (`$AD4B`; draws the four ghosts and Pac-Man in place and clears it again at `$AD59`); `InitBoard`'s zero-page clear zeroes it as well.
Live (61,919 calls of the routine in a game with 52 deaths): **with `zp_AE` = 0 all 41,739 calls moved the ghost exactly by the rule** (up (0,-2): 9,775; down (0,+2): 12,114; left (-1,0): 9,723; right (+1,0): 10,127); **with `zp_AE` = 1 there were 20,180 calls and not one moved a ghost**, and every one of them was in the death freeze (19,968 = 52 x 96 x 4) or inside `Sub_AD49` (212); `zp_AE` was never 1 anywhere else. So the "frozen" ghosts of the death sequence are not frozen by a pause but by calling the normal draw routine with the move switched off - which is also why their feet still alternate.

## After the death: the restart and the READY! display (verified)
When `DeathSequence` has counted `zp_F1` down it sets `zp_24` := 1 and the per-frame routine (`$A805`) hands over to `Sub_AA2D`. For one player with lives left (`$AAE0`) everything happens **in one frame**, then the game waits:

| Frame (0 = `zp_24` := 1) | What happens |
|---|---|
| 1 | `InitBoard` (`$ADAF`): clears the player and missile memory, **clears zero page `$80-$FF`** (this is what ends the frozen-Pac-Man flag `zp_AA`, `DeathState`, `zp_AE`, `FrightenPhase`, `ChaseTimer`, `ChompPhase`, `LegPhase`, all ghost states and the house timers), reloads the colour registers from `ColorsGame`, the move delays for the level, and `ZeroPageInit80` (all ghosts and Pac-Man back to their start squares: ghost 0 at (124,100), ghosts 1-3 at (124,116), (112,116), (136,116), Pac-Man at (124,164) facing left). `DrawLevelIndicator` (`$AC93`) first writes **the READY! text: ten tiles `$A2-$AB` at `$0DEF-$0DF8`** of the maze row under the ghost house, then the fruit row. `Sub_AD0E`: `Sub_AD49` draws the four ghosts (zp_AE = 1) and Pac-Man (shape Full) at the start squares, **the player's life counter is decremented** (`$AD13`) and the life icons are drawn. Back at `$A810` the code sets `zp_24` := 2 and `zp_25` := `$40`. |
| 2 - 66 | The wait: `$A81F` counts `zp_25` down 64, 63, ..., 0 (65 frames). **Nothing moves or changes**: no ghost, no Pac-Man, the READY! row, the lives, the dots, the power-pellet tiles (steady, not blinking: the blink routine is not called) and the colours stay as they are, **and no sound register is written at all** (the siren is silent). |
| 66 | `zp_25` = 0: `zp_24` := 0 and `$A800` runs: **ghost 0's state 0 -> 1 (start route), `Sub_AD5E` clears the READY! row** (14 bytes at `$0DED`), and the normal game step runs again from the next frame. |

So the pause is **66 frames (1.1 s) from the end of the death routine to the first move**. What the death keeps: the dots eaten, the power-pellet flags and the bonus counter (`zp_34..zp_43`, below `$80`), the score, the maze in `$0C00` with its eaten dots; what it resets: everything in `$80-$FF`, so a frightened period, the chase timer and the house timers start again.
Live (`tools/altirra_afterdeath.cmd`, 52 deaths followed to the start of play; `analysis/evidence-afterdeath-summary.txt`):
- **52 of 52 deaths took exactly 66 frames** from the end of the death routine to the start of play, with the 9 events (InitBoard, level indicator, Sub_AD0E, Sub_AD49, turn start, `zp_24` := 2, start of play, clear READY) in the order above every time; the wait lasted 65 frames in all 52 with `zp_25` = 64..0.
- The first frame after the restart equalled the model in all 52: `zp_24` = 2, `zp_25` = 64, `DeathState` 0, `zp_AE` 0, `zp_AA` 0, FrightenPhase/countdown/ChaseTimer 0, ChompPhase and LegPhase 0, all four ghost states 0 at the `ZeroPageInit80` positions, Pac-Man at (124,164) facing left, the eight colour registers = `ColorsGame`, the READY tiles `$A2-$AB` in place; the life counter was exactly one lower than the value logged before the decrement (52 of 52).
- Dots eaten, power-pellet flags and bonus counter unchanged through the death (52 of 52); everything on the screen constant during the wait (52 of 52); first frame of play: ghost 0 in state 1, ghosts 1-3 in state 0, READY row cleared (52 of 52).
- The READY row is written only by `DrawLevelIndicator` (10 writes per death) and cleared by `Sub_AD5E` (14 writes per death); **no sound register was written between the end of the death and the start of play** (0 writes).
- **Screenshots** (`Ready_wait`, `Ready_wait_start`, `Ready_play`, 3 captures each): the Pac-Man picture (Full) and all four ghost pictures equal their memory (12 of 12 Pac-Man views, 48 of 48 ghost views over the freeze and restart targets); **the READY! text on the screen equals the charset glyphs of the tiles `$A2-$AB` pixel for pixel** (14 tiles x 4 x 8 pixels in 6 of 6 views: glyph pixel value 3 = gold (the colour of Pac-Man, `COLPF3`), value 0 = black, no other value occurs; the text row is at scanline 136 = screen RAM row 12), and **after the restart the row is blank (3 of 3)**.

## Game over: the death of the last life (verified up to the end of the countdown)
`Sub_AA2D` finds no lives left (`$AAE0` -> `$AAEF`): it writes **the 14 tiles `$AC-$B9` ("GAME OVER" in the maze charset) at `$0DED`**, sets `COLOR3`/`COLPF3` to `$44` (the text is drawn in red), compares the score with the high score (`Sub_AB26` for both players), then `zp_24` := 0, `zp_20` := 1, `zp_1E` := `$E2` (226). Live (`tools/altirra_gameover.cmd`, the third death of a game; `analysis/evidence-gameover-summary.txt`): the frame after the death routine shows exactly that (GAME OVER tiles, `COLOR3` = `$44`, lives 0, `zp_20` = 1, `zp_1E` = 226); then **`zp_1E` counted down from 226 to 1 in 225 steps, 8 frames apart (224 of 224 gaps), 1,797 frames (about 30 s)**, while the screen stayed exactly as it was (ghosts hidden, Pac-Man's cleared rows, text, lives, dots). After that the per-frame routine was never called again in the log: the code at `$A4ED` sets `zp_19` := 4 and leaves the board screen (back to the title/attract screens); pressing a trigger or Start during the countdown jumps to `$A537` and starts a new game (code only).

## What was verified how
- **Static** (`tests/test_death.py`): the bytes of the selection, drawing, trigger, `DeathSequence` and `DeathAnimation`; the model's durations (354 frames, 97/59/60/9/129), animation counts (7, 8 x 15, 1) and the first AUDF1 values.
- **Live, game running** (44 real deaths, 27,181 draws): the model matched every frame; Pac-Man's pictures matched the ROM; the ghosts froze, were redrawn and then hidden as described; the 129 AUDF1 writes matched.
- **Screenshots** (30 frozen machines x 3 captures of Altirra's own window): 9 shapes, the freeze, 16 death frames, the end state, and the READY! wait and restart (ghost pictures 48 of 48, Pac-Man 90 views, READY! text pixel for pixel): 0 deviations.
- **After the death** (52 real restarts, 1 game over): the model of the restart matched every frame; zp_AE: 61,919 calls of the move/draw routine matched the rule.

## Not covered
- Sound: the death glide, the siren and every other sound in the ROM are now measured and explained in `22-sound.md` (the owner's one listening, to the start tune, is the only one). That the restart wait is silent is verified: 0 register writes.
- Game over: the high-score comparison (`Sub_AB26`), the return to the title screen and the keys during the countdown are now traced and verified in `21-start-gameover-title.md`. Two-player restarts (the other player's turn, `PLAYER ONE/TWO` labels) are in `19-two-players.md` and were not repeated here.
- The first board start of a game (the start tune, `zp_22`, `zp_A3`) is now verified frame by frame in `21-start-gameover-title.md` (11 games, 704 tune steps).
- Test aids: a joystick bot (`STICK0` poked) and refilled life counters made the deaths happen (the game-over run had no refill); for the shape screenshots Pac-Man was made invulnerable and frozen with the game's own `zp_AA` flag. No human played these runs. `21-start-gameover-title.md` audits the aids (a table) and repeats the start, game over and title with **no refill and no PC move**, only the controller values injected; a real key event did not reach the game, and still no human played.

- The joystick path of `MovePacMan` (the wanted-direction buffer, the refusal of two directions, the corner flag) and the contact test are specified and checked in `41-input-processing.md` (stage 63).
