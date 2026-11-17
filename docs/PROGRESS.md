# Progress Tracker

Master checklist = the 100 stages of "Decompilation steps.txt". Project steps (A1, A2 …) are the
approval units; each maps to one or more checklist stages.

Legend: DONE, NEXT, TODO, N/A (not applicable, with reason).

**Status 2026-11-14:** the functional verification of the whole game is finished (the register has one open item, OV-02, which needs the C re-implementation). What stands between this and stage 71 is documentation of the analysis (stages 31–40 as written deliverables, the variable catalogue of 41–48, one architecture document for 61–68, the resource format of 69–70) and the owner's decisions for 71–74. The order of work is at the end of this file.

Everything that still needs verification (partial checks, aids, unexplained results, unreached cases) is kept in one place: [OPEN-VERIFICATION.md](OPEN-VERIFICATION.md). Update it whenever a check is skipped, partial or closed.

## Project steps

| Step | Description | Checklist stages | Status |
|---|---|---|---|
| Initial | Inspection and planning | 4–7, 11–16 (partial) | DONE (2026-11-10, approved) |
| A1 | Scope, methodology, requirements documents | 1, 2, 3 | DONE (approved) |
| A1b | Check assumption A1 (ROM identity) by web hash lookup / saved thread | 5, 7 (partial) | DONE – inconclusive (approved) |
| A2 | Folder structure, .gitignore, local Git repo | 9 | DONE (approved 2026-11-10) |
| A3 | File inventory, checksums, read-only ROM backup | 6, 7, 8 | DONE (approved 2026-11-10) |
| A4 | Install analysis tools (needs owner OK) | 10 | DONE (approved 2026-11-10) |
| A5 | Boot ROM in emulator (needs owner screenshot) | 51, 52 | DONE (approved 2026-11-10) |
| B6–B7 | Hardware/memory-map documentation, vectors | 11–20 | DONE (approved 2026-11-10) |
| C8 | Disassembler built and validated | 21–22 | DONE (approved 2026-11-10) |
| C9 | Full disassembly | 23–25 | DONE (approved 2026-11-10) |
| C10 | Byte-exact rebuild (formal) | 26–28 | DONE (approved 2026-11-10) |
| C11 | Data labelling and routine naming (first pass) | 29–30 | DONE – approved by the owner (2026-11-14; data formats added 2026-11-10) |
| D12–D16 | Control flow, variables, subsystem analysis | 31–50 | IN PROGRESS: traced and verified in substance, written-up deliverables open (see "Stage status 31–70") |
| E17–E18 | Emulator traces, correlation | 51–60 | DONE in substance (2026-11-14) – approved by the owner (2026-11-16); every check is in `OPEN-VERIFICATION.md` (all closed except OV-02) |
| F19 | Resource extraction/decoding | 69–70 | PARTIAL: a first decoded set exists locally (`resources/decoded`, gitignored); format and verification not documented |
| G20–G22 | Architecture, C re-implementation, hardware layer | 71–80 | TODO |
| H23–H24 | Equivalence testing, discrepancy fixes | 81–90 | TODO |
| I25–I26 | Final documentation, archive, GitHub (owner approval) | 91–100 | TODO |
| J | Native Windows 11 port | – | LOCKED until A–I verified |
| K | Modernization | – | LOCKED until J verified |

## Checklist stage notes

Stages 1–3 – DONE (see `01-scope-and-methodology.md`).
Stage 4 – DONE (ROM supplied by owner). Stage 5 – supporting material: none supplied; to be gathered.
Stage 17 (compiler/toolchain) – N/A in the usual sense: hand-written 6502 assembly expected; to be confirmed.
Stage 18 (libraries) – Adapted: dependency is the Atari OS ROM, not libraries.
Stage 45 (heap) – N/A: no dynamic memory on this platform.
Stage 44 (stack) – done 2026-11-14 (`28-stack.md`).
Stage 59 (API tracing) – Adapted: OS vector and hardware-register tracing; done 2026-11-17 (`35-api-hardware-tracing.md`).
Added stage – byte-exact reassembly check (inside step C10).
Remaining stages: status set when their steps begin.

