# 19 – Two Players and Player 2's Counter

Written 2026-11-10 (step C11). Covers the player-2 level counter (`$31`) and everything else the game keeps per player, how the turn passes from one player to the other, and what happens when a player runs out of lives.
Evidence: the code (`tests/test_two_players.py`, 6 tests) and **a real two-player game run in Altirra** (`analysis/evidence-two-players-summary.txt`, `analysis/evidence-two-players-lives-summary.txt`; harness `tools/altirra_player2.cmd`, `tools/altirra_player2_lives.cmd`; analyzer `tools/analyze_player2_log.py`).

## The one/two-player flag
`zp_1A` (`$1A`) is **0 for one player and 1 for two**. On the title screen SELECT toggles it (`$A544`: `LDA zp_1A / BNE / LDA #1 ... LDA #0 / STA zp_1A`) and the menu shows `zp_1A + 1` as the digit in "n PLAYER GAME" (`$A719`). In the game it is read in the turn-switch code (`$AA9D`): with 0 the same player always continues.

## Everything the game keeps per player
All of these are indexed with `CurrentPlayer` (`$2B`: 0 = player 1, 1 = player 2). **Static check (`test_every_indexed_access_uses_current_player`): all 33 indexed accesses to these variables take their index from `CurrentPlayer`** (`LDX/LDY $2B` just before; two accesses reached by a branch checked by hand), with one deliberate exception: `Sub_AE1E` at new-game start, which initialises player 2 by being called with X = 1.

| Variable | Player 1 / player 2 | Meaning |
|---|---|---|
| lives | `$2C` / `$2D` | lives *left*: each turn start decrements it (`$AD13`), so a start value of 3 gives three turns; the icons show it |
| extra-life flag | `$2E` / `$2F` | set once when the player's score first reaches 10,000 (first non-zero digit at `$202B` / `$2048`, tested in `AddToScore`, `$B472–$B48B`); the same code adds a life |
| **Level** | **`$30` / `$31`** | zero-based board counter (`14-levels.md`); **player 2's counter is `$31`** |
| power-pellet flags | `$32` / `$33` | bits for the four power pellets still on the board (`$0F` at the start of a board) |
| dots eaten | `$34`+`$36` / `$35`+`$37` | 16-bit count, board ends at `$0104`; also drives the siren and the late-board chase (`17-ghost-transitions.md`) |
| bonus-item counter | `$43` / `$44` | how many bonus items have been shown on this board (`$B64F–$B660`) |
| score | digits ending at `$202F` / `$204C` | `AddToScore` picks the base with `CurrentPlayer` (`$B428–$B432`) |
| maze (dots left) | `$1000–$13FF` / `$1400–$17FF` | each player's maze is saved in its own copy; the playing player's is at `$0C00–$0FFF` |

**Player 2's counter `$31`.** At the start of a game both counters get the start level (`$ADF9`/`$ADFB`: `Level := zp_31 := StartLevel`, lives `$2C := $2D := 3`) and `Sub_AE1E` is called with X = 1 for player 2's flags and counters. A board is finished by `AdvanceLevel` (`$AC75`): `INC lives,X ; INC Level,X` with X = CurrentPlayer, so **only the player who cleared the board moves up a level**. The ten places that read `Level` (`14-levels.md`: speed, frightened time, bonus item, indicator colour, release timers ...) all load X or Y from `CurrentPlayer` first, so they see the playing player's level. It is 8-bit (wraps at 256) like player 1's.

## The turn
After a death (`$AA9D`), if `zp_1A` is non-zero: a player's turn ends and the other player's starts **only if the other player has lives left**. If the dying player still has lives, their maze is first saved (`Copy0C00To1000` / `Copy0C00To1400`); the other player's maze is loaded into `$0C00` (`zp_23` = 1: from `$1000`, `CurrentPlayer := 0`; `zp_23` = 2: from `$1400`, `CurrentPlayer := 1`) after a 48-frame pause (`zp_25 := $30`). If the other player has no lives, the same player simply continues (`$AAE0`); if the player playing has none either, the game ends (`$AAEF`).

## Live verification
**Run 1 – both players playing** (`tools/altirra_player2.cmd`; 106,267 log lines, about 122,000 frames of game play). Test aids (emulated machine only; the game's own code does everything else): the game is started with `zp_1A = 1`; right after the start levels are set the counters are poked to **player 1 = 2 and player 2 = 7** so that they differ; every 2,048 frames the playing player's level-complete flag is set, both life counters are refilled to 3 (so the game never ends), the dot counter is set to make the bonus item appear, and Pac-Man is moved onto the bonus item and a power pellet; Pac-Man is *not* protected, so the ghosts end each turn themselves. In one cycle the playing player's 10,000s score digit is set to 1.
- **114 turn switches** (57 to each player, alternating), all with `zp_1A = 1` and the other player holding lives. **In all 114 turns the player who was waiting kept every variable unchanged**: lives, level, power-pellet flags, dots eaten, extra-life flag, bonus counter and all six score digits (compared at the start and the end of each turn).
- **24 level advances** (2 by player 1, 22 by player 2): each changed the playing player's level by exactly +1 and the other player's by 0. Player 2's counter ran from 7 to **29** (wrapping/clamping rules as in `14-levels.md`).
- **105,124 table reads** (frightened time, frightened end phase, move delays, bonus glyph and score, level indicator, item colour, release timers ...) were logged with the level of the *playing* player; **every one equals the value the ROM tables give for that player's level** (0 mismatches; 55,831 reads for player 1 on levels 0, 2, 3, 4; 49,293 for player 2 on levels 7–29), and the logged level always equalled that player's own counter, never the other's. 24 board starts checked for release timers (all within the table options) and the release model `release(k) = release(1) + 4 x (timer_k - timer_1) + 48` held in 48 of 48 releases.
- Scores: 44 additions went into player 1's digits and 234 into player 2's, each with the playing player's base (`$2F` / `$4C`). **Extra life: awarded once, to player 2 only** (its flag `$2F` was set, player 1's `$2E` stayed 0); lives +1 for that player alone.
- 139 turn starts, 139 life decrements, 0 violations of any check.

**Run 2 – players running out of lives** (`tools/altirra_player2_lives.cmd`; player 1 starts with 1 life, player 2 with 2). Sequence seen: player 1 plays its only life; when Pac-Man dies with 0 left the end-of-turn code runs (`$AAEF`), the turn passes to player 2 after the 48-frame pause **without saving player 1's maze**, player 2 plays its 2 lives one after the other (`TURN_CONTINUES`: no switch while the other player has none), and when player 2 dies with 0 left the game ends (`$AAEF` again) and the state never changes again.

## Not covered
- Player 1's extra life was not provoked (the same code with index 0; `$2E` stayed 0); the extra life is tested only for the first non-zero digit at `$202B`/`$2048`, not for later 10,000s.
- The **pre-game screens** with two players (the "2 PLAYER GAME" menu text, the "PLAYER ONE/TWO" labels drawn by `Sub_AD87`/`Sub_AD9F`) were not captured; the flag and the logic were exercised by setting `zp_1A` directly.
- The high-score handling at the end of a two-player game, and what happens after the final `$AAEF` (return to the title screen): not traced.
- The maze copies were not compared byte by byte (the static test pins the copy routines; the live check shows the per-player dot counters and flags surviving every switch).
