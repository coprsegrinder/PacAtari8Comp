# 20 - Pac-Man's Pictures and the Death Sequence

Written 2026-11-11. Covers Pac-Man's nine pictures and how the game picks and draws them, and the whole death sequence: what Pac-Man, the four ghosts, the screen and the sound registers do from the moment a ghost touches him until the turn passes on.
Evidence: the code (`tests/test_death.py`, 6 tests), **a real game in Altirra in which the ghosts really killed Pac-Man 44 times and Pac-Man was drawn 27,181 times** (`analysis/evidence-death-summary.txt`; harness `tools/altirra_death.cmd`, analyzer `tools/analyze_death_log.py`), and **pixel-exact screenshots of Altirra's own window** for all nine pictures, the freeze, all 16 death-animation frames and the end state (`analysis/evidence-pacman-screenshots-summary.txt`; `tools/run_pacman_shots.ps1`, `tools/altirra_pacshots.cmd`, `tools/check_pacman_screenshots.py`). The screenshots themselves are not committed.

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
Trigger (`$A923`): a ghost whose state has bit 7 and bit 6 clear touches Pac-Man (`18-frightened-eaten-house.md`; the killing ghosts seen: `$01` start route 20, `$02` chase 20, `$08` 3, `$10` 1). The code sets `zp_AA` bit 7 (the game's "Pac-Man frozen" flag: `MovePacMan` returns at once), silences the sound chip (`ClearPokeyRegisters`), `zp_AE` := 1, **`DeathState` := 1** and **`zp_EE` := `$60`**. From then on `$A82F` calls `DeathSequence` and `DeathAnimation` once per frame instead of the normal game step.
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

## What was verified how
- **Static** (`tests/test_death.py`): the bytes of the selection, drawing, trigger, `DeathSequence` and `DeathAnimation`; the model's durations (354 frames, 97/59/60/9/129), animation counts (7, 8 x 15, 1) and the first AUDF1 values.
- **Live, game running** (44 real deaths, 27,181 draws): the model matched every frame; Pac-Man's pictures matched the ROM; the ghosts froze, were redrawn and then hidden as described; the 129 AUDF1 writes matched.
- **Screenshots** (27 frozen machines x 3 captures of Altirra's own window): 9 shapes, the freeze (Pac-Man plus the four frozen ghosts, 12 of 12 ghost views equal their player-memory pictures), 16 death frames, the end state: 0 deviations.

## Not covered
- The sound was not listened to (registers only); the siren and other sounds are still open.
- `zp_AE`: set to 1 here and cleared at board start (`$AD4B`, `$AD59`), read by the ghost drawing (`$B906-$B934`); its effect on the pictures was not analysed.
- What happens after `zp_24` becomes 1 beyond the turn logic of `19-two-players.md` (new board set-up, the "get ready" display) was not traced frame by frame.
- Test aids: a joystick bot (`STICK0` poked) and refilled life counters made the deaths happen; for the shape screenshots Pac-Man was made invulnerable and frozen with the game's own `zp_AA` flag. No human played these runs.
