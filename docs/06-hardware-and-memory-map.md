# 06 – Hardware and Memory Map

Written in Step B6 (2026-11-10). Covers checklist stages 11–16 (hardware, memory map, I/O).

**Sources and confidence.** The platform description below is standard Atari 400/800 knowledge
written from memory; it has NOT yet been cross-checked against a published hardware manual (to do
before B is approved for use in C/D). Items marked [ROM] were read directly from the supplied files.

## Target machine
Atari 400/800 (NTSC), 6502 CPU, 48K RAM, Rev B OS [ROM `original/Atari OS Rev B…rom`, 10,240 bytes, maps $D800–$FFFF].
Custom chips: ANTIC (display list DMA), GTIA (colour, players/missiles, collisions, console keys),
POKEY (sound, keyboard, random, serial, timers), PIA (joystick ports, serial control).

## Memory map (CPU view)
| Range | Contents |
|---|---|
| $0000–$00FF | Zero page: OS variables, then free for the game |
| $0100–$01FF | 6502 hardware stack |
| $0200–$02FF | OS page 2: interrupt vectors (e.g. VDSLST $0200, VVBLKI $0222, VVBLKD $0224), shadow registers |
| $0300–$03FF | OS: device/IOCB/SIO tables |
| $0400–$BFFF | RAM (to $9FFF with 40K; with cartridge in the left slot, $A000–$BFFF is cartridge ROM) |
| $A000–$BFFF | Left cartridge slot: **Pac-Man ROM, 8,192 bytes** [ROM] |
| $C000–$CFFF | Unused on 400/800 (OS ROM begins at $D800) |
| $D000–$D0FF | GTIA registers |
| $D200–$D2FF | POKEY registers |
| $D300–$D3FF | PIA registers |
| $D400–$D4FF | ANTIC registers |
| $D800–$FFFF | OS ROM (floating-point package from $D800, then OS code and tables) [ROM] |

## Cartridge facts [ROM]
- The ROM image is exactly 8,192 bytes, so one file = $A000–$BFFF; the two 4 KB halves differ.
- Cartridge header at $BFFA–$BFFF: see `07-vectors-and-entry-points.md`.
- Only 47 bytes are $FF and 439 are $00, so the ROM is not mostly empty padding.
- Text strings appear to use Atari internal screen codes (ASCII minus $20; inverse video = +$80),
  e.g. "PRESS" = `30 32 25 33 33`. To be confirmed during data labelling (C11).

## Hardware registers the ROM touches (heuristic, see below)
From `analysis/b-vectors-and-hw-scan.txt` (absolute-address instructions only; false positives and
indexed accesses not seen are possible, so this is an indication, not a list):
- **ANTIC:** $D402/$D403 (display-list pointer), $D407 (PMBASE), $D409 (CHBASE), $D40A (WSYNC, 6 sites), $D40E (NMIEN).
- **GTIA:** $D004–$D007 writes (missile horizontal positions), $D016–$D019 (colour registers),
  $D01D (GRACTL), $D01E (HITCLR), $D01F (CONSOL read for START/SELECT/OPTION),
  collision register reads ($D002, $D009, $D00A).
- **POKEY:** $D200–$D208 writes (audio channels and control; $D200–$D203 most used), $D20A (RANDOM reads),
  $D20E (IRQEN), $D20F (SKCTL).
- **PIA / joystick:** not seen in this scan; the game probably reads joysticks through OS shadow
  locations (STICK0 etc. in page 0/2). To be determined in C8/D.
- Suspect false positives: `JMP $D020` (A664) and `LDX $D0C8` (AE18); they are not hardware registers
  on these chips and are probably data bytes decoded as code.

## Open items
1. Cross-check register meanings (note read vs write meaning of $D000–$D01F) against a manual.
2. Resolve false positives and indexed accesses after the disassembly (C8).
3. Page-2 vectors and shadow registers used by the game: deferred to disassembly.
