# Progress Tracker

Master checklist = the 100 stages of "Decompilation steps.txt". Project steps (A1, A2 …) are the
approval units; each maps to one or more checklist stages.

Legend: DONE, NEXT, TODO, N/A (not applicable, with reason).

## Project steps

| Step | Description | Checklist stages | Status |
|---|---|---|---|
| Initial | Inspection and planning | 4–7, 11–16 (partial) | DONE (2026-11-10, approved) |
| A1 | Scope, methodology, requirements documents | 1, 2, 3 | DONE (approved) |
| A1b | Check assumption A1 (ROM identity) by web hash lookup / saved thread | 5, 7 (partial) | DONE – inconclusive (approved) |
| A2 | Folder structure, .gitignore, local Git repo | 9 | DONE (approved 2026-11-10) |
| A3 | File inventory, checksums, read-only ROM backup | 6, 7, 8 | DONE (approved 2026-11-10) |
| A4 | Install analysis tools (needs owner OK) | 10 | DONE – awaiting approval |
| A5 | Boot ROM in emulator (needs owner screenshot) | 51, 52 | NEXT |
| B6–B7 | Hardware/memory-map documentation, vectors | 11–20 | TODO |
| C8–C11 | Disassembler, full disassembly, byte-exact rebuild, data labelling | 21–30 | TODO |
| D12–D16 | Control flow, variables, subsystem analysis | 31–50 | TODO |
| E17–E18 | Emulator traces, correlation | 51–60 | TODO |
| F19 | Resource extraction/decoding | 69–70 | TODO |
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
Stage 44 (stack) – Adapted: 6502 hardware stack page $0100.
Stage 59 (API tracing) – Adapted: OS vector and hardware-register tracing.
Added stage – byte-exact reassembly check (inside step C10).
Remaining stages: status set when their steps begin.
