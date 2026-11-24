# 39 - Worst-case time of the vertical-blank handler (OV-64)

Tools: `tools/static_wcet.py` (the static bound), `tools/altirra_budget.cmd` + `tools/analyze_budget.py` (what the handler's thread really gets), `tools/dma_model.py` (a model of the display, kept as a cross-check), `tools/analyze_loopbounds.py` and `tools/analyze_clip.py` (hand-argued facts against the game), `tools/altirra_rare.cmd` (the rare paths), `tools/wcet_sets/` (an experiment that was stopped, section 5), `tools/check_bounds_concrete.py` and `tools/fuzz_concrete.py` (the bounds against the real handler on the concrete 6502, section 5b), `tools/altirra_fuzz.cmd` + `tools/analyze_fuzz.py` (adversarial frames in the emulator); tests: `tests/test_static_wcet.py`; the measured side is `38-main-loop.md`.

## 1. The result

- **A static upper bound of the instruction cycles of one handler run** (`$A5FD` to `JMP XITVBV`) exists for every frame class, for any contents of memory and any hardware input, under **6 loop bounds argued by hand** (section 3, all tested against the game).
- **What the handler's thread really gets was measured** (section 4): a counting loop in place of the handler runs from its entry to the next interrupt: **16,100 cycles on the game screen, 19,750 on the title and copyright screens**, the same in every one of 23,323 frames of the game screen. Display DMA, the 5 display-list interrupts and the OS's own work are all in it.
- **12 of the 15 classes are proved to fit**: their bound is below the budget of their screen (copyright setup, copyright wait, title menu, title after game, paused, board start, start idle, game-over countdown, death, eaten pause, the **turn control: 14,226 against 16,100**, and the **level end: 14,846**).
- **The level end is proved by its stages** (section 4a): its five stages are bounded one by one (6,096, 3,197, 3,165, 10,322, 14,846), and the heavy stage 4 is entered with the entities at their start positions, which the frame of stage 3 leaves (`InitBoard`) - checked by the tool - and nothing between the two frames changes. The tunnel clip is then light. Without this the level end is 17,581 (16,003 if at most two entities are in a tunnel zone, a fact that was tested and is no longer needed).
- **The play frame is not proved: 32,049**, twice the budget, and so are the start-tune and ready-wait frames whose last frame plays (32,417, 32,233). Every way tried to tighten it failed (section 5): the set search stops at 14 million states for one ghost and gains 750 cycles, and even with each ghost fixed to one state a run passes 50 million. **What is known instead (section 5b)**: the static bounds are sound and tight where they can be (no concrete frame of any class costs more than its bound; the turn control and the last two stages of the level end are reached to 96-100%), and a search for the heaviest play frame on the real handler finds **14,278 instruction cycles at most** on arbitrary memory (89% of the budget; 11,806 by plain hill climbing) and **11,026 with every byte inside its documented domain** (68%), against the static 32,049. The play frame's true worst lies between 14,278 and 32,049 on arbitrary memory (11,026 and 32,049 inside the domains); the budget is 16,100. For these three classes "stays inside 262 lines" is the measurement of `38` and this search, not a proof - a documented limit (OV-64, C-80).
- **The rare paths of the frame have sessions** (section 6).

## 2. The static bound

`tools/absint6502.py` (docs/34) run from `$A5FD` with the dispatcher's own variables followed (`$19 $9B $1C $20 $26 $21 $22 $24 $ED $E5`, set to the values that give the class, and `$FE`) and everything else unknown. Unlike docs/34 the search keeps the states **exact** (no joins), so a path of the graph is a path of the abstraction, and the bound is the **longest path** of that graph with the cycles of the NMOS 6502: an indexed read costs +1 for a page crossing - **exact when the index is known, and assumed only when the table does not start on a page** (the maze copies read `$0800,x` and the like, which never cross: the first version charged 1,024 cycles to every copy it could not have); a taken branch +1, +1 more on a page change. A loop the abstraction cannot follow shows as a cycle of the graph; the search reports it and does not bound it. After the bounds of section 3 no cycle remains in any class.

For the classes that run on the game, title and copyright screens (all but the play-type ones) two further things are followed, which is what brings the turn control under its budget: **the positions of the five entities** (`$85-$8E`), and **the current player** (`$2B`, 0 or 1 - docs/34: the bound is the larger of the two runs). The turn control calls `InitBoard`, which clears `$80-$FF` and copies the start positions from `ZeroPageInit80`; with the positions known the tunnel clip at the end of the frame sees three ghosts on row `$74` inside the house and nothing in a tunnel zone, and the lives code (`dec zp_2C,x`, X = the current player) no longer wipes everything the search follows.

## 3. The loop bounds (claims about the game, each argued and each tested)

| pc | per call of | at most | most seen in the game | why |
|---|---|---|---|---|
| `$ACDF` | `DrawLevelIndicator` (`$AC93`) | 6 | 5 | X counts 0 to `zp_2A`, which is below 6 (`cmp #6 / bcs` at `$ACB8`) |
| `$AFF3` | siren (`$AFD7`) | 1 | 1 | one test per call |
| `$B018` | siren (`$AFD7`) | 1 | 1 | from `$B018` the path goes to `$B007`, where `E1 + $10` (E1 = `$40`) is not 0, so it leaves at `$B00C` |
| `$B53D` | siren 2 (`$AF54`) | 1 | 1 | `SirenStep + DE` at `$B52C` is not 0 (SirenStep is 2, 3 or 4 - written only at `$B5FF` - and DE starts at `$28`) |
| `$B8E8` | one ghost's update (`$B7F5`) | 1 | 1 | `GhostGoToCorner` jumps to `GhostSelectPatrol`, which sets the timer to `$96`, so the travel does not go back to the corner |
| `$B9F2` | `SteerToTarget` (`$B999`) | 2 | 2 | the loop `$B9EA` to `$B9EE` needs `WantHoriz` = 0 at `$B9EA` and (`WantHoriz` and `zp_2A`) not 0 at `$B9F0`, which cannot both hold: at most 2 passes |

**Tested** (`analysis/evidence-loopbounds-summary.txt`, `tools/run_mainloop_audit.ps1 -Loops`, the 7 sessions of `38` and the rare session): tracepoints on each pc and on the entry of its routine, executions counted per call. The most seen is at or below every bound; 5 of the 6 are reached exactly. A test is not a proof: a bound is a claim read from the code.

**Proved by the search, not claimed**: the loops of `ClipEntityAtTunnel` (`$AB7B`, `$ABA3`) were first bounded by hand at 8 executions and the bound was **wrong by one** (the shift loop runs its test 9 times, the 9th without a carry): once `$FE` is followed (it is loaded with `$FF` and shifted) the search unrolls them itself. That is the argument for following a variable instead of claiming a bound where one can.

The bound of `$B53D` is also a finding: if `SirenStep` and `DE` were both 0 the code at `$B52C-$B53D` would never leave; the game cannot have both (DE is set to `$28` at `$B512`).

## 4. What the handler's thread gets, and the result per class

**Measured** (`tools/altirra_budget.cmd` and its `_title` and `_copyright` variants, `analysis/evidence-budget-summary.txt`): from a chosen frame on, at every entry of the handler the program counter is sent to a loop in RAM (25 cycles an iteration: a 16-bit counter) and the stack pointer is reset; the loop runs until the next vertical-blank interrupt takes it over, and at the next entry it saves its count and starts again. The loop also clears the display-list interrupts' band counter (`$18`) as the handler does. Result:

| Screen | Iterations a frame | Cycles for the handler's thread |
|---|---|---|
| game (the maze) | 644 in all 23,323 frames | **16,100** |
| title | 791 (790 in 72 of 18,271 frames) | 19,750 |
| copyright | 791 (790 in 70 of 17,922 frames) | 19,750 |

This is the whole of what the display, the display-list interrupts and the OS take, in the machine, from the entry to the interrupt that ends the window. `tools/dma_model.py` models the display from the display list (`$BFA3`, 5 interrupts at lines 39, 47, 207, 215 and 231 - the lines of `38`) and gives 16,425 for the game screen: **2% above the measurement**, because it runs to the next *entry* and the next interrupt comes 8 lines earlier. The model is kept as a cross-check; the fit is decided with the measurement. (`tests/test_static_wcet.py`: the model never gives less than a measured frame.)

| Class | Screen | Static bound | Budget | Fits? |
|---|---|---|---|---|
| copyright setup | copyright | 9,205 | 19,750 | yes |
| copyright wait | copyright | 3,030 | 19,750 | yes |
| title menu | title | 4,905 | 19,750 | yes |
| title after game | title | 4,705 | 19,750 | yes |
| paused | game | 3,114 | 16,100 | yes |
| board start | game | 3,881 | 16,100 | yes |
| start idle | game | 3,123 | 16,100 | yes |
| game-over countdown | game | 3,162 | 16,100 | yes |
| death | game | 5,923 | 16,100 | yes |
| eaten pause | game | 13,150 | 16,100 | yes |
| **turn control** | game | **14,226** | 16,100 | **yes** |
| **level end** | game | **14,846** (stages 6,096 / 3,197 / 3,165 / 10,322 / 14,846; 17,581 without the stages) | 16,100 | **yes** |
| play | game | 32,049 | 16,100 | no |
| start tune, ready wait (their last frame plays) | game | 32,417 / 32,233 | 16,100 | no |

(The classes on the title and copyright screens would fit the smaller budget as well.)

### 4a. The level end, stage by stage

The level end is `LevelComplete` (`$26`) with a stage counter `LevelEndStep` (`$27`): the frame code at `$AC18` draws (stage 0), waits and flashes (stages 1 and 2), calls `InitBoard` (stage 3, `$AC6F`) and then, at stage 4, `AdvanceLevel`: `NewBoardInit` with the 920-byte maze copy (10,503 cycles) and the new READY! screen. The state proof of docs/34 lists every store to the counter: 0 to 1, 1 to 2 and 2 to 3 at `$AC26`, **3 to 4 at `$AC72`** (right after `InitBoard`), 4 to 0 at `$AC88`, and a clear to 0 at the restart (`$A47B`). So stage 4 is entered only from the frame of stage 3.

The search without the stages (`$27` unknown) charges the stage-4 frame with the tunnel clip of five entities at unknown positions: 17,581 (the heavy path of `ClipEntityAtTunnel` costs 526 cycles against about 60 for an entity not in a zone; at most 2 entities in a zone would give 16,003, 3 would give 16,529). With the stages:

| Stage | What the frame does | Bound |
|---|---|---|
| 0 | `ClearPokeyRegisters`, `DrawAllInPlace`; entities at unknown positions (the clip may be heavy for all five) | 6,096 |
| 1 | the wait | 3,197 |
| 2 | the flashing | 3,165 |
| 3 | `InitBoard` (`FillPlayerPages` 8,170) | 10,322 |
| **4** | `AdvanceLevel`: the maze copy, the level indicator, READY!; **entities at the start positions** | **14,846** |

**Why the entities are at the start positions in stage 4**: (1) the tool runs the frame of stage 3 from unknown positions and every path leaves with `LevelEndStep` = 4 and the entity bytes `$85-$8E` equal to the start positions that `InitBoard` copies from `ZeroPageInit80` (`tools/static_wcet.py`, `check_level_end_chain`: one exit state, positions Y 100, 116, 116, 116, 164 and X 124, 124, 112, 136, 124 - three ghosts on row `$74` inside the house, none in a tunnel zone); (2) nothing writes the entity bytes between the end of that frame and the entry of stage 4. The code that writes them: `MovePacMan` and `StepAndDrawEntity` and `ClipEntityAtTunnel` (all in the handler, and in the frames in between only the level-end code runs: a paused frame returns at once), `InitBoard` (the restart at `$A4A3`, turn control, stage 3) and the power-on code. The restart is the one writer outside the handler: it clears `$20-$3F` (`$26` and `$27` with them) at `$A47B`, **before** it reaches `InitBoard` at `$A4A3`, so a level-end frame never sees half-cleared positions with the counter still at 4. The stage-4 run itself follows the positions through the whole frame (they are not the start positions any more when the frame ends: the draw routines write them, and the search follows that) and the clip never finds a heavy case.

(The tunnel fact of the first version - at most two entities in a tunnel zone - was tested before this proof (`analysis/evidence-clip-summary.txt`, `tools/analyze_clip.py`: the most in any of 251,267 frames is 2) and is no longer needed.)

## 5. Why the play frame is not tighter

The longest path of the play frame has 16 calls of `JunctionLookup`, 12 of `SteerToTarget`, 4 of `GhostSeesPacMan`, 5 of `ClipEntityAtTunnel` and 4 ghost updates, each in the heaviest state its branches allow; the real frame has one state per ghost, and a ghost cannot be an eaten ghost (`EyesAndHousePerFrame`) and a chasing ghost in the same frame. The search cannot say so because it does not follow the ghost states: a byte that is not followed is unknown at every read.

**The set-of-values search was built and stopped** (`tools/wcet_sets/wcet_sets.cpp`, run by `tools/wcet_sets.py`). It is a C++ port of the abstract 6502 in which a ghost-state byte is a set of possible values (256 bits; the 229 values the proof of docs/34 reached): a load of the byte gives the accumulator a table, the flags the next instructions set are tables, and a branch on such a flag narrows the set on each side, so two tests of one byte in a frame cannot disagree. Only 128-bit hashes of the states are kept (24 bytes a state). **The port is checked against the Python search**: with the ghost bytes not followed it gives the same bounds (paused 3,114, death 5,923, level end 17,581, and, before the page crossing was made exact, the play frame's 32,764 in 1.12 million states in seconds); the differences it showed on the way (a ROM path with a space in it read as zeros) were fixed.

| Ghost bytes followed as sets | States | Bound (play, page crossing assumed) |
|---|---|---|
| none | 1.12 million | 32,764 |
| 1 (`$CE`) | **18.35 million** | 32,603 |
| 2 | more than 60 million (stopped at the limit, 64 s) | - |
| 4 | more than 30 million (stopped, 33 s, still growing 1 million a second) | - |

The state count does not stay near a few million: it grows about 16 times per ghost followed. And **following a ghost buys almost nothing**: ghost 0 followed lowers the bound by 161 cycles. So the mixing of states *within one ghost* is not what makes the bound large; what does is the **four ghosts being in their heaviest state in the same frame** (each ghost's worst consistent path is already about 7,000 instruction cycles in the abstraction), and excluding that needs facts about where the ghosts are and when they reach junctions, which no variable the search follows holds.

### 5b. What the real handler costs: the bounds against the concrete 6502, and a search for the heaviest play frame

**Soundness and tightness of the static bounds** (`tools/check_bounds_concrete.py`, `analysis/evidence-bounds-concrete-summary.txt`): random frames of every class (the project's `frame_setup` of stage 55, the dispatcher variables set to the class) are run on the concrete 6502 (`tools/cpu6502.py`) with the instruction cycles counted exactly (the table of section 2 with the real index registers and branch outcomes). 200 frames a class: **no frame of any class costs more than its bound**, and for the classes whose worst path is real the bound is almost reached: level end stage 3 10,310 of 10,322, stage 4 14,350 of 14,846, turn control 13,657 of 14,226. So the cycle table and the abstract search count what the machine counts. For the play frame the random frames reach 6,206 of 32,049 (19%).

**Searching for the heaviest play frame** (`tools/fuzz_concrete.py`, `analysis/evidence-fuzz-summary.txt`): a hill climb on the same concrete handler: it starts from a random play frame (the dispatcher fixed to play), changes one byte of the zero page or of the sight tables, or one of the random numbers the frame reads, and keeps what costs at least as much; 700 s, 200,000 to 250,000 handler runs each. With **every byte changed inside its documented domain** (ghost states the 16 of docs/34, directions 1/2/4/8, positions on the junction lines, timers up to `$96`, move delays up to 7): **8,582, 8,887, 9,228**. With **arbitrary memory** (the dispatcher still in the play state): **11,397 and 11,806**. In the emulator (`tools/altirra_fuzz.cmd`) 76,245 play frames with random ghost states, junction positions, directions and expired timers (the junction was first picked with a shift the debugger does not have, so it was always the same; the harness was corrected and rerun: same heaviest frame) cost at most 9,750 elapsed cycles of the 28,956 the handler has, and the natural sessions of `38` 11,799.

What it says: the heaviest play frame found is **14,278 instruction cycles, 89% of the 16,100 budget, on arbitrary memory**, and 11,026 (68%) inside the domains; the static bound, 32,049, is 2.2 times the first. The true worst case is somewhere in between and the search does not tell where: it is a lower bound, as every search is. **The stronger search** (`--anneal`, `analysis/evidence-fuzz-summary.txt`: simulated annealing with 4000 steps per restart from a temperature of 400 cycles, 2 to 4 changes at a time, and a move that copies one ghost onto another; 5 runs of 1,500 s on arbitrary memory and 5 inside the domains, 160,000 to 220,000 handler runs each) raised the lower bound from 11,806 to **14,278** (the five runs: 14,035, 14,278, 10,072, 11,500, 10,135) and from 9,228 to **11,026** inside the domains (9,565 to 11,026). The heaviest frames put **all four ghosts in the same state at the same place**; on arbitrary memory that state is one the game never writes (`$D5`, `$C4`: not one of the 16 of docs/34), so they exploit code paths no game reaches; inside the domains the best is four ghosts in state `$04` (leaving the house) at one tunnel position with expired timers - a frame the game does not produce either (ghosts do not leave the house on the same frame in the same cell). The searches still differ a lot between runs (10,072 to 14,278): a longer run could find more, and none went above the budget. The result is that **the margin is not as large as the first search suggested**: 11% of the budget on arbitrary memory.

(The first version of the search kept the memory *after* each run as the next input and drifted into the level-end frame, whose 14,100-14,200 cycles it reached against the static 14,846: that error is why the input state is saved before the run.)

## 6. The rare paths in sessions

`tools/altirra_rare.cmd` (run with `tools/run_mainloop_audit.ps1 -Only rare`; `analysis/evidence-mainloop-rare-summary.txt`): five games in one session, driven through the game's own console reads and the space bar - pauses in the start tune, play and later; SELECT in play; START in play and in the start tune; OPTION in play; START at the title. 60,932 frames, no handler entry missed, never late. New transitions seen: **paused to start tune**, **start tune to paused**, **start tune to start idle**, and play to title menu 2 times, play to start idle once more (the main sessions had each once). The heaviest handler run in this session is 106 lines.

## 7. Limits

- The bound counts instruction cycles; the budget is a measurement of one machine (Altirra 4.40, NTSC, the game's own display lists), not of a real Atari. PAL is not covered.
- The 6 loop bounds are read from the code and tested, not proved; the proved ones are the two the search follows. The entry state of stage 4 of the level end rests on the list of the writers of the entity bytes (4a), read from the code; the chain from stage 3 is checked by the tool.
- Three classes (play, and the start-tune and ready-wait frames that end in a play frame) are not proved to fit: their static bound is above the budget and the search of 5b is a lower bound. OV-64 is closed on this as a documented limit by the owner's decision (register C-80); what would reopen it is a play frame above 16,100 instruction cycles in a state a game can reach (`tools/fuzz_concrete.py`), or a proof that the four ghosts cannot all be in their heaviest state in one frame.
- The search follows the dispatcher's variables, `$FE`, the entity positions and the current player; every other byte is unknown. The domain of the current player (0 or 1) is the proof of docs/34.
- The rare session uses test aids (invulnerable Pac-Man, a bot, console values written into the key loop's reads); the game's own code does the rest.
