# 02 – Repository Layout and Version Control

Written in Step A2 (2026-11-10). Covers checklist stage 9 (workspace preparation).

## Folders

| Folder | Purpose | In Git? |
|---|---|---|
| `original/` | Owner-supplied originals: `Pac-Man.rom` (read-only), `Decompilation steps.txt`, saved forum page used as evidence | NO (copyrighted/third-party) |
| `docs/` | All documentation and the progress tracker | yes |
| `analysis/` | Disassembly listings, memory maps, traces, working notes | yes |
| `src/asm/` | Reconstructed annotated 6502 source (must rebuild the ROM byte-for-byte) | see note 1 |
| `src/c/` | C re-implementation and later the Windows layer | yes |
| `tools/` | Scripts and helper programs | yes |
| `tests/` | Verification tests and records | yes |
| `resources/` | Extracted graphics/sound/text | NO (derived from ROM) |
| `build/` | Build output | NO |

Layout change in this step: the ROM, the methodology text and the saved forum page were moved from
the project root into `original/` (same volume, so timestamps are preserved). The ROM's SHA-1 was
re-checked after the move: BC600EF63F8D1BDD3911981C2752EA23DB959960 (unchanged).

## What must never be committed
The original ROM, any Atari OS/BASIC ROM images, other ROM/disk/cartridge formats, extracted
resources and build output. `.gitignore` enforces this. Anyone rebuilding must supply their own ROM
in `original/Pac-Man.rom` (expected SHA-1 above).

## Notes / decisions pending for the owner
1. **Reconstructed assembly (`src/asm/`).** A full disassembly of the ROM is a derivative of
   copyrighted code. It is currently NOT ignored, so it would be committed to the (local, and later
   private) repository. The owner should decide before any push whether the repository may contain it.
   **Owner decision (2026-11-10): the repository stays private.** Never make it public without a new review and explicit owner approval.
2. **Git identity.** The repository uses a generic local identity ("Pac-Man Preservation Project",
   noreply@localhost) so the owner's personal name/email do not enter the project history. It can
   be changed on request.
3. Nothing has been pushed anywhere; there is no remote.

## Commit conventions
Small commits after each verified step; message states the step ID (e.g. "A2: ...").
