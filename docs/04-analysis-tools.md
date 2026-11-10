# 04 – Analysis Tools

Written in Step A4 (2026-11-10). Covers checklist stage 10. Tools live OUTSIDE the repository in
`F:\Ports\Pac-Man-tools\` (not committed); downloads are kept in `downloads\` for re-checking.

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
