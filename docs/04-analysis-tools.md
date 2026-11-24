# 04 – Analysis Tools

Written in Step A4 (2026-11-10). Covers checklist stage 10. Tools live OUTSIDE the repository in
`external-tools\` in the project root (not committed); downloads are kept in `downloads\` for re-checking.

| Tool | Version | Source | Purpose |
|---|---|---|---|
| Altirra (`Altirra64.exe`) | 4.40 | virtualdub.org/downloads/Altirra-4.40.zip (SHA-256 8B0BE7D8…2C87; file is not code-signed) | Emulator, debugger, tracing |
| cc65 suite (`ca65`, `ld65`, `cl65`) | V2.19, Git eebf54a snapshot | sourceforge.net/projects/cc65 `cc65-snapshot-win64.zip` (SHA-256 B357E868…0EB1) | 6502 assembler/linker for the byte-exact rebuild (C10) |
| GCC (WinLibs, with LLVM/clang) | 14.2.0 | winget `BrechtSanders.WinLibs.POSIX.UCRT.LLVM` | C compiler for the re-implementation (G21) |
| Python | 3.14 (pre-existing) | – | Scripts, own 6502 disassembler (C8) |

`tools/run_altirra.ps1` starts Altirra in portable mode as an NTSC Atari 800 with the Rev B OS from
`original/` and the Pac-Man cartridge. Not yet run interactively (that is step A5).

Notes: the new WinLibs PATH entries only apply to newly opened terminals. Altirra's built-in
AltirraOS remains available for later cross-checking against the Rev B ROM.

## Unattended runs (added with the nibble-map / patrol / level verification)
- `tools/trace_altirra.ps1` (interactive tracing, you play), `tools/run_patrol_trace.ps1` (unattended: `-Cmd altirra_patrol.cmd` or `-Cmd altirra_levels.cmd`), `tools/boot_crc_check.ps1`, `tools/capture_altirra.ps1`.
- Altirra treats a *quoted* token as a file name, so switches must be unquoted; debugger commands go in a `.batch` file; its expression language has **no accumulator variable** (a bare `a` is the hex number `$A`);
  `r a` from a breakpoint has no effect; debugger arguments are split at spaces; the log file is flushed in 4 KB chunks and fully only on a clean exit.
- Fast unattended runs use a private settings copy, never your normal settings: copy `external-tools\Altirra\Altirra.ini` to `Altirra_fast.ini` in the same folder and set `"Speed: Frame rate modifier" = 800`
  (about 7 to 10 times real time). The command files start the game themselves (self-clearing breakpoint at `$A504` jumping to the start-game code at `$A537`), so no key press or window focus is needed.
- Screenshots of the whole screen can capture other windows (a browser was captured once by accident and deleted); the unattended runs do not use screenshots. The exception is `tools/run_ghost_shots.ps1`, which uses `PrintWindow` on Altirra's own window (it never reads other windows) after stopping the emulator; its captures stay local (game images are not committed).

## Known quirk of the Altirra 4.40 debugger: the first tracepoint hit is printed late (OV-56, C-57)
The first `bt` hit of a session is printed with the state of the **next** tracepoint hit (its registers, memory, `@frame`, `vpos`, `pc`). Shown on the cold start of the game: `bt a3b8` first printed `src=$0000` and `pc=$A481` (the next trace line); with a tracepoint on `Start` (`$A386`) in front, the line for `$A3B8` is `src=$A1E1 dst=$0800` and every later line is exact. All later lines of a log are right (checked by the `pc` and the pointer values at 11 addresses along `Start`). **Rule: every trace harness that reads the first line puts `bt a386 "SENT f=%d pc=$%04X" @frame pc` first** (`tools/run_pointer_audit.ps1`, `tools/run_structure_audit.ps1`); the earlier session logs are not affected unless their analysis depends on their very first line.

## Known quirk of the Altirra 4.40 debugger: a bare `a` in a trace expression is the number 10 (OV-56 / stage 53-56)
In the arguments of `bt` / `bp` the register A must be written `@a`: a bare `a` is parsed as the hexadecimal number 10 (like `b` ... `f`); `x`, `y`, `s`, `p`, `pc` and `@frame` are fine. A trace that prints `a=0A` in every line is this mistake.

## The 6502 interpreter and the executable models (stage 50, OV-58)
`tools/cpu6502.py` runs the ROM instruction by instruction (no timing, no hardware: a read of `$D20A` returns the next value of a list, other hardware addresses are plain memory; a JSR into the OS returns at once). `tools/algorithm_models.py` .. `algorithm_models7.py` hold the models of all 22 algorithms and compare the **whole memory** (zero page, `$0200-$9FFF`, `$D000-$D7FF`) after every call, with the RANDOM reads counted: sets 1-2 the pure routines, 3 the house and the drawing of an entity, 4 Pac-Man, the bonus and the eaten ghost, 5 scores, drawing, the death and the level change, 6 the display-list interrupts and the key loop (the hooks for the interrupt and the user are listed in `run_key_loop`), 7 the ghost state machine, the turn handling and the whole frame. `tools/analyze_model_coverage.py` runs all seven with the interpreter counting every instruction and the outcome of every branch (about 8 minutes; `--cache FILE` keeps the counts). Evidence: `analysis/evidence-algorithms*-summary.txt`, `analysis/evidence-model-coverage-summary.txt`; tests: `tests/test_algorithms*.py` (they also break models on purpose). `tools/check_state_rules.py` (stage 58) runs the same drivers and the OV-58 comparisons with a logger on every store to a state variable, every variable forced to each value of its domain (about 10 minutes), and gives the exact old -> new relation of every writing instruction (`analysis/evidence-state-rules-summary.txt`). Limit: this is the code, not the machine; the timing, the interrupts and the video and sound hardware are covered by the Altirra sessions.

`tools/absint6502.py` is an abstract interpreter of the ROM (followed variables concrete, everything else unknown, both outcomes of every unknown branch, the vertical-blank handler entering between any two instructions of the key loop); `tools/prove_state_rules.py --slice NAME` runs it for one set of followed state variables and `--write analysis/evidence-state-proof-summary.txt` combines the slices (`docs/34` section 5a, `tests/test_absint.py`, `tests/test_states.py`); `tools/absint_diag.py` gives a witness path for a store. A full run of all 11 slices takes about 3.5 hours (the ghost-0 slice 1.9 h, 30 million states, about 9 GB of memory).

## What is kept in git and what stays local (OV-40 / OV-41, 2026-11-14)
Committed: the tools, the tests, the documents, the evidence summaries (`analysis/evidence-*.txt`) and the tiny rendered start tune (`analysis/start-tune.wav`). **Local only (gitignored), regenerable with the harness and the command line named in the register row of each session:** the raw debugger logs (`analysis/raw-logs/`, tens to hundreds of MB each: the traces behind every evidence summary), the emulator screenshots (`analysis/shots/`, game imagery), the audio recordings of Altirra's output (`analysis/*.wav`, about 776 MB in 44 files, derived from the copyrighted ROM; the sessions are deterministic, so the same harness gives the same recording and the same register trace) and the emulator's OS ROM set (`a800.zip`). The tests that read a raw log or a screenshot folder skip themselves when it is absent. Nothing of the original game (`original/`, `*.rom`) and no OS ROM is ever committed.
