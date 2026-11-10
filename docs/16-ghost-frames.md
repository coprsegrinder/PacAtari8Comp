# 16 – The Ghost Frames

Written 2026-11-10 (step C11). **The meaning of every ghost frame is now understood and verified**: which bitmap the game draws for a ghost, why, and how the picture animates.
Evidence: the frame-selection code (`tests/test_ghost_frames.py`), the bitmaps, and a live trace of **47,510 ghost draws with 0 deviations from the rule**
(`analysis/evidence-ghost-frames-summary.txt`).

## The six shapes
Each shape is 10 rows of 8 pixels at `$BAC0 + 10 × index`; the routine adds an 11th row (the feet) and draws 16 rows to the ghost's player.

| Index | Address | Name | Used when | What it looks like |
|---|---|---|---|---|
| 0 | `$BAC0` | `GhostShapeUp` | normal ghost moving up (`EntityDir` 1) | eye holes high (rows 2–4) |
| 1 | `$BACA` | `GhostShapeDown` | moving down (`EntityDir` 2) | eye holes low (rows 6–8) |
| 2 | `$BAD4` | `GhostShapeLeft` | moving left (`EntityDir` 4) | eye holes shifted left (columns 1 and 3) |
| 3 | `$BADE` | `GhostShapeRight` | moving right (`EntityDir` 8) | eye holes shifted right (columns 3 and 5) |
| 4 | `$BAE8` | `GhostShapeFrightened` | `GhostState` bit 7 set (power pellet) | same body, different face: eyes (rows 3–5) and a zigzag mouth (rows 7–8) |
| 5 | `$BAF2` | `GhostEyesShape` | `GhostState` bit 6 set (eaten, returning to the house) | only two vertical eye bars (rows 3–5, columns 2 and 4), no body, no feet |

The four direction shapes are **identical except for the eyes** (the head top and bottom rows are the same); the eye holes are 6 enclosed background pixels (two eyes of three); their centre is at row 3.0 (up) or 7.0 (down) with column 3.0, and at column 2.0 (left) or 4.0 (right)
(the test flood-fills the outside of each bitmap). So the ghost always **looks the way it is moving**.

## The selection rule (`StepAndDrawEntity`, `$B902`–`$B998`)
After moving the entity one step in `EntityDir` (1 pixel sideways, 2 pixels up or down) the routine chooses the frame:
1. frame offset from the direction: up `$00`, down `$0A`, left `$14`, right `$1E`;
2. if `GhostState` bit 7 (frightened): offset := `$28` (frightened shape);
3. if `GhostState` bit 6 (eaten): offset := `$32` (eyes shape) and feet row := 0 (this wins over rule 2);
4. otherwise the **feet row** (the 11th row, `$041C`) is `$AA` when `LegPhase` (`zp_AF`) is non-zero and `$54` when it is zero.
Then `SrcPtr = $BA00 + $C0 + offset`, the 10 rows go to `$0412–$041B`, the feet row to `$041C`, `HPOSP0+ghost` := `EntityX`, and 16 rows from `$0410` are copied to player memory at page `$24 + ghost`, offset `EntityY`.

### Animation
`LegPhase` is toggled between 0 and 1 by `ToggleLegPhase` (`$AC05`) **every 16th jiffy** (when `RTCLOK2 AND $0F` = 0); it is called from the main game step and from the death sequence. The two feet patterns
`$54` = `.#.#.#..` and `$AA` = `#.#.#.#.` are complements, so the legs alternate; with the four directions that gives 4 × 2 normal images, 2 frightened and 1 eyes image: **11 distinct pictures** in all.

### Colours (the player's colour register, `PCOLR0+ghost`)
Normal ghosts keep their own colour from `ColorsGame` (`$44` dark red, `$4A` pink, `$D8` green, `$28` dark gold). Frightened ghosts get `$84` (blue) when bit 0 of `FrightenPhase` is set and `$0C` (white) otherwise (`$AFBE`–`$AFD6`);
the eyes of an eaten ghost are `$0C`: the routine at `$B09D` finds the player whose colour is the pop-up colour `$DC` and sets it to `$0C` (`$B0A8`).

