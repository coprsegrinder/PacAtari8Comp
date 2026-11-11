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
- **Design intent:** see the next section: the lists are an exact map of the maze's closed corridors, apart from three entries, so the data was built for an offset lookup that the shipped code does not do.

## What the list elements mean (confirmed against the maze)
Tool: `tools/describe_sight_lists.py`; tests: `ListMeaning` in `tests/test_sight_colors.py`. The check is static (the data against the maze's own junction map `JunctionExits`, RAM `$060E`), the scan rule is the one the code implements (an element `e` blocks the two junction coordinates `lo < hi` when `lo <= e < hi`).
- **Each list is the set of closed corridors on one junction row (x lists) or one junction column (y lists).** An element is a coordinate inside the gap between two neighbouring junctions that are *not* connected, or the coordinate of a lattice point that does not exist (`$64`, `$84` in the y lists: the house rows are missing in columns 0, 1, 8, 9). Every element of the x lists (15 over the ten rows) lies strictly between two neighbouring junction columns, and every y element lies strictly between two neighbouring junction rows or equals a missing row's coordinate. Example, row 2 (y = 84): the maze is closed between columns 2 and 3, 4 and 5, and 6 and 7, at x = 90, 124, 158 (gap midpoints); the list is `$58 $7C $9E` = 88, 124, 158 (any value inside the gap does; the first is slightly off the midpoint).
- **The offset tables pick the right list for each row and column** (`SightOffsetsX` = `0 12 2 6 0 6 0 9 2 12`, `SightOffsetsY` = `0 3 10 12 17 17 12 10 3 0`): rows 1 and 9 are fully open (empty list), rows 0, 4, 6 are cut only at the centre wall (`$7C`), rows 3 and 5 (the house rows) have two cuts, columns 3/6 and 4/5 and 1/8 have the lists of their own wall pattern, and the lists are mirror-symmetric (column 1 = column 8, 3 = 6, 4 = 5, 2 = 7, 0 = 9).
- **Agreement with the maze, junction pair by junction pair** (unordered pairs on the same row / column): as shipped **366 of 373 on rows and 324 of 364 on columns** (the 732/746 and 648/728 counted above, as ordered pairs). All 47 disagreements come from **three entries**:
  | Where | Shipped | The maze says | Effect of fixing it |
  |---|---|---|---|
  | row 7 (y = 164), first blocker | `$3C` (x = 60, between columns 0 and 1) | the corridor is closed between columns 1 and 2: about `$4C` (x = 76; mirror of the right-hand `$AC` = 172) | rows 366 -> 373 |
  | columns 2 and 7, the only element | `$3C` (y = 60, between rows 0 and 1) | closed between rows 8 and 9: `$BC` (y = 188) | columns 324 -> 356 |
  | columns 0 and 9 | `$64 $84` | also closed between rows 7 and 8: no element for `$AC` (y = 172) | columns 356 -> 364 (each fix is counted on its own in the tests) |
  With the three corrections **every one of the 373 + 364 pairs agrees with the maze.** That the same value `$3C` stands where `$4C` and `$BC` are expected, and that an entry is missing, suggests slips made when the tables were typed in; the ROM cannot show whether this is so, and since the shipped code never reads the lists (it reads the offset tables themselves, above), the slips have no effect on the game. A port that wants the original behaviour copies the shipped code's effect (blocking at x = 100 and 132 and at y = 68 and 74 only); one that wants the *intended* sight test uses the lists through the offsets and may correct the three entries.

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
- The colours of the frightened and eaten ghosts are written by code, not from these tables; they are **verified live and explained** in `16-ghost-frames.md` ("Colours of frightened and eaten ghosts").
- Colour of the bottom-row items other than by the rule above (identified from the code and the scanline log; no pixel-by-pixel check of every item).
- The sight test while a ghost is frightened or eaten (it is only called from the patrol states).

## The sight test while a ghost is frightened or eaten (verified 2026-11-11)
**Rule: only a ghost in state `$08` (patrol travel) or `$10` (patrol) is ever tested.** `GhostSeesPacMan` has exactly one caller, the loop at `$B603` (once per frame, in `Sub_B5C7`), which compares the state with `$08` and `$10` for equality (`tests/test_sight_colors.py`, `SightOnlyForPatrolGhosts`). Consequences, all from that one comparison:
- **Frightened ghosts** have bit 7 set, so a patrol ghost that becomes frightened is `$88` or `$90` and no longer equals `$08`/`$10`: it is **not tested** and can never be switched to chase by sight, however clearly Pac-Man is in line. (It does not need to be: a frightened ghost already steers by the Pac-Man target, mirrored, see `18-frightened-eaten-house.md`.)
- **Eaten ghosts** (`$42` eyes, `$44` at the door) are never tested either; they go home and come back as chase (`$02`).
- When the frightened time ends a frightened patrol ghost does **not** return to patrol: `$AF8C-$AFA0` turns `$88`/`$90` into `$20` (corner), from where the normal corner arrival gives a fresh patrol (`17-ghost-transitions.md`). So the sight test resumes only after that.
- Ghosts in the house, on the start route, chasing or going to a corner are not tested for the same reason (they were already not tested before; this is just the same comparison).
Live (`tools/altirra_sight_states.cmd`, `tools/analyze_sight_states_log.py`, `analysis/evidence-sight-states-summary.txt`; Pac-Man invulnerable and, by test aid, kept on the line of sight of one ghost at a time, power pellets eaten at many moments of each board including whenever a ghost was in `$10`; 49,800 frames of the loop, levels 0-39, 199,200 ghost-frames):
- **GhostSeesPacMan was called for exactly the ghosts in `$08`/`$10` and for no others**: 2,416 ghost-frames in `$08`/`$10`, 2,416 calls; 0 calls for any other of the 196,784 ghost-frames.
- **Patrol ghosts: the sighting equals the exact software model of the test in every frame** (66 sightings in 2,416 frames, 0 differences), so the control works: the aid really does put Pac-Man in sight.
- **Frightened patrol ghosts (`$88`: 1,068 ghost-frames, `$90`: 349) with Pac-Man in line of sight according to the model: 155 frames (141 and 14) - 0 calls, 0 sightings, the state stayed frightened.** All frightened states together (`$80` house, `$81`/`$82`/`$84`/`$88`/`$90`/`$A0`): 91,446 ghost-frames, the model says "would see" in 12,473, 0 calls, 0 sightings; eaten ghosts (`$42`/`$44`: 25,685 ghost-frames, 2,836 "would see"): 0 calls, 0 sightings.
- All other states (`$00 $01 $02 $04 $20`): 79,653 ghost-frames, 10,818 "would see", 0 calls, 0 sightings.
Limit: the line of sight was produced by test aids (Pac-Man moved in front of the ghost), not by a person; the sighting of the shipped test is the one in this document (it reads the offset tables, not the lists). In that first run frightened `$90` was thin (5 episodes, 349 ghost-frames, 14 "would see" frames in 2 runs, one ghost) - see the targeted session below.

### Targeted session for frightened patrol `$88` / `$90` (2026-11-11)
Why `$90` was rare: a ghost is in patrol `$10` only for a short stretch, and any time Pac-Man is in sight of a ghost in `$08`/`$10` the (working) sight test turns it to chase before a pellet can catch it. `tools/altirra_sight_states_90.cmd` therefore (test aids, emulated machine only) plays **one long board at level 0** (about 148,000 frames, no level change) so that the ghosts go through chase, corner and patrol again and again; it eats a power pellet **whenever a ghost is in `$10` and no frightened period runs**; and it puts Pac-Man in front of a ghost **only while that ghost is frightened patrol** (`$88`/`$90`). Result (`analysis/evidence-sight-states-90-summary.txt`; 141,663 frames of the loop, 566,652 ghost-frames):
- **Frightened `$90`: 114 separate episodes, 9,809 ghost-frames, all four ghosts (27 / 32 / 34 / 21 episodes); the model says Pac-Man was in line of sight in 7,274 of those frames (96 separate runs). 0 calls of `GhostSeesPacMan`, 0 sightings, the state stayed `$90` until the frightened time ended.**
- **Frightened `$88`: 200 episodes, 23,287 ghost-frames, all four ghosts; "would see" in 8,410 frames (161 runs). 0 calls, 0 sightings.**
- Control in the same log: patrol `$08` ghosts: 65,916 ghost-frames, 65,916 calls, 33 sightings, equal to the model in every frame (0 violations).
- Because the aid eats the pellet in the first frame a ghost is in `$10`, this run has no unfrightened `$10` frames; the positive control for `$10` itself (178 ghost-frames, all called) is in the first run above.

