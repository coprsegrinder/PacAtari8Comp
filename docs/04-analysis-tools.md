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

## What is kept in git and what stays local (OV-40 / OV-41, 2026-11-14)
Committed: the tools, the tests, the documents, the evidence summaries (`analysis/evidence-*.txt`) and the tiny rendered start tune (`analysis/start-tune.wav`). **Local only (gitignored), regenerable with the harness and the command line named in the register row of each session:** the raw debugger logs (`analysis/raw-logs/`, tens to hundreds of MB each: the traces behind every evidence summary), the emulator screenshots (`analysis/shots/`, game imagery), the audio recordings of Altirra's output (`analysis/*.wav`, about 776 MB in 44 files, derived from the copyrighted ROM; the sessions are deterministic, so the same harness gives the same recording and the same register trace) and the emulator's OS ROM set (`a800.zip`). The tests that read a raw log or a screenshot folder skip themselves when it is absent. Nothing of the original game (`original/`, `*.rom`) and no OS ROM is ever committed.