## Verification
- **Live (all 47,510 draws, four ghosts):** the frame address and the feet byte equalled the rule on every draw. Draws per frame: up 5,176, down 5,809, left 13,451, right 14,214, frightened 5,546, eyes 3,314.
  Colours at draw time: normal ghosts `$44`, `$4A`, `$D8`, `$28` (about 9,600 each), frightened `$84` (4,174) and `$0C` (1,372), eyes `$0C` (3,314).
  `LegPhase` toggled 2,215 times, always when `RTCLOK2 AND $0F` = 0, normally 16 frames apart (2,189 gaps; the longer gaps are stretches where the main step did not run).
- **Static:** the bytes of the selection code, the toggle routine and its two callers, and the bitmap analysis above (eye positions, identical bodies) are in `tests/test_ghost_frames.py`.
- The test aids used (emulated machine only): the game is started from its own start-game code, ghosts do not kill Pac-Man, Pac-Man is moved around and onto power pellets and ghosts so that every ghost state occurs
  (`tools/altirra_ghostframes.cmd`, `tools/analyze_ghost_frames_log.py`).

## Screenshot check: the pixels on the screen equal the bitmaps
Added 2026-11-10. The bitmaps and colours above were first checked as data; this check compares **what Altirra actually renders** with them.
- **Method** (`tools/run_ghost_shots.ps1`, `tools/altirra_ghostshots.cmd`, `tools/check_ghost_screenshots.py`): for each of the 11 pictures (plus frightened in both colours, plus eyes in white) the game is run unattended until the picture is drawn,
  then two whole frames with no ghost draw are waited for and the emulated machine is stopped (a debugger break; test aid in emulated RAM/PC only, ROM untouched). The RAM (player memory `$2400-$27FF`, entity tables, colours) is logged and the window of Altirra itself is captured
  (`PrintWindow`, which reads only that window). With fewer quiet frames the screen still showed the previous picture; that timing error is why the freeze waits for two.
- **What is compared:** for every ghost on every capture, its player memory must be exactly one of the 11 pictures built from the ROM, and the screen must show it: in each of the 8 x 11 cells the cell centre has one colour where the bit is set and a different one where it is clear.
  The window scale is fitted from the normal ghosts (about 5.47 pixels per colour clock and 3.17 per scanline, residual <= 1.3 px; a sub-cell offset of at most 1 pixel was needed).
- **Result** (`analysis/evidence-ghost-screenshots-summary.txt`; 14 stopped states x 3 captures = 42 captures, 168 ghost views): **0 deviations**. 159 views were compared pixel for pixel, 9 were skipped because two ghosts overlap
  (their colours merge, so cells cannot be told apart). **All 11 pictures were seen on the screen** (up x2 feet rows, down x2, left x2, right x2, frightened x2, eyes). Every ghost was found exactly where the game says
  (column = `EntityX`, row = player-memory row; offset 0 in all views). The ghost the picture was waited for held exactly the ROM shape and feet row that were being drawn in all 42 views.
- **Colours on the screen:** normal ghosts (144,24,41) / (254,135,155) / (49,156,13) / (170,126,0) for `$44 / $4A / $D8 / $28`; frightened **blue (18,62,178)** for `$84` and **white (205,198,210)** for `$0C`; the eyes are the same white (205,198,210) as the status text (`$0C`).
  One capture of the eyes shows them in the ghost's own colour: the ghost had just reached the house, which restores its colour before the picture is redrawn (the register already held `$44`); the eyes drawn with `$0C` were white on the screen.
- **Where things are** (needed for the comparison): `EntityX` is `$8A+ghost` (it is written to `HPOSP0+ghost`), `EntityY` is `$85+ghost`; the 16 rows copied by `$B991` start at player-memory offset `EntityY`, the first two are blank, so shape row *r* is at `EntityY + 2 + r`.
- **New observation - the tunnel edge:** a frightened ghost at `EntityX` = 195 (the right tunnel mouth) had its player memory equal to the frightened picture **ANDed with `$F8`** (and with `$FC` in another capture): the game cuts the picture at the screen edge, and the screen shows the cut ghost.
  The routine that applies the mask has not been analysed (see below).

## Not covered
- Pac-Man's own frames (documented in `12-data-formats.md`: `PacMouthOffsets`, shapes) and the ghosts during the death sequence (they are hidden by setting their horizontal positions to 0, not by a different frame).
- The code that clips ghosts at the tunnel edges (masks `$F8`, `$FC` seen; the left side and the other masks were not captured), and ghosts inside the tunnel.
- Overlapping ghosts (merged colours) were not compared pixel by pixel.
