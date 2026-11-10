# 15 – The Small Tables Around `$BBAB–$BBF7`

Written 2026-11-10 (step C11). Everything in this region is now identified and verified: the **sight (line-of-sight) data** used by `GhostSeesPacMan`, the **colour tables**, and the two
tables already covered in `14-levels.md` (`HouseReleaseTimers` `$BBF2–$BBF7` and the start of `FrightenFrames` `$BBF8`). The headline finding is that the ghosts' sight test **does not
use the sight lists the way their layout intends**: the shipped code reads the offset tables themselves. Names are in `tools/labels.py`; tests are `tests/test_sight_colors.py` (7 tests);
live numbers are in `analysis/evidence-sight-colors-summary.txt`.

| Address | Name | What it is |
|---|---|---|
| `$BBAB–$BBB7` | `SightListsX` | five `$FF`-terminated lists of x blocker coordinates |
| `$BBB8–$BBC1` | `SightOffsetsX` | 10 offsets, one per junction row, into `SightListsX` |
| `$BBC2–$BBD7` | `SightListsY` | five `$FF`-terminated lists of y blocker coordinates |
| `$BBD8–$BBE1` | `SightOffsetsY` | 10 offsets, one per junction column, into `SightListsY` |
| `$BBE2–$BBE9` | `ColorsGame` | `PCOLR0–3`, `COLOR0–3` for game play |
| `$BBEA–$BBED` | `ColorsTitle` | `COLOR0–3` for the title screen |
| `$BBEE–$BBF1` | `ColorsDli` | four colours for the display-list-interrupt bands |
| `$BBF2–$BBF7` | `HouseReleaseTimers` | see `14-levels.md` |

## The sight test (`GhostSeesPacMan`, `$BA19`)
Called for ghosts in the patrol states (`$08`, `$10`). It answers "may this ghost start chasing Pac-Man?" and, if yes, sets `GhostState := 2` and `ChaseTimer := $A0` (`$BAB7`).
Exact rule (reproduced in `tools/sight_model.py` from the ROM bytes):
1. **Same pixel row:** the ghost's y equals Pac-Man's y *and* that y is one of the 10 junction rows (`JunctionYList`); otherwise no sight.
   **Same pixel column:** the ghost's x equals Pac-Man's x and that x is a junction column. A ghost that is on neither returns at once.
2. The ghost must be **facing Pac-Man** (direction right if he is to its right, left if to its left, down if he is below, up if above).
3. A list scan decides whether something is in between: scan elements from `list[y]`, where `y` is the junction row/column index, until an element is at least the nearer coordinate or `$FF` is reached.
   `$FF` → clear; otherwise clear only if that element is at least the farther coordinate.
4. **Ghost 2 only reacts when bit 7 of `RTCLOK2` is clear** (about half of the time); the other ghosts always do.

### What the shipped code really scans
The data is laid out as an **offset table followed by lists**: `SightOffsetsX` = `00 0C 02 06 00 06 00 09 02 0C` holds exactly the start offsets (0, 2, 6, 9, 12) of the five lists in
`SightListsX` (`[7C]`, `[58 7C 9E]`, `[58 9E]`, `[3C AC]`, `[]`); `SightOffsetsY` = `00 03 0A 0C 11 11 0C 0A 03 00` is mirror-symmetric over the ten columns and holds exactly the start
offsets (0, 3, 10, 12, 17) of the five lists in `SightListsY`. But the code does `LDA $BBB8,Y` / `LDA $BBD8,Y` with `Y` = the row or column index: it never loads an offset and never
adds the list base, so it scans **the offset bytes themselves** and then whatever follows them.

Consequences (all computed from the bytes and then confirmed by the running game):
- **Horizontal:** the small offset bytes are skipped, the scan lands on the second x list for every row, so only **x = 100 (`$64`) and x = 132 (`$84`)** ever block. Sight along a row works inside each of three
  zones (x ≤ 100, 100 < x ≤ 132, x > 132) and never across their borders, whatever the walls are.
- **Vertical:** the scan runs from `SightOffsetsY` into the colour tables that follow (`44 4A D8 28 86 …`), so the only blocking values are `$44` (68) and `$4A` (74): a ghost and Pac-Man see each other
  vertically unless one of them is in the top band (y ≤ 68) and the other below it. The table values `$D8`… and the `$FF` further on are never reached.
- So the sight test is far more permissive than a real line of sight and is **independent of the maze walls**.