## Stage status 31–70 (2026-11-14)

DONE = the result exists and is written down; SUBSTANCE = the work was done and verified (in the chapter named) but there is no single deliverable for the stage; PARTIAL / TODO as written; ADAPTED / N/A = the stage means something else on this platform.

| Stage | Status | Where / what is missing |
|---|---|---|
| 31 Branch identification | DONE | the recursive trace of `tools/make_asm.py` (2,925 instructions, 463 chunks, 0 data bytes uncovered); byte-exact rebuild |
| 32 Jump destination resolution | DONE | same; every JSR/JMP/branch target is a label in `src/asm/pacman.s` |
| 33 Control flow graph | DONE – approved by the owner (2026-11-14) | `26-control-flow-graphs.md`: the basic-block graph of all 81 routines (1,703 blocks, 2,389 edges; table plus Mermaid diagram each), back edges / natural loops, cyclomatic complexity, exit blocks; 75 graphs are reducible, 6 are not (a loop with a second entry through `lda #imm / bne`: FrameDispatch, FrightenedTick, FrightenedSound, MovePacMan, GhostBehaviour, SteerToTarget) (`tools/analyze_cfg.py`, `tests/test_cfg.py`); call tree and body in `23-function-table.md` |
| 34 Loop identification | DONE | the backward branches of every routine are counted in `23-function-table.md` (81 routines); the loops that matter are described in the chapters |
| 35 Function boundaries | DONE (2026-11-14) | 81 routines (66 JSR targets, the entry points, the named jump targets); the 39 that were `Sub_XXXX` are named (`11-labelling.md`, `tools/labels.py`) |
| 36 Function calls | DONE | `23-function-table.md`: callers and callees of every routine, tail jumps, and the call tree from the five entry points; no indirect call or jump exists |
| 37-39 Parameters, return values, calling convention | DONE – approved by the owner (2026-11-14) | `23-function-table.md`: inputs (registers and flags read before written), clobbers, saved-and-restored registers, results observed at the call sites, zero-page variables read and written per routine; the convention is stated there and tested (`tests/test_functions.py`) |
| 40 Function relationship mapping | DONE – approved by the owner (2026-11-14) | `24-function-relationships.md`: the 80 routines in 14 subsystems with a role each (a proposed name for the 39 `Sub_XXXX`), the subsystem call matrix, the start-up order, the interrupt-time order and one frame of play in the order of the code (`tools/analyze_relationships.py`, `tests/test_relationships.py`); one chapter per subsystem (13-22) for the detail |
| 41 Global variables | DONE and APPROVED (2026-11-14) | `25-variable-catalogue.md`: every zero-page byte the code touches (132) in 109 variables, each with name, size, role, evidence and who reads / writes it (81 GLOBAL, 28 LOCAL), the RAM areas outside the zero page, and the state shared by three or more subsystems (`tools/analyze_variables.py`, `tests/test_variables.py`). **The 60 new names are proposals, not yet in `tools/labels.py`** |
| 42 Local variables | DONE (2026-11-14) – approved by the owner (2026-11-16) | `27-local-variables.md`: the 6502 has no locals, so they are found by data flow (read-before-written per routine, liveness at every call site): the 28 single-routine variables are 8 TEMPORARY (automatic in C), 19 STATIC (state kept between calls), 1 OS; `Scratch2A` is the one shared byte that is a temporary in some routines; the stack use (PHA/PHP, 8 routines) and saved registers; per-routine table of 81 routines (`tools/analyze_locals.py`, `tests/test_locals.py`) |
| 43 Register usage | DONE – approved by the owner (2026-11-14) | `23-function-table.md` (per routine: A, X, Y and the flags C, Z, N, V) |
| 44 Stack | DONE (2026-11-14) – approved by the owner (2026-11-16) | `28-stack.md`: the hardware stack only (page 1, no instruction addresses it, S = `$FF` from the `TXS` at `$A480`), 8 `PHA`/`PHP` pushes in 5 routines, every one of the 81 routines balanced, no indirect jump; depth per routine and per interrupt handler from the code, and measured in Altirra over 5 session harnesses (about 590,000 frames, 3.0 million display-list interrupts, the interrupted pc read from the stack at each): deepest case 21 bytes (the model predicts it exactly), bound by construction 28, of 256 (`tools/analyze_stack.py`, `tools/run_stack_audit.ps1`, `tools/analyze_stack_log.py`, `tests/test_stack.py`, `analysis/evidence-stack-summary.txt`); OV-54 closed (C-54) |
| 45 Heap | N/A | no dynamic memory |
| 46 Pointers | DONE (2026-11-15) – approved by the owner (2026-11-16) | `29-pointers.md`: the 31 indirect instructions (all `lda/sta (zp),y`; no `(zp,X)`, no `JMP (abs)`), the 6 pointer variables with every read, every load (constant, table or computed) and every bulk clear, the 4 pointer tables (23 entries, every target named), the display-list and vector addresses, the OS / ANTIC pointers, the port representation; a stray 16-byte copy into the ROM at every `InitDisplay2` (harmless) found; **measured** in Altirra over 5 harnesses (1.33 million probe hits at 19 probes, 0 rule violations) (`tools/analyze_pointers.py`, `tools/run_pointer_audit.ps1`, `tools/analyze_pointer_log.py`, `tests/test_pointers.py`, `analysis/evidence-pointers-summary.txt`); OV-55 and C-55 |
| 47 Arrays | DONE | tables in `12-data-formats.md`, `14-levels.md`, `15-small-tables.md` |
| 48 Structures / objects | DONE (2026-11-16) – approved by the owner (2026-11-16) | `30-structures.md`: the ROM keeps its objects as a structure of arrays (stride 1, indexed by X); all 109 zero-page variables (184 bytes) are the fields of 14 structures (`Entity`[5], `Ghost`[4], `Player`[2], `PacMan`, `GhostShared`, `Frighten`, `Bonus`, `Death`, `Sound`, `Flow`, `Display`, `Scratch`, `Pointers`, `Os`) with C type, original address and lifetime (cleared at start-up / game / every `InitBoard`); the 191 indexed accesses (all at offset 0 except `GhostTimer+1,x`); the initial state of the five entities; the RAM / ROM record shapes, player-missile pages, picture buffers and the proposed C layout; **measured** in Altirra over 11 harnesses (93 million index hits at all 191 sites, 0 outside their array; 89 `InitBoard` snapshots and 29 restart snapshots as modelled) (`tools/analyze_structures.py`, `tools/run_structure_audit.ps1`, `tools/analyze_structures_log.py`, `tests/test_structures.py`, `analysis/evidence-structures-summary.txt`); C-56; OV-56 (C-57) and OV-57 (C-58) closed |
| 49 Lookup tables | DONE | `12`, `14` (every level-dependent table over levels 0-255), `15`, `16` |
| 50 Constants and algorithms | DONE (2026-11-16) – approved by the owner (2026-11-16) | `31-constants-algorithms.md`: all 651 immediate constants of the code by routine (what each is compared with, assigned to, masked or added to), 51 named constants with C names, 22 algorithms covering all 81 routines (rule, tables, evidence, status), `RANDOM` read at exactly 3 places; all 22 algorithms (first data expansion, score BCD, speed pacing, release timers, junction lookup, steering; since OV-58 / C-60 the rest up to the whole frame, `tools/algorithm_models2.py` .. `algorithm_models7.py`, `tools/analyze_model_coverage.py`) **run as models against the ROM** in the new 6502 interpreter `tools/cpu6502.py` (0 differences in about 76,000 calls; the real `Start` builds the same RAM images as the decoders) (`tools/analyze_constants.py`, `tools/algorithm_models.py`, `tools/cpu6502.py`, `tests/test_constants.py`, `tests/test_algorithms.py`, `analysis/evidence-algorithms-summary.txt`); C-59, OV-58 closed (C-60: about 940,000 calls, 0 differences, every instruction of the ROM executed, 27 one-sided branches explained) |
| 51 Execution environment | DONE | Altirra 4.40, NTSC and PAL, OS-B, the PAL OS and the built-in OS (`04`, `22`) |
| 52 Baseline execution | DONE | `05-first-boot.md` |
| 53-56 Traces, breakpoints, RAM and register inspection | DONE (2026-11-16) – awaiting approval | `32-tracing-and-inspection.md`: **53** coverage of the ROM by 33 live sessions (2,920 of 2,925 instructions in 36 sessions, 79 of 79 routines, 124 of 124 JSR sites; the 5 never executed are dead code of the original, shown from the code; OV-59 closed by three more sessions, C-62), **54** the inventory of the 75 harnesses and their 179 breakpoint addresses (every one an instruction start), the conventions (sentinel, `@a`, numbering, named test aids), **55** memory snapshots at twelve events (2,827 changing bytes, all in the catalogue of `25` or a named class), **56** registers at every entry and exit (5.55 million calls, 0 violations of the claims of `23`), and the pause key live (`tools/run_coverage_audit.ps1`, `run_register_audit.ps1`, `run_memory_audit.ps1`, `analyze_coverage.py`, `analyze_registers.py`, `analyze_memory.py`, `analyze_harnesses.py`, `analyze_tracing.py`, `tests/test_tracing.py`); C-61, C-62, OV-59 (closed) |
| 57 Input / output observation | DONE (2026-11-16) – awaiting approval | `33-input-output.md`: the complete inventory of the 133 instructions that read an input or write an output (51 registers: STICK0/1, STRIG0/1, CONSOL, CH, RANDOM, the collision registers, the OS clock; the ANTIC / GTIA / POKEY outputs; the OS hand-over), the meaning of each, and what the real game does there: all 133 executed in 11 sessions, with the values seen (CONSOL all 8, STRIG 0 and 1 on both ports, both players' sticks, the pause key); the heuristic list of `06` is replaced (`tools/analyze_io.py`, `tools/run_io_audit.ps1`, `tools/altirra_inputs.cmd`, `tests/test_io.py`); the keys' effects stay in `21`, the screens in `15`, `16`, `19`, `20`; C-63 |
| 58 State transitions | DONE (2026-11-17) – awaiting approval (OV-60 closed, C-66: the `$A800` race is a path of the search that no game can take) | `34-state-transitions.md`: the 20 state variables of the game (screen, start, turn, level end, pause, death, eaten pause, frightened phase, bonus, the four ghosts) with the instructions that write them, **68 transition rules** written from the code (checked against it) and every change in 20 sessions of the real game (243,000 writes watched): 0 transitions without a rule, 68 of 68 rules seen; **every pair of every rule is also made by the code run in the interpreter with every variable forced to every domain value** (99,057 calls; the code makes more at 12 instructions); **proved against every behaviour of the code by abstract interpretation** (`tools/absint6502.py`, `tools/prove_state_rules.py`, 11 slices, up to 29.8 million search states each): 0 stores that no rule allows, 11 of the 12 extra-pair sites never make their extra pairs, every live change is inside the result; **found: a race at `$A800`** (ghost 0 incremented twice, a path of the search that no game can take: the dot counter is zero there, OV-60 closed, C-66); the ghost-0 slice leaves out three variables (C-65); a state diagram of what was seen per variable (`tools/analyze_states.py`, `tools/run_state_audit.ps1`, `tools/check_state_rules.py`, `tests/test_states.py`, `tests/test_absint.py`); the chapters `17`, `18`, `19`, `20`, `21` keep the reasons; C-64, C-65, C-66; OV-60 closed |
| 59 API / hardware tracing | DONE (2026-11-17) – awaiting approval (OV-61 closed, C-68: a real space-bar press through the OS keyboard IRQ) | `35-api-hardware-tracing.md`: the OS API of the game is two calls (`SETVBV`, `XITVBV`) plus the shadow area; **traced in 8 sessions of the real game** (116,495 frame entries, none missed; every CPU write to GTIA / POKEY / ANTIC with writer and scan line, 4.66 million; the display-list interrupts by line and what each writes); the chips equal the OS shadows (1.74 million checks) and the last CPU write (4.19 million checks), **0 violations**; all 71 static chip-write sites seen, none outside (`tools/run_hw_audit.ps1`, `tools/analyze_hw.py`, `tests/test_hw.py`, `analysis/evidence-hw-summary.txt`); the sound itself stays in `22-sound.md`; C-67; OV-61 closed (C-68) |
| 60 Behaviour correlation | DONE (2026-11-17) – awaiting approval (the only open item of the register is OV-02, the port) | `36-behaviour-correlation.md`: 24 behaviours, 22 algorithms and 81 routines tied to their rule (chapter), live measurement (register entries, harness sessions) and executable check (tests, models); every routine and algorithm is carried by a behaviour, every named file and entry exists, checked mechanically (`tools/analyze_correlation.py`, `tests/test_correlation.py`); C-69 |
| 61 Startup | DONE (2026-11-17) – awaiting approval | `37-startup.md`: power-on to the title on NTSC OS-B, PAL OS-B and the built-in OS (the OS reads the header, calls INIT = the shared `RTS` at `$A6B4`, jumps to RUN with S=`$FF` I=0 D=0; every step of `Start` with its frame and scan line; the same state at the first key loop on all three machines), the warm start, and **what the game takes from the power-on state** (the OS's zeros at `$0400-$041F` and `$0B98-$0BFF`, a few OS zero-page values; random RAM changes nothing of the game's own state) (`tools/altirra_startup.cmd`, `altirra_warmstart.cmd`, `tools/startup_poison.py`, `tools/analyze_startup.py`, `tests/test_startup.py`, `analysis/evidence-startup-summary.txt`); C-70 |
| 62 Main loop | PARTIAL | `$A4BA-$A559` (keys, `21`), the VBI `$A5FD` and the per-frame routines `$A78C` / `$A82F` are described in pieces; **one frame-by-frame description is missing** |
| 63 Input processing | SUBSTANCE | `21` (the keys), `13`, `20` (STICK0 and Pac-Man's steering) |
| 64 Output processing | SUBSTANCE | screens (`15`, `16`, `19`, `20`, `21`), sound (`22`) |
| 65 State management | SUBSTANCE | game / title state `zp_19`, two players (`19`), levels (`14`), ghost states (`17`) |
| 66 Core algorithms | SUBSTANCE | ghost AI (`13`, `17`, `18`), Pac-Man (`20`), levels (`14`), scoring (`12`), sound (`22`) |
| 67 External interface | ADAPTED, SUBSTANCE | the hardware registers (`06`) and the OS vectors (`07`); no files, no network |
| 68 Communication | N/A | none |
| 69-70 Resources | PARTIAL | maze, charsets, shapes, text, tunes are decoded in `12`; a decoded set exists locally; **asset format for the port not defined** |

## What is left before the C re-implementation (stage 71)

1. This file brought up to date (done 2026-11-14).
2. **Function table and call graph** (stages 33-40, 43): DONE 2026-11-14 for inputs, outputs, registers, zero page and the call tree (`23-function-table.md`, 81 routines) and for the subsystems and the order (`24-function-relationships.md`, stage 40); the 39 `Sub_XXXX` are named (done 2026-11-14, `11-labelling.md`).
3. **Variable catalogue** (41, 42, 46, 48): stage 41 DONE and approved 2026-11-14 (`25-variable-catalogue.md`), stage 42 DONE 2026-11-14 (`27-local-variables.md`), stage 46 DONE 2026-11-15 (`29-pointers.md`), stage 48 DONE 2026-11-16 (`30-structures.md`); still open: **apply the proposed names** to the 83 `zp_XX`, the lifetimes are now in `30-structures.md` (section 5).
4. **Architecture document** (61-68): how one frame runs (main loop, VBI, DLIs, per-frame routines), and **resource format** (69-70).
5. **Owner decisions** (71-74): faithful frame-by-frame port with a thin hardware layer (recommended: the existing traces become the test oracle) or a redesign; the equivalence level (RAM state each frame, or visible behaviour and sound); C99 or C11, MSVC or clang, CMake or Makefile; layout of `src/c`.
6. Then stages 75-80 (the C code), with OV-02 closing at stage 86-87.
