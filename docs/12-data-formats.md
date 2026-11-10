# 12 – Data Formats (Step C11, data labelling)

Written 2026-11-10. Every byte of the ROM that is not code (2,246 bytes) now belongs to a labelled region in
`src/asm/pacman.s`; the map lives in `tools/labels.py` (`DATA`). Rebuild check after the change: byte-identical.
Comments marked **hyp** are hypotheses; everything else is read from the code or checked by a test
(`tests/test_streams.py`, 5 tests). Decoders: `tools/decode_streams.py`
(`--dump` writes the decoded RAM images to `resources/decoded/`, which is not committed).

## The three compressed formats
`Start` expands compressed ROM data into RAM before the game runs. The formats were read from the code:

| Format | Code | Rule |
|---|---|---|
| **Type A** | `$A3BA` (inline in Start) | byte `c`: `c < $80` = literal `c`; `$80–$BF` = repeat the next byte `(c & $3F)+1` times; `$C0–$FE` = three bytes out: `c & $3F`, high nibble and low nibble of the next byte; `$FF` = end |
| **Type B** | `ExpandData` `$A668` | byte `c`: `$FF` = end; otherwise output `PixelPatternTable[c & $3F]` repeated `(c >> 6)+1` times |
| **Nibble split** | `$A40A` | each source byte gives its high nibble then its low nibble (256 bytes in, 512 out) |

Evidence that the decoders are right: the streams end exactly on the next boundary (`$A1E0`, `$A385` = the byte
before `Start`, `$BE74`), and the output sizes are whole structures (below).

