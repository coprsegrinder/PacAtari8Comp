# 16 – The Ghost Frames

Written 2026-11-10 (step C11). **The meaning of every ghost frame is now understood and verified**: which bitmap the game draws for a ghost, why, and how the picture animates.
Evidence: the frame-selection code (`tests/test_ghost_frames.py`, 7 tests), the bitmaps, and a live trace of **47,510 ghost draws with 0 deviations from the rule**
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

## Not covered
- Pac-Man's own frames (documented in `12-data-formats.md`: `PacMouthOffsets`, shapes) and the ghosts during the death sequence (they are hidden by setting their horizontal positions to 0, not by a different frame).
- A pixel-by-pixel screenshot comparison of each of the 11 pictures (the bitmaps were checked as data and the colours as register values; a capture of the game was used earlier only to name the colours).
