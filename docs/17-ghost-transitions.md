# 17 – What Switches a Ghost Between Start Route, Patrol and Chase

Written 2026-11-10 (step C11). The state machine itself (`GhostBehaviour`, the handlers, the 16 routes) is in `13-ghost-patrols.md`; the sight test is in `15-small-tables.md`; the ghost pictures are in `16-ghost-frames.md`.
This page answers one question: **which events change `GhostState` (`$CE + ghost`), and when.**

## Why the answer is complete
1. **Static:** every instruction in the ROM's code that can write `$CE–$D1` was searched for (`tests/test_ghost_transitions.py`): there are **exactly 13** (12 `STA GhostState,X` and one `INC GhostState` for ghost 0). The only other writer is the board-start clear loop in `InitBoard` (`$ADAF`, `STA zp_80,X` over `$80–$FF`), which sets every state to 0.
2. **Live:** `tools/altirra_transitions.cmd` logs every execution of those 13 stores (old value, and the game's variables at that moment); `tools/analyze_transitions_log.py` checks them. Run: 131,090 frames of game play (about 36 minutes of game time at 60 Hz), 6 board starts, **23,322 state writes, all 13 sites reached, 0 writes that break the rule the code implies**
   (`analysis/evidence-ghost-transitions-summary.txt`). **No hidden writer:** for each ghost, every write found exactly the value that the previous write left, except 20 cases (5 later board starts × 4 ghosts) where the state was 0, each with an `InitBoard` call (6 logged) in between.
   (The new value cannot be read at the store in Altirra's debugger, so it is derived from the code for each site and then confirmed by the *next* write of the same ghost.)
3. (A test-aid side effect on later frames of this run, zeroed `ReverseDir` entries, is described in `18-frightened-eaten-house.md`; it does not affect the rule checks above.) Test aids (emulated machine only; the sight test and all timers are the game's own): the game is started from its start code; ghosts do not kill Pac-Man; Pac-Man is moved around the lattice, onto power pellets and onto ghosts; and the dots-eaten counter is set to `$B1`, `$E1`, `$F1` in turn so that the late-board code runs. Those aids create *situations*; they do not change what the game does in them.

## The states
| State | Name | Behaviour (`GhostBehaviour`, `$B7F5`) |
|---|---|---|
| `$00` | in the house, waiting | `GhostTimer` counts down (release timers, `14-levels.md`) |
| `$01` | start route | follows `StartRoutes[ghost]` out of the house |
| `$02` | chase | target = Pac-Man's position; runs while `ChaseTimer` is non-zero |
| `$04` | leaving the house | back inside the house after being eaten; walks to the door row |
| `$08` | patrol travel | walks to the start junction of the chosen patrol route |
| `$10` | patrol | follows the route, one direction per junction, forever |
| `$20` | to corner | walks to its own corner (`CornerPositions`) |
| `$42` / `$44` | eaten / eaten at the door | eyes returning to the house / entering it |
| bit 7 (`$80`) | frightened (added to any of the above) | handled as chase with the inverted steering (flee); the underlying state is kept |

## Every event that writes the state
Counts are from the 131,090-frame run; the "store" column is the address of the instruction.

| Event | Store | Change | Condition (checked on every write) | Count |
|---|---|---|---|---|
| Board starts | `$A800` | ghost 0: `$00 → $01` | – (ghosts 1–3 stay `$00`; `InitBoard` cleared all) | 6 |
| Release: a ghost reaches the door row | `$B756` | `$00 → $01` (start route) | ghost `y = $64` (the door), after its `GhostTimer` ran out | 18 |
| **Start route ends, ghost 0** | `$B8ED` | `$01 → $02` (chase), `ChaseTimer := $50` | route nibble `$F` reached, ghost 0 only | 6 |
| **Start route ends, ghosts 1–3** | `$B853` (`GhostSelectPatrol`) | `$01 → $08` (patrol travel); route := `RANDOM AND $0F`; `GhostTimer := $96` | route nibble `$F` reached | 17 |
| **Arrived at the route's start junction** | `$B895` | `$08 → $10` (patrol) | steering has nothing left to do (target reached) | 57 |
| **Patrol time up** | `$B8C7` | `$10 → $20` (corner) | `GhostTimer = 0` | 7 |
| **Patrol travel time up** | `$B8C7` | `$08 → $20` | `GhostTimer = 0` (the 20 s budget includes the walk) | 5 |
| **Chase time up** | `$B8C7` | `$02 → $20` | `ChaseTimer = 0` | 16 |
| (corner state re-entered every step) | `$B8C7` | `$20 → $20` | – | 22,313 |
| **Corner reached** | `$B853` | `$20 → $08` (new random patrol) | steering has nothing left to do | 92 |
| **Sighting** | `$BAB9` | `$08` or `$10 → $02` (chase), then `ChaseTimer := $A0` | `GhostSeesPacMan` (`15-small-tables.md`); ghost 2 only if `RTCLOK2` bit 7 is clear; **only ghosts in exactly `$08`/`$10` are tested, never frightened or eaten ones** (verified, `15-small-tables.md`) | 31 + 17 |
| **Late board (dots eaten)** | `$B626` | `$08`, `$10` or `$20 → $02` | dots eaten ≥ `$E0` (ghosts 0–2) or ≥ `$F0` (ghost 3); afterwards `ChaseTimer := $FF` so the chase never times out | 1 + 5 + 38 |
| Power pellet | `$B40A` | any not-eaten state `→` state OR `$80` | ghost not eaten (bit 6 clear) | 315 |
| Frightened time over | `$AFA0` | `$8x → $20` (corner); `$80 → $00` | `FrightenPhase` reached `FrightenEndPhase`; only frightened ghosts | 155 |
| Ghost eaten | `$A888` | `$8x → $42` | Pac-Man touches a frightened ghost | 58 |
| Eaten ghost at the door square | `$B6D0` | `$42 → $44` | ghost at (`$7C`, `$64`) | 55 |
| Eaten ghost inside the house | `$B764` | `$44 → $04` (state AND `$0F`; colour restored) | `Sub_B781`: the ghost has reached its row inside the house (`y = $74`, and its own `x` for ghosts 2 and 3) | 55 |
| Ghost leaves again | `$B756` | `$04 → $02` (chase) | door row `y = $64` | 55 |

### The answer to the question
- **Start route → patrol:** ghosts 1–3, when the route's last nibble (`$F`) is read: `GhostSelectPatrol` (`$08`). **Start route → chase:** ghost 0 only, same moment (`ChaseTimer := $50`, about 10 s).
- **Patrol (`$08`/`$10`) → chase:** two events only: **sighting** (`GhostSeesPacMan`, `ChaseTimer := $A0`, about 21 s) and the **dots-eaten threshold** (late board, permanent chase).
- **Chase → corner → patrol:** chase ends when `ChaseTimer` reaches 0 (the game decrements it every 8th jiffy); the ghost goes to its corner (`$20`) and on arrival picks a new random patrol (`$08`). The same corner state ends every patrol (`GhostTimer`, 20 s from the selection).
- **Nothing else** moves a ghost between those states: the other writes are the release, the power pellet, its end, being eaten, and the return to the house.

### Frightened and eaten ghosts
- A power pellet adds bit 7 to every ghost that is not already eaten (including ghosts that are still on their start route, `$81` – seen once – or in a frightened state already: the bit is simply set again, 70 + 10 + 13 + 5 times). Frightened ghosts run the *chase* handler with inverted steering; they never run the patrol or timer logic, so **no patrol, chase or corner transition happens while a ghost is frightened**.
- When the frightened time is over every frightened ghost goes to its corner (`$20`) – whatever it was doing – except a frightened ghost still inside the house (`$80`), which goes back to `$00`. (`$80 → $00` was not reached in this run: the code is `$AF9A`, tested bytes only.)
- Eaten: `$42` (eyes) walk to the door square, `$44` there, `$04` once inside (the colour register is restored), then through the door row to `$02` (chase). The eyes picture is drawn while bit 6 is set (`16-ghost-frames.md`).

## Details worth knowing
- **`ChaseTimer` is one byte for all four ghosts.** It is set to `$50` (ghost 0, start), `$A0` (a sighting), the house-exit code writes `$82` into it for a frightened ghost (`$B74C`; code only, not seen), and `Sub_B616` leaves `$FF` in it. A chase therefore lasts until the *shared* timer runs out, whichever ghost started it.
- The dots-eaten counter is the 16-bit pair `zp $34/$36` (per player, incremented at `$B386` for every dot or pellet). It also selects the siren pitch step (`zp_9C` = 2, 3 at `$B0`, 4 at `$E0`, 5 at `$F0`; code only). The thresholds `$E0`/`$F0` were reached in the run only through the aid that sets the counter, but the code that acts on them ran as the game wrote it (44 writes, all matching).
- A returned eaten ghost resumes as **chase** (`$02`); because the shared `ChaseTimer` is often 0 by then, it usually goes straight to its corner on the next step (`$02 → $20`).
- Ghosts are never in two of the states at once: bit 7 is the only overlay.

## Not covered
- ~~`$80 → $00` and `$81 → …`~~ verified live: `$80 → $00` in 9 of 9 natural ends (`18`, "Frightened ghosts inside the house"); **`$81` (OV-35, 2026-11-14)**: 43 pellets on a start-route ghost, 13,656 frames as `$81`, `StartRouteStep` never moved (a frightened ghost runs `GhostChase` instead of the start route: `GhostBehaviour` `$B7F5` sends every frightened state with bit 2 clear there), no route-end store happened to it, and it ended `$81 → $20` (corner) in 41 of 41 frightened-time ends or `$81 → $42` in 2 of 2 eatings (`tools/analyze_frightened_cases.py`, `analysis/evidence-frightened-cases-summary.txt`). The steering inversion (`SteerToTarget`) is verified live in `18` (9,581 decisions); the pellet reversal in `13-ghost-patrols.md`.
- **Measured (OV-30, `tools/analyze_timer_budgets.py`, `analysis/evidence-timer-budgets-summary.txt`):** the timers fall one step per 8 frames (14,995 of 16,998 consecutive log-frame pairs match exactly; the rest are explained below); `ChaseTimer` is `$A0` (1,280 frames = 21.36 s NTSC / 25.67 s PAL) after a sighting in 28 of 28 cases and `$50` (640 frames = 10.68 s) after the start route of ghost 0 in 5 of 5; all 16 chase time-ups have `ChaseTimer` = 0; the patrol budget (`$96`) ends 1,194-1,201 frames after its selection (12 cases). **A ghost eaten stops the decrement for about 32 frames** (29 cases, 29-36 frames missing, mean 32.1): the timers run only when the game routine runs, so an eating lengthens a chase by that time. The PAL lengths are computed from the frame rate (no PAL ghost log was made).
- ~~Names~~ done (OV-36, 2026-11-14): `zp_34` / `zp_36` are now `DotsEatenLo` / `DotsEatenHi` (per player, index `CurrentPlayer`), `zp_9C` is `SirenStep`, and the role of the one shared `ChaseTimer` is in `tools/labels.py` (the ROM rebuilds byte for byte).