## Regions
| ROM range | Label | Content | Evidence |
|---|---|---|---|
| `$A000–$A002` | UnreadHeader_A000 | 3 bytes, purpose unknown | no code reads them |
| `$A003–$A1E0` | CharsetStream | type B → RAM `$3000`, 808 bytes = **101 glyphs** | DliHandler1 sets `CHBASE=$30`; 808 = 101 × 8 |
| `$A1E1–$A385` | MazeMapStream | type A → RAM `$0800`, 920 bytes = **23 × 40** | DisplayList1 has exactly 23 mode-4 rows of 40; Start copies it to `$0C00/$1000/$1400` |
| `$BAC0–$BAF1` | GhostShape0–4 | five ghost frames, 10 rows × 8 px | rendered bitmaps (see listing comments) |
| `$BAF2` | GhostEyesShape | eyes only | bitmap |
| `$BAFC–$BB55` | PacShape* | nine Pac-Man frames (full; open right ×2, left ×2, up ×2, down ×2) | bitmaps; pointer table `PacShapePtrs` at `$BB65` points to the first frame of each direction |
| `$BB56–$BB64` | SmallTable_BB56 | 15 bytes | read by tiny indexes; purpose unknown |
| `$BB65–$BB6E` | PacShapePtrs | 5 words: `$BAFC $BB06 $BB1A $BB2E $BB42` | verified by test |
| `$BB6F–$BB82` | ZeroPageInit80 | 20 bytes → zero page `$80–$93` | copy loop at `$ADE0` |
| `$BB83–$BB96` | SearchList_BB83/BB8D | two ascending 10-value lists | linear `CMP` search loops |
| `$BB97–$BBAA` | RecordPtrs_BB97 | 10 pointers `$060E…$0668` (10 bytes apart) | indexed `2*X` then used as SrcPtr |
| `$BBAB–$BBE1` | ThresholdLists / ProfileList_BBD8 | `$FF`-terminated lists | `CMP #$FF / BEQ` loops |
| `$BBE2–$BBED` | ColorsGame, ColorsTitle | 8 + 4 colour bytes → `PCOLR0..COLOR3` / `COLOR0..3` | `LoadShadowColors`, `InitDisplay2` |
| `$BBEE–$BBF1` | ColorsDli | 4 colours for the DLIs, masked by `COLRSH`/`DRKMSK` | code at `$A4BC` |
| `$BBF2–$BBF7` | Window3Table | overlapping 3-byte windows | copy of 3 bytes at offset 0–3 |
| `$BBF8–$BC06` | ByteTable_BBF8 | 15 entries by level index | result to `zp_FD` |
| `$BC07–$BC4F` | StarShape, PopupZeros, PopupDigits200/400/800/1600 | 12-row shapes copied as 16 rows (4 pad bytes from the next table) | bitmaps; pointer table `PopupPtrs` indexed by `zp_E9` (**hyp**: ghost-eaten 200/400/800/1600) |
| `$BC50–$BCCF` | TuneAudf1, TuneAudf2 | 2 × 64 sound values → `AUDF1`/`AUDF2`, one step per 4 jiffies | `$A7DF`; index stops at `$40` (**hyp**: start-up tune) |
| `$BCD0–$BCD7` | PopupPtrs | `$BC1F $BC2B $BC37 $BC43` | `2*zp_E9` indexing |
| `$BCD8–$BCE5` | AudfSweepDown/Up | two 7-byte pitch sweeps, 0-terminated | chosen by `zp_F6` |
| `$BCE6–$BCED` | RecordPtrs_BCE6 | 4 pointers into `$0686…$06A3` | indexed `2*X` |
| `$BCEE–$BD0D` | RandomPositions | 16 (x, y) pairs | indexed by `RANDOM AND $0F` |
| `$BD0E–$BD15` | CornerPositions | (`$BE,$2C`) (`$3A,$2C`) (`$BE,$C4`) (`$3A,$C4`): the four corners | indexed by ghost number; same stores as RandomPositions |
| `$BD16–$BD25` | RowOffsets | 16 offsets | added to a column to index `$06AE,Y` |
| `$BD26–$BD44` | CharCodeProfile | 31 codes up and down | written to `$0F92…` as code and code+1 |
| `$BD45–$BD79` | LevelGlyphRecords, LevelRecordOffsets | 8 records × 5 codes, 13 offsets | indexed by level (`zp_30`, clamped to 12) |
| `$BD7A–$BDB8` | PixelPatternTable | 63 pattern bytes | used by type B; index 63 never occurs (test) |
| `$BDB9–$BDC6` | LevelIndexTable1/2 | 7 + 7 entries | level clamped to 6 |
| `$BDC7–$BDD0` | TextHighScore | "HIGH SCORE" (10) | copy loop X=9..0 → `$200F`; shown on screen |
| `$BDD1–$BDD5` | DliChbaseTable | `$18 $E0 $30 $E0 $30` | `CHBASE` per DLI in DliHandler2 (**correction**: an earlier note had read this as text) |
| `$BDD6–$BDF6` | TextChangeDifficulty, TextPressStartTo | "CHANGE DIFFICULTY" (17), "PRESS [start] TO " (16) | fixed-length copy loops to `$1D05`, `$1D56` |
| `$BDF7–$BE04` | TextCopyright | 14 custom-glyph codes, reads like "(c) atari 1982" | **hyp** |
| `$BE05–$BE12` | TitleAnimCodes | 14 codes written as N and N+1 | `$A764` loop (**hyp**) |
| `$BE13–$BE74` | TitleCharsetStream | type B → RAM `$1808`, 160 bytes = 20 glyphs | DliHandler2 sets `CHBASE=$18` |
| `$BE75–$BE94` | TitleCharsetTail | 32 bytes → `$18A8–$18C7` | copy loop at `$A443` |
| `$BE95–$BF80` | NibbleMapSource | 236 meaningful bytes → nibbles at RAM `$0600–$07FF` | Start copies **256** bytes; the extra 20 are the start of DisplayList2 (harmless junk in RAM) |
| `$BF81–$BFC5` | DisplayList2, DisplayList1 | ANTIC display lists | decoded; JVB targets point to themselves |
| `$BFC6–$BFF9` | TextPlayerGame, TextPressSelectFor, TextPressOptionTo, TextPlayGame | title-screen lines of 11, 16, 16, 9 bytes | fixed-length copy loops, lengths from the loop counts |
| `$BFFA–$BFFF` | cartridge header | RUN, flags, INIT | standard layout |

## Findings worth knowing
- The "text" on the title screen is not zero-terminated: `$00` is the **space** character, and every line has a fixed length given by the
  loop that copies it. The lines are drawn in the title charset, so some codes (`$C8 $E3 $C9`, `$D1…`) are custom glyphs.
- The maze is stored as a 23 × 40 character map in a run-length format and held in RAM three or four times (`$0800`, `$0C00`, `$1000`, `$1400`).
- Nothing in the ROM is a "maze graph" in plain form; the grid at RAM `$06AE…` is built from the nibble stream (**hyp**: movement data).

## Still unknown
Purpose of `UnreadHeader_A000`, `SmallTable_BB56`, the three `ByteTable`/`ThresholdLists`/`SearchList` families (what they index, in
game terms), and the meaning of each ghost frame. These need tracing in Stage D/E.
