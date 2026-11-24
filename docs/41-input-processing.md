# 41 - Input processing (stage 63)

Tools: `tools/input_model.py` (the executable model of the joystick path and of the contact test, and their exhaustive comparison with the code on the concrete 6502), `tools/altirra_stick.cmd`, `tools/altirra_stick2.cmd`, `tools/run_input_audit.ps1` (the live sessions), `tools/analyze_input.py` (the analysis); tests: `tests/test_input.py`; evidence: `analysis/evidence-input-summary.txt`. The inventory of what the game reads is `33-input-output.md` (stage 57); this chapter is what it **does** with each input.

## 1. The result

- **Every input of the game has one consumer and one effect** (section 2): the stick steers Pac-Man (`MovePacMan`), the triggers and the console keys act in the key loop (`38`, `40`), the keyboard pauses, the two missile-to-player collision registers decide a contact, `RANDOM` is read at three places of the ghost AI. Nothing else is read.
- **The joystick path is a small state machine with four bytes of state** (section 3): the wanted direction `zp_AC` (it stays when the stick is let go: the game remembers the last direction asked for and takes it at the first cell where it is open), Pac-Man's direction `$93`, the open directions at his cell `zp_2A`, and the corner flag `zp_A8` (set when a remembered turn between a horizontal and a vertical direction is taken: the next frame Pac-Man moves whatever his move delay says). A stick with **exactly two directions pressed is refused**; one direction is taken at once if it is open (this is how a reversal works), else remembered.
- **Checked exhaustively**: the model gives the code's result for **every** stick value x open set x direction x wanted direction x player (131,072 cases, 0 mismatches), and the contact test for every combination of the two collision registers, the ghosts' state classes and near / far in Y (1,048,576 cases, 0 mismatches); and **in the real game** for 53,207 passes of the joystick path (all sixteen stick values, both players) and 138,104 passes of the contact test (3,561 deaths, 55 ghosts eaten), 0 disagreements (section 7).

## 2. The inputs and what processes them

| Input | Read at | Processed by | Effect |
|---|---|---|---|
| `STICK0,x` (the OS shadow of the stick port, 0 = pressed; bit 0 up, 1 down, 2 left, 3 right; x = the player on turn: `STICK0` for player 1, `STICK1` for player 2) | `$B1A1` | `MovePacMan` (`$B179`), section 3 | Pac-Man's wanted and actual direction; `ATRACT` |
| `STRIG0`, `STRIG1` (0 = pressed) | `$A4FA`, `$A4FF` | the key loop (`38` section 3, `40`) | a new game (`$A537`), but only on a title screen or in the game-over countdown; ignored in play |
| `CONSOL` (bit 0 START, 1 SELECT, 2 OPTION; 0 = pressed) | `$A504`, `$A511`, `$A51C` | the key loop with its debounce | START: a new game at any time; in play or on the copyright screen any other key or combination goes to the title menu; on the title menu OPTION cycles StartLevel (0 1 2 4 6 8 10 12), SELECT toggles one / two players; any other combination is ignored (section 4) |
| `CH` = `$21` (the space bar) with `KEYDEL` = 0 | `$A4CC`, `$A4D1` | the key loop | the pause flag `$9B` toggles, in a game only (GameState 0) |
| `M1PL`, `M2PL` (`$D009`, `$D00A`: missile 1 / 2 with the players) | `$A857`, `$A85C` | the contact test of the frame (`$A84D-$A883`), section 5 | a ghost is eaten or Pac-Man dies |
| `M2PF` bit 1 (`$D002`) | `$A938` | the bonus-item test | Pac-Man touches the bonus item (`12`, `18`) |
| `RANDOM` (`$D20A`) | `$B859`, `$B9E1`, `$B9F4` | the ghost AI | the patrol route of a ghost (`$B859`), the choice between two equally good directions (`$B9E1`, `$B9F4`) (section 6) |
| `RTCLOK2` (the OS clock) | 15 places | every timer of the game | `33` |

## 3. The joystick path

`MovePacMan` first asks `JunctionLookup` (X = 4, Pac-Man) for the **open directions at his cell** (`zp_2A`: bit 0 up, 1 down, 2 left, 3 right; the values the table gives are 0, 3, 5, 6, 7, 9, A, B, C, D, E, F: the corridors are `$0C` horizontal and `$03` vertical, the junctions have their own sets), then:

```
$B183  if wanted & open != 0:                         the remembered direction is open now
           if wanted != direction and (wanted | direction) has a vertical AND a horizontal bit:
               corner := wanted | direction            ($B199: zp_A8, a non-zero value)
           direction := wanted                          ($B19B)
$B19F  s := STICK0,x xor $0F                            the pressed directions as bits (1 = pressed)
       if s != 0 and the number of ones in its low four bits != 2:
           ATRACT := s;  wanted := s                    ($B1BA, $B1BC)
           if s & open != 0:  direction := s            ($B1C2)
$B1C4  if direction & open == 0:  Pac-Man stands (the picture of his direction, no move)      -> $B2AA
       else the case of direction: 1 up ($B1E3), 2 down ($B211), 8 right ($B23F), 4 left ($B271); any other value: no move ($B2CE)
```

The two parts are in this order, so the **buffered turn is taken before the stick is read** in the same frame, and a direction pressed this frame is applied at once only when it is open now. In the cases the code gives (`input_model.steer` and `motion`):

| STICK0,x | pressed | what the game does |
|---|---|---|
| `$0` | up+down+left+right | accepted, but as a value that is none of the four directions (4 at once): wanted := $F, ATRACT := $F; if any of them is open Pac-Man direction becomes $F and he stands still (the dispatch finds no case) until a single direction is accepted |
| `$1` | down+left+right | accepted, but as a value that is none of the four directions (3 at once): wanted := $E, ATRACT := $E; if any of them is open Pac-Man direction becomes $E and he stands still (the dispatch finds no case) until a single direction is accepted |
| `$2` | up+left+right | accepted, but as a value that is none of the four directions (3 at once): wanted := $D, ATRACT := $D; if any of them is open Pac-Man direction becomes $D and he stands still (the dispatch finds no case) until a single direction is accepted |
| `$3` | left+right | **refused**: exactly two directions (a diagonal or two opposite ones): nothing changes |
| `$4` | up+down+right | accepted, but as a value that is none of the four directions (3 at once): wanted := $B, ATRACT := $B; if any of them is open Pac-Man direction becomes $B and he stands still (the dispatch finds no case) until a single direction is accepted |
| `$5` | down+right | **refused**: exactly two directions (a diagonal or two opposite ones): nothing changes |
| `$6` | up+right | **refused**: exactly two directions (a diagonal or two opposite ones): nothing changes |
| `$7` | right | accepted: wanted direction := right, ATRACT := 8; if right is open now Pac-Man turns at once (a reversal too), else he keeps going and takes it at the first cell where it is open |
| `$8` | up+down+left | accepted, but as a value that is none of the four directions (3 at once): wanted := $7, ATRACT := $7; if any of them is open Pac-Man direction becomes $7 and he stands still (the dispatch finds no case) until a single direction is accepted |
| `$9` | down+left | **refused**: exactly two directions (a diagonal or two opposite ones): nothing changes |
| `$A` | up+left | **refused**: exactly two directions (a diagonal or two opposite ones): nothing changes |
| `$B` | left | accepted: wanted direction := left, ATRACT := 4; if left is open now Pac-Man turns at once (a reversal too), else he keeps going and takes it at the first cell where it is open |
| `$C` | up+down | **refused**: exactly two directions (a diagonal or two opposite ones): nothing changes |
| `$D` | down | accepted: wanted direction := down, ATRACT := 2; if down is open now Pac-Man turns at once (a reversal too), else he keeps going and takes it at the first cell where it is open |
| `$E` | up | accepted: wanted direction := up, ATRACT := 1; if up is open now Pac-Man turns at once (a reversal too), else he keeps going and takes it at the first cell where it is open |
| `$F` | none | nothing pressed: the path does nothing (the wanted direction stays, ATRACT is not touched) |

Consequences, each checked by the model and by the real game:

- **The wanted direction is a buffer.** Press up in a corridor where up is closed: nothing changes but `zp_AC`; at the first cell where up is open (`wanted & open != 0`) Pac-Man turns without any further press, though the stick may be back in the middle. The buffer is also what a person does when he "pre-turns" a corner.
- **A reversal is immediate**: the opposite direction is open in any corridor, so pressing it sets `direction` at once.
- **The corner flag is only set by the buffered path** (the first part of the code), not by an immediate turn: pre-turning gives Pac-Man the free step, turning at the last moment does not. The flag is consumed in the next frame (`$A9A4`): `zp_A7` := 0, so `MovePacMan` moves although the move-delay counter says to skip (the classic cornering gain); `$A9B9` clears it. The eaten-ghost pause also sets it (`inc zp_A8` at `$B0B7`, after an extra `MovePacMan` call).
- **A direction that is closed at the cell stops Pac-Man** (`direction & open == 0`): he stands, his picture is that of his direction, `$B2AA`; nothing moves the entity. The same code is the wall.
- **Two directions at once are refused whatever they are** (a diagonal `$A`, `$9`, `$6`, `$5`, two opposite ones `$C`, `$3`): a diagonal is what a person gives when he cuts a corner, and the game ignores it **and keeps the old wanted direction**.
- **Three or four directions are not refused** (the machine cannot produce them; the exhaustive check does): the three-bit value becomes `wanted` and `ATRACT`, and if any of its bits is open it also becomes Pac-Man's direction, which none of the four cases matches: he stands still until a single direction is accepted.
- **`ATRACT`**: an accepted stick value (1 to 15) is written into the OS attract-mode timer, which resets it (the screen does not darken or change colour while somebody plays; the key loop writes 3 or 4 when it changes screen, `33`).
- **Two players**: x = `CurrentPlayer`: player 2's turn reads `STICK1` (`$0279`, the second stick port). The state (`zp_AC`, `$93`, the corner flag) is the same bytes for both players and is cleared by `InitBoard` at each turn, so nothing is carried over.

## 4. Triggers, console keys and the keyboard

All of this is in the key loop, whose every branch was run (`40`); the table gives each input value its effect. `zp_19` is GameState (0 = a game, 1 and 2 = the copyright screen, 3 = the title menu, 4 = the title after a game).

| Input | Condition | Effect |
|---|---|---|
| STRIG0 or STRIG1 = 0 | GameState not 0, or the game-over countdown still running | `CH` := `$FF`; a new game: CountdownActive := 0, GameState := 0, IntroRequest := 1, the restart (`$A537`) |
| STRIG0 or STRIG1 = 0 | in play | ignored |
| CONSOL = 6 (START) | any time (after the debounce and the release) | a new game, as above |
| CONSOL = 3 (OPTION) | GameState >= 3 | StartLevel: 0 to 1 to 2 to 4 to 6 to 8 to 10 to 12 to 0; GameState := 3 |
| CONSOL = 5 (SELECT) | GameState >= 3 | TwoPlayers toggles; GameState := 3 |
| CONSOL = any value but 6 and 7 (a key or a combination) | GameState 0 (a game) or 1 or 2 (the copyright screen) | GameState := 3, ATRACT := 3: the title menu (`$A52B`: no further test) |
| CONSOL = 0, 1, 2, 4 (two or three keys) | GameState >= 3 | ignored (back to the top of the loop) |
| `CH` = `$21` (space) and `KEYDEL` = 0 | GameState 0 | `Paused` toggles; `CH` := `$FF` |
| `CH` = anything else | | ignored (`CH` is cleared to `$FF` only by the pause key and by the trigger path) |

A console key is acted on when it is **released**: the loop reads CONSOL, waits for the handler to count the debounce byte `$45` down (one frame), reads again (a changed value starts again), and waits until the value is gone (`$A51C`).

## 5. The collision registers: the contact test

The frame code `$A84D-$A883` goes through the four ghosts in the order 0 to 3 (the mask `1 << g`) and the **first** ghost that qualifies decides (`input_model.contact`):

1. the ghost's state has bit 6 clear (an eaten ghost, the eyes, is skipped);
2. its bit is set in **both** `M1PL` and `M2PL` (the two missiles that make Pac-Man's body overlap the ghost's player in the hardware);
3. the vertical distance `|PacY - EntityY| < 5`.

Then the ghost's state decides: bit 7 set (frightened): the ghost is eaten (`GhostEaten`, `$A886`: state := `$42`, the score and the pop-up, `18`); bit 7 clear: Pac-Man dies (`$A923`, `20`). No ghost qualifies: the frame goes on to the bonus-item test. `HITCLR` clears the registers after each board set-up and each frame's test.

