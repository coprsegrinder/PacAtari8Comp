# 13 – Ghost Behaviour and the Patrol Routes

Written 2026-11-10 (step C11, nibble-map follow-up). **The patrol routes are fully verified**: all 16 were selected, followed
step by step, and closed their loops in the running game. How the surrounding behaviour fits together is described below, with
the evidence level of each statement. Names are in `tools/labels.py`; tests are `tests/test_ghost_states.py` and
`tests/test_nibble_map.py`; the live numbers are in `analysis/evidence-patrol-summary.txt`.

## What a patrol is
Ghosts do not plan paths. Their movement is a small state machine (`GhostState`, zero page `$CE + ghost`; bit 7 = frightened).
At every **lattice point** (a junction listed in `JunctionExits`) a ghost either **steers** toward a target (`SteerToTarget`)
or reads the **next direction of a route** (`StartRoutes`, `PatrolRoutes`: one direction nibble per junction).
Each of the 16 patrol routes is a closed loop of 6 to 28 steps over the junction lattice; `PatrolStartPositions[route]` is the
junction where it starts and ends.

## State machine (`GhostBehaviour`, `$B7F5`)
| State | Handler | Meaning / target | Leaves when | Evidence |
|---|---|---|---|---|
| `$00` | (house) | waiting; `GhostTimer` counts down the release time | timer reaches 0 | code (`Sub_B7A5`), not traced |
| `$01` | `GhostStartRoute` | follow `StartRoutes[ghost]` from the house door | route ends with `$F`: ghosts 1–3 go to `$08`, ghost 0 chases (`ChaseTimer` = `$50`) | live: 864 route reads match; ghosts 0–2 passed exactly the predicted junctions; transitions 01→08 and 01→02 seen |
| `$08` | `GhostPatrolTravel` | steer to the start junction of the chosen route | target reached → `$10`; `GhostTimer` = 0 → `$20` | live (run 2): 8→10 231 times, 8→20 30 times |
| `$10` | `GhostPatrol` | read `PatrolRoutes` one direction per junction, wrap at the 0 terminator | `GhostTimer` = 0 → `$20`; sighting → `$02` | live: 75,452 route reads, 423 wraps, 10→20 230 times |
| `$20` | `GhostGoToCorner` | steer to `CornerPositions[ghost]` (lattice corners (0,9) (0,0) (9,9) (9,0)) | corner reached → `GhostSelectPatrol` | live: corner → 08 258 times |
| `$02` | `GhostChase` | target = Pac-Man's position (`TargetX/Y` = `PacX/PacY` at every step) | `ChaseTimer` = 0 → `$20` | live in run 1 (02→20 78 times); entered with `$50` (ghost 0) or on sighting (`$A0`) |
| `$40`–`$44` | `Sub_B69E` | eaten ghost returning to the house (`$42` set when eaten, `$44` at the door) | arrives | code and the eaten-ghost trace; not followed further |
| bit 7 set | `GhostBehaviour`, `SteerToTarget` | frightened: steering is inverted (flee) | pellet ends | code; the power-pellet reversal itself is verified (`ReverseDir`) |

**Selecting a patrol (`GhostSelectPatrol`, `$B851`):** state := 8; `PatrolStep` := 0; route := `RANDOM AND $0F`; the target is
`PatrolStartPositions[route]` (x, y); `GhostTimer` := `$96`. Live, on all 261 selections of run 2: the target equalled the table
entry for the chosen route and `GhostTimer` was `$96` every time.

`GhostTimer` and `ChaseTimer` are decremented every 8th jiffy (code at `$A9DD` and `$B5C7`), so `$96` = 150 × 8 = 1,200 frames =
**20 seconds at 60 Hz, including the walk to the start junction** (computed from the code, not measured against a wall clock).

**Sight (`GhostSeesPacMan`, `$BA19`):** a ghost on the same row or column as Pac-Man, facing him, with no blocking entry in the
`$FF`-terminated lists between them (`SightListsX` for rows, `SightListsY` for columns, see `15-small-tables.md`) switches to `$02` and sets
`ChaseTimer` := `$A0`. Live (run 1): 8→02 63 times and 10→02 17 times; with the aid that disables it (run 2) it never happened.
**Update:** the lists are decoded and verified in `15-small-tables.md`: because the shipped code reads the offset tables instead of the lists, the sight test is far more permissive than its data intends (zones only, independent of the maze walls), and ghost 2 reacts only when `RTCLOK2` bit 7 is clear.

