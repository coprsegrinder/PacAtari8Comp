# 03 – File Inventory, Integrity and Dependencies

Written in Step A3 (2026-11-10). Covers checklist stages 6, 7 and 8.

## 1. Inventory (stage 6)

| File | Format | Size (bytes) | Location (local only) |
|---|---|---|---|
| `Pac-Man.rom` | Raw Atari 8-bit cartridge image, no header | 8,192 | `original/` (+ backup, see §4) |
| `Atari OS Rev B (19xx)(Atari)(NTSC)[400-800].rom` | Raw OS ROM image, Atari 400/800 Rev B, NTSC (added 2026-11-10, owner-supplied) | 10,240 | `original/` |
| `Decompilation steps.txt` | Plain text, 100-stage methodology | 16,051 | `original/` |
| `reference-AtariAge-thread-291065.htm` (+ `_files/`, 49 files, 1,926,115 bytes) | Saved web page (evidence for ROM identity) | 225,063 | `original/` |

## 2. Checksums (stage 7)

| File | SHA-256 | SHA-1 | MD5 | CRC-32 |
|---|---|---|---|---|
| Pac-Man.rom | a99b2dd10b546d90d14de56d73a58a9d38e19ec411e37e33dcbd7e0633d8a56a | bc600ef63f8d1bdd3911981c2752ea23db959960 | e66e9af9af01b019cd4e54aba813fbac | 61CF6167 |
| Atari OS Rev B ROM | 63973d5e86b1ae5b6fca5b119a7f7589e817e19acc3ca54e54462c9dfb619e73 | db1031585968cfc6ec2ecda5c9a5a52f61444a3b | 4177f386a3bac989a981d3fe3388cb6c | 0E86D61D |
| Decompilation steps.txt | 1afa7d69b5463a2379aeb1197dc66e918346a7b56a22a2fc6f09c421bfae2090 | 7053b0c33aca8bc3dfad2e06b98f6d2a140ee78c | 461d30bd2b67e5d9c4207d44534afd84 | F79F37E4 |
| reference-AtariAge-thread-291065.htm | 3130f4de3c5108d2911b7eb0587ada55737219df840b0b0713881ab8f3741ddc | 5787af48ea675cb80a5f174c6834569e13ebcaa5 | be7726a57378ac0edb72b4e4cbd5a4a8 | 566A5944 |

The machine-readable manifest is `docs/original-manifest.txt`; check it any time with
`python -I tools/verify_originals.py` (read-only; prints OK/MISMATCH per file).

**What "verified" means here.** The checksums prove that the files have not changed *since
inspection*. They do NOT prove the ROM is an unaltered retail dump: no published checksum for
Pac-Man could be found to compare against (assumption A1, see `01-scope-and-methodology.md`).

**The PAL OS ROM (decision of 2026-11-23).** `original/Atari OS Rev B (19xx)(Atari)(PAL)[a800.zip MAME].rom` has been in this folder since the PAL sound verification (2026-11-13, register C-24 to C-26), the one run that needed a PAL machine in the emulator. By the owner's decision of 2026-11-23 **the project uses only the NTSC OS ROM**: the PAL file is not a project material, is not in the manifest and is not checked; the evidence it produced stays in `analysis/`. It may be deleted from the folder.

## 3. Duplicates and dependencies (stage 8)

- **Duplicates:** none. The ROM's two 4 KB halves are different, so it is not a doubled 4 KB image
  (consistent with the two-chip retail cartridge).
- **Other versions in the project:** none supplied.
- **External dependencies of the game (to be mapped in Stage B):** the Atari OS ROM (a replacement
  OS such as the one built into the Altirra emulator is expected to suffice), plus the ANTIC, GTIA,
  POKEY and PIA hardware.
- **Dependencies of the project tooling:** none yet (Python 3.14 and Git are installed; assembler,
  emulator and C compiler come in step A4).

## 4. Protection of the original ROM

- `original/Pac-Man.rom` is set read-only in Windows (modified date preserved: 2000-09-02 17:47:44).
- A second read-only copy is at `F:\Ports\Pac-Man-Atari8-ROM-backup\Pac-Man.rom` (outside the project
  folder, identical SHA-256). Note: it is on the same drive (F:), so it protects against accidental
  edits/deletes in the project, not against drive failure. The owner may want to copy it to another
  drive or cloud storage.
- Both are excluded from Git.
