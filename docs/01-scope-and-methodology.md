# 01 – Scope and Methodology

Status: written in Step 1 (2026-11-10). Covers master-checklist stages 1, 2 and 3.

## 1. Objective

Preserve Pac-Man for the Atari 8-bit family (target: Atari 800) by:

1. Fully reconstructing the original program as documented, labelled 6502 source that
   reassembles **byte-for-byte** into the original ROM.
2. Understanding and documenting how the game works (maze, ghost AI, scoring, timing, sound, video).
3. Re-implementing the game logic in readable, maintainable C.
4. Building a standalone native Windows 11 executable (no emulator needed).
5. Later, adding optional modernization while keeping a faithful "original mode".
6. Keeping everything in a private GitHub repository (only with the owner's explicit approval).

Accuracy, completeness, documentation and maintainability take priority over speed.

## 2. Scope boundaries

In scope: the 8 KB cartridge image `Pac-Man.rom` (6502 code, data tables, graphics, text, sound data);
documentation of the Atari hardware/OS features the game relies on; test and verification tooling.

Out of scope until explicitly unlocked:
- Windows port (Stage J) – starts only after reconstruction is verified (Stages A–I).
- Modernization (Stage K) – starts only after the Windows port is verified.
- Publishing: no GitHub repository, push or release without explicit owner approval.

## 3. Methodology (decision, checklist stage 2)

A **combination** of the methods listed in "Decompilation steps.txt":

| Method | Used for |
|---|---|
| Disassembly + source-level reconstruction | The 6502 code: result is annotated assembly that rebuilds the ROM exactly |
| Behavioural analysis (emulator traces) | Confirming what routines do; timing; ghost AI |
| Clean re-implementation in C | The Windows port, verified against the original |

Binary translation is rejected: it would produce unreadable code and defeat the maintainability goal.

Key principles:
- Evidence over assumption: every claim in the documentation points to an address, trace or test.
- Byte-exact rebuild is the gate for the disassembly phase.
- Behavioural equivalence (same inputs -> same game state and video) is the gate for the C phase.
- The original ROM is never modified; it is kept outside version control (copyright).

## 4. Adaptation of the supplied 100-stage checklist

"Decompilation steps.txt" is a generic checklist for PC executables. It is the master checklist
(see `PROGRESS.md`); each stage is marked Done, Adapted, or N/A with a reason. Notably:
- N/A or trivial: compiler/library identification (hand-written 6502), heap, stack frames, API tracing.
- Adapted: "system call tracing" becomes tracing of Atari OS vectors and hardware register access
  (ANTIC, GTIA, POKEY, PIA).
- Added: an explicit "reassemble and compare byte-for-byte" stage (not in the original list).

## 5. Working rules (from the project brief)

- One step at a time; verify before declaring done; document as we go.
- After each step: a report (completed work, approach, findings, files affected, verification,
  outstanding issues, documentation, next step), then STOP until the owner says "Approved, proceed".
- Assumptions and uncertainties are recorded explicitly (see section 7).

## 6. Requirements (checklist stage 3)

Functional:
- F1. Reconstructed assembly rebuilds a ROM identical to the original (SHA-1 match).
- F2. C re-implementation reproduces original behaviour: maze, movement, ghost AI, scoring, fruit,
  lives, attract mode, difficulty/option handling, sound, video.
- F3. Standalone Windows 11 executable, no emulator required.

Technical:
- T1. Reconstruction in C (C99 or later), game logic separated from the Windows/hardware layer.
- T2. Reproducible build with documented instructions.
- T3. Build tools free and documented (assembler, C compiler, emulator).

Compatibility / preservation:
- P1. Original behaviour is the default; modernization is optional and documented as a deviation.
- P2. Repository must not contain the ROM or Atari OS ROMs; users supply their own ROM.
- P3. Documentation must let another developer reproduce and continue the work.

## 7. Known facts, assumptions, open questions

Known (from initial inspection, 2026-11-10):
- `Pac-Man.rom`: 8,192 bytes, SHA-1 BC600EF63F8D1BDD3911981C2752EA23DB959960,
  MD5 E66E9AF9AF01B019CD4E54ABA813FBAC; raw cartridge image, no header.
- Mapped at $A000–$BFFF; trailer: start $A386, cart flag $00, option $04, init $A6B4.
- 6502 code at the start address; text stored as Atari screen codes.

Assumptions (to be verified):
- A1. The dump is the retail 1982 Atari cartridge. STATUS (2026-11-10): NOT CONFIRMED by hash,
  circumstantially consistent. Web searches for the SHA-1 and MD5 found no database entry
  (no exact-hash source reachable; AtariAge threads returned HTTP 403 to automated fetch).
  Consistent evidence: the retail Atari cartridge (CXL4022 / RX8022, 1982, developed by Roklan,
  per Atarimania) reportedly uses two 4K mask ROMs = 8 KB, matching our 8,192-byte image, and the
  trailer layout is the standard one. Not excluded: other 8K variants. Re-check later by
  comparing game behaviour in the emulator and, if possible, against a downloaded reference dump.
  Update (same day): the owner saved the AtariAge thread "What are these ROMs? Pac-Man cartridge?"
  (6BQ5, 2019-05-10; saved as an .htm in the project folder). It is a hardware-repair discussion with
  NO checksums or dump. Relevant statements (forum users, unverified): the Pac-Man cartridge board
  C012963 is an 8K board with two 2332 4K mask ROMs ("Pac Man is 8K"); one user believes the version
  with animated interludes is rarer and 16K; "the last 6 bytes of the ROM have the run address and
  flags". This supports the retail cartridge being 8K with the standard trailer, matching our file,
  but does not prove identity. Open sub-question: our ROM is the 8K version; whether it has
  animated interludes can be checked in the emulator (step A5).
- A2. The game runs on a stock Atari 800 with a replacement OS in the emulator.

Open questions:
- Q1. Exact release/revision of the ROM.
- Q2. Which OS ROM routines the game calls (to be mapped in Stage B).
