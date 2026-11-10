# 07 – Vectors and Entry Points

Written in Step B7 (2026-11-10). Covers checklist stages 19–20 (entry points, vectors). Produced by
`tools/scan_vectors.py` (read-only) from the supplied ROMs; output in `analysis/b-vectors-and-hw-scan.txt`.

## Cartridge header (Pac-Man ROM, $BFFA–$BFFF) [ROM]
| Address | Bytes | Meaning |
|---|---|---|
| $BFFA–$BFFB | `86 A3` | RUN vector = **$A386** (start of the game, jumped to after OS init) |
| $BFFC | `00` | Cartridge-present byte (0 = cartridge present) |
| $BFFD | `04` | Option byte: bit 2 set = cartridge is run (not just a data cart); bit 0 clear = no disk boot |
| $BFFE–$BFFF | `B4 A6` | INIT vector = **$A6B4** (called by the OS during start-up, before RUN) |

Entry-point reading above follows the standard Atari cartridge header layout (from memory, to be
cross-checked).

**Correction (step C9, 2026-11-10):** the first version of this document said INIT ($A6B4) sets the
display list and VDSLST. That was wrong; it came from the heuristic byte scan. The disassembly shows that
`$A6B4` is a single `RTS` (INIT does nothing). The display-list/VDSLST code is a separate routine that
starts at `$A6B5` (named `SetDisplayList`), called from `$A49B` and `$A621`.

## Rev B OS vectors [ROM, OS file maps $D800–$FFFF]
| Vector | Address | Points to |
|---|---|---|
| NMI | $FFFA | $E791 |
| RESET | $FFFC | $F125 |
| IRQ | $FFFE | $E6F3 |

OS jump table ($E450–$E47F, each entry `JMP`): DISKIV $EDEA, DSKINV $EDF0, **CIOV $E4C4**, **SIOV $E959**,
**SETVBV $E8ED**, SYSVBV $E7AE, **XITVBV $E905**, SIOINV $E944, SENDEV $EBF2, INTINV $E6D5, CIOINV $E4A6,
BLKBDV $F223, WARMSV $F11B, COLDSV $F125 (same target as RESET), RBLOKV $EFE9, CSOPIV $EF5D.
(Names and order follow the standard OS vector table; the targets above were read from the ROM.)

## OS calls made by the game (heuristic scan)
- `JSR $E45C` (SETVBV) at $A460, probably to install the vertical-blank handler.
- `JMP $E462` (XITVBV) at $A60D, the normal end of a deferred VBI handler.
- No CIOV/SIOV calls seen: the game does not appear to use the OS I/O system in the scanned code.

## Start-up sequence (expected, to be verified by tracing in Stage E)
Power-on → RESET ($F125) → OS initialises hardware, detects cartridge → INIT ($A6B4) → RUN ($A386).