## 6. Random numbers

`RANDOM` is read at three places and nowhere else (`33`): `GhostSelectPatrol` (`$B859`): `and #$0F` gives the patrol route of a ghost, 0 to 15 (`13`); `SteerToTarget` (`$B9E1`, `$B9F4`, `17`): the routine works out the vertical and the horizontal direction towards the target (towards a frightened ghost's target they are turned round); when **both** are open at the ghost's cell, bit 7 of `RANDOM` picks one of them (`$B9E1`); when **neither** is open, `RANDOM and open` picks a random open direction (the lowest set bit of it; of the open set itself when the AND is zero, `$B9F4`). The game never seeds the generator and never reads it for anything else, so the ghosts' choices are the only random part of the game (the maze, the levels, the bonus items and the scores are fixed).

## 7. Verification

- **The model against the code, exhaustively** (`tools/input_model.py --exhaustive`, the concrete 6502 of `tools/cpu6502.py`): the joystick path from `$B182`: every stick value 0-15, every open set 0-15, every direction 0-15, every wanted direction 0-15, both players: **131,072 cases, 0 mismatches** (the new wanted direction, direction, `ATRACT`, the corner flag and the case of the dispatch); stick values 16-255 (the OS never gives them): 1,440 random cases, 0 mismatches. The contact test from `$A84D`: `M1PL` x `M2PL` (16 x 16) x the state class (bit 7, bit 6) of each of the four ghosts x near / far for each: **1,048,576 cases, 0 mismatches**.
- **The model against the real game** (Altirra 4.40, NTSC; `analysis/evidence-input-summary.txt`): `altirra_stick.cmd` and `altirra_stick2.cmd` poke a random stick value (0-15, all sixteen, 3,200 to 3,400 times each) before each read: **53,207 passes, 0 disagree** (49,536 for player 1, 3,671 for player 2, whose turn reads `STICK1`); the open sets seen are 3, 5, 6, 7, 9, A, B, C, D, E, F (0 is a cell Pac-Man cannot be in); 19,926 stick values with two directions refused, 16,729 with three or four, 20,120 immediate turns (902 reversals), 97 buffered turns, 87 corner flags. **A real press**: `altirra_realstick.cmd` writes nothing to `STICK0`: the arrow keys are posted to Altirra's window (which maps them to joystick 1), the OS reads the PIA port (`$D300`) in its vertical blank and fills the shadow, and the game reads it: 19,947 passes with all four directions pressed (up 37, left 31, right 30, down 29 passes), **the value the game read equals the PIA port masked to four bits in every pass** (right: port `$F7`, shadow `$07`; so the high bits never reach the game), 0 disagree with the model. `run_input_audit.ps1` logs the registers, the ghost states and the positions at `$A84D` and the outcome in six sessions: **138,104 passes, 0 disagree** (3,561 deaths, 55 ghosts eaten, 32,781 passes with a ghost's bit in both registers).
- The key loop's inputs: `40` (every branch).

## 8. For the port

The port needs, per player, **four booleans** (up, down, left, right) from whatever device it has, in the order of the bits above, and the three console keys, the trigger and one pause key; everything else is the machine's. To be exact: take the four booleans as `STICK0,x` bits (0 = pressed), run the model of section 3 once a frame **after** the open directions of Pac-Man's cell have been computed, keep `zp_AC` between frames, **refuse exactly two directions pressed**, and let the buffered turn precede the stick. A port may restrict the device so that three and four directions cannot occur (a stick cannot give them); it must not restrict the other rules, which a player feels: the buffer, the immediate reversal, the free step after a buffered corner and the refusal of diagonals.

## 9. Limits

- The key-loop inputs rely on `40` (values written into the loop's reads except the real space bar of `realkey`); in the exhaustive and the random sessions the stick values are poked into the OS shadow before `MovePacMan` reads them, and the real arrow-key session shows that the OS fills the shadow from the PIA port as the model assumes (the OS copies the port and masks it to four bits); the stick is the emulator's keyboard-mapped joystick, not a real Atari stick (the same limit as the sound: no real machine, OV-42b).
- The contact test is checked on the code between `$A84D` and the three exits; what follows (the pop-up, the death sequence) is in `18` and `20`.
- `RANDOM` is described from the three sites, not modelled (it is the ghost AI of stage 66).