### Verification
- **Live:** `tools/altirra_sight.cmd` logged every same-row / same-column test in the running game with the inputs the code uses; **the model gave the game's answer on all 6,069 tests** (51 chases started,
  6,018 refusals; horizontal and vertical). Ghost 2 rule: of the tests whose geometry said "sees", ghost 2 chased in 13 of 13 with `RTCLOK2 < $80` and in 0 of 137 with `RTCLOK2 ≥ $80`; the other ghosts chased
  in 17 of 17 and 21 of 21 regardless of `RTCLOK2`.
- **Design intent (inference, evidence stated):** the offset values coincide exactly with the list starts and the vertical offsets are symmetric, so the data was built for an offset lookup. Applying the offsets
  to pairs of real junctions agrees with the maze's junction connectivity on **732 of 746** horizontal and **648 of 728** vertical pairs; what the shipped code does agrees on only **478** and **360**.
  The lists are therefore close to, but not exactly, a wall map (for example the list for junction row 7 has a blocker at x = 60 where the maze is open), and the ROM cannot tell whether the missing offset step
  is a slip or a deliberate simplification; I describe the behaviour, not the motive.

## The colour tables
The Atari colour byte is hue (high nibble) and luminance (low nibble). Names below are what Altirra's NTSC palette renders, checked by sampling a game capture
(ghost 0 (144,24,41), ghost 1 (254,135,155), ghost 3 (170,126,0), ghost 2 (49,156,13), Pac-Man (210,163,58), wall (76,98,218), dot (240,147,101)).

| Table | Bytes | Loaded by | Becomes |
|---|---|---|---|
| `ColorsGame[0–3]` | `44 4A D8 28` | `LoadShadowColors` (`$B113`) | `PCOLR0–3`: **ghost 0 dark red, ghost 1 pink, ghost 2 green, ghost 3 dark gold** |
| `ColorsGame[4–7]` | `86 0C 00 2A` | same | `COLOR0–3`: **blue (maze walls), light (status text), black, gold** — gold is also Pac-Man (his missiles take `COLPF3`: `GPRIOR` = `$11`) |
| `ColorsTitle` | `DA 0C 00 2A` | `InitDisplay2` (`$A610`) | title `COLOR0–3`: **green** text, light, black, **gold** (logo and the highlighted words SELECT, OPTION, START) |
| `ColorsDli` | `3A 44 2A DA` | `$A4BC` (each value is EORed with `COLRSH` and ANDed with `DRKMSK`, the attract-mode fade) | `DliColors` (`$5E–$61`): **peach, red, gold, light green** |

The game's display-list interrupts apply `DliColors` to bands of the screen (hardware writes logged with their scanline, 19,769 frames of game play):

| Scanline | Written | Source |
|---|---|---|
| 48 | `COLPF1` = `ItemColor` (`$A0`: `$44` red, or `$DA` light green on levels 6–9), `COLPF2` = `$3A` peach | `DliHandler1` band 1: peach dots / red fruit glyphs in the maze body |
| 208 | `COLPF1` = `$44` red | band 2 (`DliColors[1]`) |
| 216 | `COLPF0` = `$DA` light green, `COLPF3` = `$2A` gold | band 3 (`DliColors[3]`, `DliColors[2]`) for the bottom rows |
| 231 | `COLPF3` = `$00` | band 4 (also clears `COLPM0–3`) |
| 250 | `COLPF0` `$86`, `COLPF1` `$0C`, `COLPF2` `$00`, `COLPF3` `$2A`, `COLBK` `$00` | the OS copying the shadow registers (`ColorsGame`) at vertical blank |

Why those registers colour those things: in the maze charset the wall glyphs use only pixel value 1 (`COLPF0`, blue), the dot and power-pellet glyphs only value 3 (`COLPF2`, peach), and the fruit glyphs values 2 and 3 (`COLPF1` = `ItemColor`, and peach).

`ItemColor` was verified live for levels 0–29 and 100–109 (`$DA` on levels 6, 7, 8, 9, `$44` otherwise); the green/red fruit icons seen on the title screen for start levels 6 and 8 (green) against the rest (red) follow the same rule.
On the title screen `DliHandler2` writes `COLPF1` = `$44` (the red "1 PLAYER GAME") and `COLPF2` = `$3A`.

## Not covered
- The colours of the frightened and eaten ghosts are written by code, not from these tables; they were observed in `16-ghost-frames.md`.
- Colour of the bottom-row items other than by the rule above (identified from the code and the scanline log; no pixel-by-pixel check of every item).
- The sight test while a ghost is frightened or eaten (it is only called from the patrol states).
