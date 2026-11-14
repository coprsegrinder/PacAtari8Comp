# 10 – Byte-Exact Rebuild (Step C10)

Written 2026-11-10. Covers checklist stages 26–28 plus the added stage "byte-exact reassembly check".

## How to rebuild
`python -I tools/build_rom.py` assembles `src/asm/pacman.s` (ca65 V2.19, `--cpu 6502`), links it with
`src/asm/pacman.cfg` (ld65, ROM at $A000, 8,192 bytes) into `build/pacman.rom`, and compares it with
`original/Pac-Man.rom`. Exit code 0 means byte-identical; otherwise it prints the first differing address.
Toolchain location comes from `CC65_BIN` (default `external-tools/cc65/bin`).

## Result (2026-11-10)
- Built: 8,192 bytes, SHA-256 `a99b2dd10b546d90d14de56d73a58a9d38e19ec411e37e33dcbd7e0633d8a56a`.
- Original: same size, same SHA-256. **BYTE-IDENTICAL.**

## Tests (`python -I tests/test_rebuild.py`, 2 tests, pass)
1. Two independent builds in different folders are identical to each other and to the original (reproducible).
2. Negative test: changing one byte in the source (`$4A` -> `$4B` at $A000) makes the check report
   "1 differing bytes, first at address $A000", so the comparison does catch errors.

## Rule from now on
Every later edit to `src/asm/` (labels, comments, data directives, renamed symbols) must keep this check
passing; run `tools/build_rom.py` before each commit that touches `src/asm/`. `build/` is not committed.