## The 16 routes
Verified (static) as valid walks over `JunctionExits` that return to their start (`tests/test_nibble_map.py`), and (live) every route
was selected, read exactly as the table says, reached its full length, and **every wrap landed on the route's start junction**
(loops seen / loops closed, run 2): 0: 23/23, 1: 13/13, 2: 24/24, 3: 60/60, 4: 54/54, 5: 50/50, 6: 23/23, 7: 80/80, 8: 5/5,
9: 21/21, 10: 12/12, 11: 6/6, 12: 22/22, 13: 5/5, 14: 7/7, 15: 18/18. All 6,097 scripted steps were followed by the ghost
reaching the neighbouring junction in the scripted direction, with no exception (run 1: 2,029 of 2,029). U = up, D = down,
L = left, R = right; lattice rows and columns are indexes into `JunctionYList` / `JunctionXList`.

| Route | Start junction (lattice row,col) | Maze cell (row,col) | Steps | Directions |
|---|---|---|---|---|
| 0 | (7,6) | (16,26) | 10 | `DLDLULURRR` |
| 1 | (4,3) | (10,13) | 10 | `URRRDDLLLU` |
| 2 | (3,5) | (8,21) | 10 | `LLDDRRRUUL` |
| 3 | (3,3) | (8,13) | 10 | `RULULDDDRU` |
| 4 | (6,3) | (14,13) | 6 | `RDLLUR` |
| 5 | (4,2) | (10,9) | 6 | `RDDLUU` |
| 6 | (6,6) | (14,26) | 6 | `LDRRUL` |
| 7 | (4,7) | (10,30) | 6 | `LDDRUU` |
| 8 | (2,6) | (6,26) | 10 | `URDDDLULUR` |
| 9 | (8,2) | (18,9) | 12 | `URDRDLLLLURR` |
| 10 | (9,9) | (20,36) | 12 | `ULLULDLDRRRR` |
| 11 | (1,5) | (4,21) | 18 | `URRDLDLDLLDLUUURRR` |
| 12 | (7,2) | (16,9) | 24 | `ULLDRDLDRRRRULURULUULDDD` |
| 13 | (8,8) | (18,33) | 28 | `URULLDDRRDLLLLURULURUURDDDDR` |
| 14 | (1,5) | (4,21) | 18 | `RDLDRDDLLLUURULURR` |
| 15 | (1,2) | (4,9) | 28 | `DLLURRURRDRURRRRDLLLDLDLULUL` |

`tools/describe_patrol_routes.py` prints every junction of every route; with `--image` it draws all 16 loops over the maze (the
picture shows game graphics, so it is kept locally and not committed). In the picture routes 1, 2 and 14 loop around the ghost house, routes 5 and 7 around the two small blocks beside it, routes 4 and 6 are the two short bars on maze row 14, route 0 is in the lower right, routes 9, 10, 12 and 13 patrol the lower maze, and 3, 8, 11 and 15 the upper part.

## How the evidence was gathered, and the test aids
`tools/run_patrol_trace.ps1` starts Altirra with `tools/altirra_patrol.cmd`, presses Start itself and runs unattended; it uses a
private settings copy (`Altirra_fast.ini`, game speed 800 %), so your normal Altirra settings stay as they were.
`tools/analyze_patrol_log.py` checks the log against the tables. Only the *emulated* machine is changed, never the ROM:
- always: a ghost touching Pac-Man does not kill him (the PC skips from `$A923` to `$A936`), so the run needs no input;
- run 2 only (`-Complete`): the sighting switch to chase is skipped, and the patrol timer of routes 3, 12 and 15 is refilled once
  when their patrol begins, because those long routes timed out before completing a loop (run 1: routes 3, 12 and 15 never
  wrapped; run 2: all 16 did).
Route selection stayed the game's own `RANDOM`; writing the A register from a breakpoint has no effect in Altirra, so routes cannot
be forced. Run 1 covered about 30 minutes of game time (200 selections), run 2 about 37 (261 selections).

## Not covered
- Levels above 1: **covered in `14-levels.md`**: the ghost state machine, routes and timers contain no read of the level counter, so they are identical on every board (verified over levels 0–50 and beyond); only speed, frightened time, bonus items and the house release timers change.
- Every write to the state, including frightened and eaten ghosts and the house release, is now logged and checked: **`17-ghost-transitions.md`**. The frightened-mode steering, the eaten-ghost return and the house release are traced in **`18-frightened-eaten-house.md`**.
- (The sight lists are now decoded: `15-small-tables.md`.)
- The wall-clock length of the 20-second patrol budget.
