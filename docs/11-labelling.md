# 11 – Labelling and Naming (Step C11, first pass)

Written 2026-11-10. Covers checklist stages 29–30 as far as evidence allows. This is a **first pass**:
the rest of the naming belongs to the analysis stages (D), where behaviour is traced and understood.
Every change in this step was checked with `tools/build_rom.py` (**byte-identical** after each regeneration).

## How the listing is produced now
`tools/make_asm.py` (entry points, structures) + `tools/labels.py` (names) regenerate `src/asm/pacman.s`;
never hand-edit that file. Names are cosmetic and cannot change the bytes.

## What was added to `src/asm/pacman.s`
| Item | Count | Evidence / rule |
|---|---|---|
| Hardware register names (GTIA, POKEY, ANTIC) | 50 used | Standard 400/800 register names; stores use the write name, other accesses the read name (e.g. `$D000` store = `HPOSP0`, load = `M0PF`) |
| OS variables (shadow registers, `VDSLST`, `SDLSTL`, `STICK0`, `CH` ...) | 13 | Standard names at standard addresses, used in the standard way |
| OS zero page: `POKMSK` $10, `RTCLOK2` $14, `ATRACT` $4D, `DRKMSK` $4E, `COLRSH` $4F | 5 | Standard names; `$14` is waited on for a tick, `$10` is ORed then stored to `IRQEN`; $4D–$4F appear together |
| Game zero page: `SrcPtrL/H` $3C/$3D, `DstPtrL/H` $3E/$3F | 4 | Used as `(zp),Y` read/write pointers by the copy/expand helpers and by `Start` |
| Other zero page | rest | generic `zp_xx` (meaning not yet established) |
| Subroutines (JSR targets) | 66 | `Sub_xxxx` for the 53 still unnamed; the other 13 have real names (below) |
| Data labels | 43 | `D_xxxx` at every ROM address the code reads as data |
| Display lists | 2 | Decoded ANTIC instructions with comments; `DisplayList1` ($BFA3, 29 instructions, jumps to itself), `DisplayList2` ($BF81, 26 instructions) |
| Text | 3 runs | Atari screen codes decoded in comments; strings seen on the title screen: HIGH SCORE, CHANGE DIFFICULTY, PRESS, PLAYER, GAME, [select], [option], TO, PLAY |
| Cartridge header | 4 lines | `.word Start`, present byte, option byte, `.word Init` |

## Named routines and the reason for each name
| Address | Name | Evidence |
|---|---|---|
| $A386 | Start | cartridge RUN vector |
| $A6B4 | Init | cartridge INIT vector; a single `RTS` |
| $A5FD | VbiHandler | installed with SETVBV (A=7); ends with `JMP XITVBV` |
| $A573 / $A5CE | DliHandler1 / 2 | installed into VDSLST by SetDisplayList at $A49B / $A621; both end with `RTI` |
| $A6B5 | SetDisplayList | writes SDLSTL/H, DLISTL/H and VDSLST from X, Y and constant $BF/$A5 |
| $A610 | InitDisplay2 | clears HPOSP0–7 and AUDF1–AUDC4 area, installs `DisplayList2` + `DliHandler2`, loads four colours |
| $A668 | ExpandData | reads a stream via SrcPtr and writes via DstPtr (decompressor; **working name**) |
| $A69C / $A69E | ReadSrcByte / AdvanceSrcPtr | `LDA (SrcPtr),Y` falling into a 16-bit pointer increment |
| $A6A5 | WriteDstByte | `STA (DstPtr),Y` then 16-bit increment of DstPtr |
| $A6AE | ReadSrcHighNibble | `LDA (SrcPtr),Y` then four `LSR` |
| $B0E6 | ClearPokeyRegisters | stores 0 to $D200–$D207 |
| $B113 | LoadShadowColors | copies 8 bytes from `D_BBE2` into $02C0–$02C7 |
| $B11F / $B13D / $B15B | Copy0800To0C00 / Copy0C00To1000 / Copy0C00To1400 | each copies four 256-byte pages between fixed RAM blocks |

`Start` shows the game expands compressed ROM data into RAM at start-up: it copies 10 bytes ("HIGH SCORE")
to $200F, clears zero page, and decodes streams from `$A1E1` into $0800.. and from `$BE95` into $0600..
through `ExpandData`. So much of the "data" in ROM is compressed source for RAM tables (stage D will decode it).

## Not done yet (and why)
- The 53 unnamed subroutines and all zero-page game variables: meaning not yet established; names need
  traced behaviour (Stage D/E). `analysis/routine-catalog.txt` lists each with size, call count, hardware touched
  and callees, to prioritise. Sizes in it are approximate (nearest preceding label).
- Data: **now fully labelled** (every non-code byte); see `12-data-formats.md` for formats, evidence and what is still unknown.
- Screen codes `$00–$3F` = ASCII $20–$5F (verified on the title screen); codes with bit 7 are inverse video.
