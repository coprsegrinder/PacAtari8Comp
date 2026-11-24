# 40 - The key loop: every branch run, and what a pass costs (OV-65)

Tools: `tools/make_keyloop_cmd.py` (the counters), `tools/run_keyloop_audit.ps1` (the sessions), `tools/analyze_keyloop.py` (the analysis), `tools/altirra_keyloop.cmd` (a harness for the rare outcomes); tests: `tests/test_keyloop.py`; evidence: `analysis/evidence-keyloop-summary.txt`. The code is the key loop of `38-main-loop.md` section 3 (`$A4BA-$A572`, the main program).

## 1. The result

- **All 54 outcomes of the 27 conditional branches of the key loop were observed or are impossible by construction**: 47 were seen in the real game, 7 cannot happen (section 3), **0 are missing**. The pseudo-code of `38` section 3 was written from the code; this is the record that every path of it ran.
- **A pass of the loop is short and measured**: an idle pass costs **111 instruction cycles on a title screen and 114 in a game** (static, exact index for the colour table); in the sessions the main program gets **160-161 passes a frame on a title screen, up to 178 on the copyright wait, 137-139 in a game's countdown, 114-123 in play (median)** - the product with the cost stays inside the measured budgets of `39` (16,100 cycles on the game screen, 19,750 on the title screens), the rest being the handler's own frame.

## 2. Method

A breakpoint at each conditional branch (27 of them, `$A4BA-$A572`) increments one of two 16-bit counters in unused RAM (`$4300 +4k`: taken, not taken) from the processor flags the branch reads (`@p`: the flags at the branch decide it); the counters saturate at 65,535 so that "it happened" survives. A tracepoint at the handler's entry writes every counter to the log once a frame (`KC` lines); the last complete line of a log is its total. The debugger's `>>` is not a shift (a first version read `$30>>7` as 1), so the flags are taken with masks and divisions (`tests/test_keyloop.py`). A pass counter at `$A4BA`, cleared just after the handler's entry, gives the passes of the loop in each frame. Nothing is written to the game's memory or registers. The sessions are those of the earlier stages with the counters added: the input exerciser (`inputs`, `inputs1`: SELECT, OPTION, two keys, the trigger and the second button), `pregame`, `copyright_key`, `pause`, `rare`, `fullgame`, `gameover`, `realkey` (the space bar pressed from outside the machine, so that the OS sets `KEYDEL`, which `$A4CC` tests), and one harness written for this (`altirra_keyloop.cmd`: the option key ten times so that StartLevel runs through 0 1 2 4 6 8 10 12 0 1, a console value that changes during the debounce, STRIG1).

With the counters on every branch the emulator runs 30 to 100 times slower while the loop spins (a breakpoint hit costs about 0.8 ms and the loop makes about 140 passes a frame), so the points that only a long session reaches were counted separately with cold points: the game-over countdown is seen by how often `$A4ED` ran (the countdown is on: `$A4EB` not taken, `$A4EF` reached) and `$A4F1` (the countdown timer is 0: `$A4EF` not taken, then `$A4F3` always taken): `--blocks a4ed,a4f1` (`KB` lines), 59,545 frames of the `fullgame` session, the countdown ended twice.

## 3. The outcomes that cannot happen

Seven branches have one outcome that is impossible, because the flag they test is fixed by the instruction before (each is checked in `tests/test_keyloop.py`): `$A4DE beq` after `lda #$00` (the pause flag cleared: always taken), `$A4F3 bne` after `lda #$04`, `$A54A bne` after `lda #$01`, `$A571 beq` after `lda #$00 / sta`, `$A535 bne` after `cmp #$05 / beq` fell through (not equal: always taken, any other console combination goes back to the top), `$A561 bne` after `inc StartLevel` from 0 or 1 (the result is 1 or 2), `$A56B bne` after two `inc StartLevel` from an even 2 to 10 (4 to 12). For each the other outcome (always taken) was seen.

## 4. What was seen, by outcome

| Branch | What it tests | Seen both ways in |
|---|---|---|
| `$A4C6` | the colour loop (4 passes) | every log |
| `$A4CA` | GameState 0 (a game) or a title screen | the title logs and the games |
| `$A4CF` | `$02F1` (KEYDEL: the OS holds the keyboard for 3 frames after a key) | `realkey` (taken, 890 times) and everything else (not taken) |
| `$A4D6`, `$A4DA` | the space bar (`CH` = `$21`), pause or resume | `inputs`, `inputs1`, `pause`, `rare` (`CH` written), `realkey` (really pressed) |
| `$A4EB`, `$A4EF`, `$A4F3` | the game-over countdown on / its timer / its end | `fullgame` (the countdown ran 65,533 or more passes and ended twice) |
| `$A4FD`, `$A502` | the trigger STRIG0 / STRIG1 | `inputs` (STRIG0 pressed), `inputs1` (STRIG1 pressed), every other log (not pressed) |
| `$A509`, `$A516`, `$A51A`, `$A51F` | the console: nothing pressed, the debounce wait, the value changed in the debounce, the wait for release | `inputs`, `inputs1`, `copyright_key`, `pregame`, `rare`, `fullgame`; the changed value (`$A51A` taken): `keyloop`, 9 times |
| `$A525`, `$A52B`, `$A52F`, `$A533` | START, the copyright screen (any key leaves it), OPTION, SELECT | START: `fullgame`, `rare` (taken), `inputs`, `pregame` (not); copyright (`$A52B` taken): `copyright_key`; OPTION and SELECT: `inputs`, `inputs1`, `pregame` |
| `$A546` | SELECT toggles the number of players, both ways | `inputs`, `inputs1` (taken), `pregame` (not taken) |
| `$A55D`, `$A565` | OPTION: StartLevel below 2, at `$0C` | `keyloop` (ten presses) |

## 5. Timing

The cost of an idle pass uses the cycle table of `39` with the real colour index: 111 cycles with GameState not 0 (the colour loop 77, the tests of GameState, CH, the trigger and the console 34), 114 in a game (it reads `$02F1` and CH on the way). The sessions give the passes a frame: 160-161 on the title screen, up to 178 on the copyright wait (the handler's frame there is a few hundred cycles), 137-139 in the game-over countdown, 114-123 in play (the handler's frame is long). The consistency check: **passes x cost stays within the measured budget of `39`** (to its resolution: the budget is counted in 25-cycle iterations, so 19,750 means 19,750 to 19,774) - 161 x 111 = 17,871 of 19,750 on the title screen (the title menu's handler frame takes about 1,900), 178 x 111 = 19,758 of 19,750 on the copyright wait (the most in one frame, 8 cycles over: a pass is not always 111 cycles, a frame's count is rounded by where the handler enters), 139 x 114 = 15,846 of 16,100 in the game-over countdown.

The loop itself has no bound to keep: it never returns and does no game logic; the only waits are the debounce (`$A511`, until the handler counts `$45` down: one frame) and the wait for release (`$A51C`, as long as the key is held).

## 6. Limits

- Altirra 4.40, NTSC; the harnesses write the console and trigger values into the key loop's reads (the game's own code does the rest) except `realkey`, which presses the space bar from outside.
- The pass counts come from sessions with the counters on, in which the emulator is slow; they are per frame, so the speed does not matter.
- The 7 impossible outcomes are shown by the code before each branch (tests), not by a run.
