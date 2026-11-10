"""Step C11: symbol tables for the Pac-Man disassembly.

Every name here must be backed by evidence: either a standard Atari 400/800 equate (hardware
register or OS variable, used the standard way) or something shown in the code. Confidence is
recorded in docs/11-labelling.md. Names are cosmetic: the rebuild check (tools/build_rom.py)
proves they do not change a single byte.
"""

# ---- Hardware registers: name by (address, is_write) -------------------------------------
GTIA_W = {0xD000: "HPOSP0", 0xD001: "HPOSP1", 0xD002: "HPOSP2", 0xD003: "HPOSP3",
          0xD004: "HPOSM0", 0xD005: "HPOSM1", 0xD006: "HPOSM2", 0xD007: "HPOSM3",
          0xD008: "SIZEP0", 0xD009: "SIZEP1", 0xD00A: "SIZEP2", 0xD00B: "SIZEP3", 0xD00C: "SIZEM",
          0xD00D: "GRAFP0", 0xD00E: "GRAFP1", 0xD00F: "GRAFP2", 0xD010: "GRAFP3", 0xD011: "GRAFM",
          0xD012: "COLPM0", 0xD013: "COLPM1", 0xD014: "COLPM2", 0xD015: "COLPM3",
          0xD016: "COLPF0", 0xD017: "COLPF1", 0xD018: "COLPF2", 0xD019: "COLPF3", 0xD01A: "COLBK",
          0xD01B: "PRIOR", 0xD01C: "VDELAY", 0xD01D: "GRACTL", 0xD01E: "HITCLR", 0xD01F: "CONSPK"}
GTIA_R = {0xD000: "M0PF", 0xD001: "M1PF", 0xD002: "M2PF", 0xD003: "M3PF",
          0xD004: "P0PF", 0xD005: "P1PF", 0xD006: "P2PF", 0xD007: "P3PF",
          0xD008: "M0PL", 0xD009: "M1PL", 0xD00A: "M2PL", 0xD00B: "M3PL",
          0xD00C: "P0PL", 0xD00D: "P1PL", 0xD00E: "P2PL", 0xD00F: "P3PL",
          0xD010: "TRIG0", 0xD011: "TRIG1", 0xD012: "TRIG2", 0xD013: "TRIG3", 0xD014: "PAL",
          0xD01F: "CONSOL"}
POKEY_W = {0xD200: "AUDF1", 0xD201: "AUDC1", 0xD202: "AUDF2", 0xD203: "AUDC2",
           0xD204: "AUDF3", 0xD205: "AUDC3", 0xD206: "AUDF4", 0xD207: "AUDC4", 0xD208: "AUDCTL",
           0xD209: "STIMER", 0xD20A: "SKREST", 0xD20B: "POTGO", 0xD20D: "SEROUT",
           0xD20E: "IRQEN", 0xD20F: "SKCTL"}
POKEY_R = {0xD200: "POT0", 0xD201: "POT1", 0xD202: "POT2", 0xD203: "POT3", 0xD204: "POT4",
           0xD205: "POT5", 0xD206: "POT6", 0xD207: "POT7", 0xD208: "ALLPOT", 0xD209: "KBCODE",
           0xD20A: "RANDOM", 0xD20D: "SERIN", 0xD20E: "IRQST", 0xD20F: "SKSTAT"}
ANTIC_W = {0xD400: "DMACTL", 0xD401: "CHACTL", 0xD402: "DLISTL", 0xD403: "DLISTH", 0xD404: "HSCROL",
           0xD405: "VSCROL", 0xD407: "PMBASE", 0xD409: "CHBASE", 0xD40A: "WSYNC",
           0xD40E: "NMIEN", 0xD40F: "NMIRES"}
ANTIC_R = {0xD40B: "VCOUNT", 0xD40C: "PENH", 0xD40D: "PENV", 0xD40F: "NMIST"}

STORES = ("sta", "stx", "sty")

# ---- OS shadow registers and variables (standard 400/800 equates) ------------------------
OS_ABS = {0x0200: "VDSLST", 0x022F: "SDMCTL", 0x0230: "SDLSTL", 0x0231: "SDLSTH",
          0x026F: "GPRIOR", 0x0278: "STICK0", 0x0284: "STRIG0", 0x0285: "STRIG1",
          0x02C0: "PCOLR0", 0x02C4: "COLOR0", 0x02C5: "COLOR1", 0x02C7: "COLOR3",
          0x02FC: "CH"}
OS_ZP = {0x10: "POKMSK", 0x14: "RTCLOK2", 0x4D: "ATRACT", 0x4E: "DRKMSK", 0x4F: "COLRSH"}
OS_ENTRY = {0xE456: "CIOV", 0xE459: "SIOV", 0xE45C: "SETVBV", 0xE45F: "SYSVBV", 0xE462: "XITVBV"}


def hw_name(addr, mnem):
    """Name for an absolute operand, or None (stores use the write name, everything else the read name)."""
    if addr in OS_ABS:
        return OS_ABS[addr]
    chip = {0xD0: (GTIA_W, GTIA_R), 0xD2: (POKEY_W, POKEY_R), 0xD4: (ANTIC_W, ANTIC_R)}.get(addr >> 8)
    if chip is None:
        return None
    write, read = chip
    first, second = (write, read) if mnem in STORES else (read, write)
    return first.get(addr) or second.get(addr)


# Game zero-page variables named so far (evidence: used as (zp),y pointers by the helpers and by Start).
GAME_ZP = {0x1B: "StartLevel", 0x30: "Level", 0x3C: "SrcPtrL", 0x3D: "SrcPtrH", 0x3E: "DstPtrL", 0x3F: "DstPtrH",
           # Sub_B423 adds these six BCD digits to the score; zp_E9 and zp_2B proven in docs/12-data-formats.md
           0x94: "ScoreAdd100000", 0x95: "ScoreAdd10000", 0x96: "ScoreAdd1000",
           0x97: "ScoreAdd100", 0x98: "ScoreAdd10", 0x99: "ScoreAdd1",
           0xE9: "GhostsEaten", 0x2B: "CurrentPlayer",
           # Pac-Man movement / animation (docs/12-data-formats.md, section on SmallTable_BB56)
           0x89: "PacY", 0x8E: "PacX", 0x93: "PacDirection", 0xAB: "ChompPhase",
           0xED: "DeathState", 0xEA: "DeathAnimActive", 0xEB: "DeathAnimFrame", 0xEC: "DeathAnimDelay"}


def zp_name(addr):
    return OS_ZP.get(addr) or GAME_ZP.get(addr) or "zp_%02X" % addr


# ---- Game symbols (address -> name). Evidence in docs/11-labelling.md ---------------------
ROM_NAMES = {
    0xA386: "Start", 0xA6B4: "Init", 0xA5FD: "VbiHandler", 0xA573: "DliHandler1",
    0xA5CE: "DliHandler2", 0xA6B5: "SetDisplayList",
    0xBF81: "DisplayList2", 0xBFA3: "DisplayList1",
    # Small routines whose whole job is visible in a few instructions:
    0xA610: "InitDisplay2",        # clears HPOSP0-3.. and AUDF1.. (8 bytes each), installs DisplayList2 + DliHandler2, loads 4 colours
    0xA668: "ExpandData",          # reads a byte stream via SrcPtr, writes via DstPtr (decompressor; working name)
    0xA69C: "ReadSrcByte",         # LDA (SrcPtr),Y then falls into AdvanceSrcPtr
    0xA69E: "AdvanceSrcPtr",       # 16-bit increment of SrcPtr
    0xA6A5: "WriteDstByte",        # STA (DstPtr),Y then 16-bit increment of DstPtr
    0xA6AE: "ReadSrcHighNibble",   # LDA (SrcPtr),Y; shift right four times
    0xB0E6: "ClearPokeyRegisters", # stores 0 to $D200-$D207
    0xB113: "LoadShadowColors",    # copies 8 bytes from D_BBE2 to PCOLR0..COLOR3 ($02C0-$02C7)
    0xB11F: "Copy0800To0C00",      # copies four pages $0800-$0BFF to $0C00-$0FFF
    0xB13D: "Copy0C00To1000",      # copies four pages $0C00-$0FFF to $1000-$13FF
    0xB15B: "Copy0C00To1400",      # copies four pages $0C00-$0FFF to $1400-$17FF
    0xBB55: "PacMouthOffsets",     # 3 entries 00,0A,00 read at $B2DC (chomp cycle)
    0xAE3D: "DeathSequence",       # state machine on DeathState (zp_ED), run while it is non-zero
    0xAEF7: "DeathAnimation",      # plots Pac-Man's death frames while DeathAnimActive (zp_EA) is non-zero
    0xB179: "MovePacMan",          # reads STICK0, moves PacX/PacY, picks and draws the Pac-Man shape
    0xB423: "AddToScore",          # decimal-mode add of ScoreAdd digits to the score at $202A-$202F (player 1) / $2047-$204C (player 2)
    0xA886: "GhostEaten",          # frightened ghost touched: pop-up, score 200/400/800/1600
    0xB3DE: "PowerPelletEaten",    # adds 50, sets GhostsEaten=$FF, frightens the ghosts
}


# ---- Data map (step C11, data formats) --------------------------------------------------------
# (first, last, kind, name, comment).  kinds: stream | bytes | shape | words | text.
# Evidence for every row is in docs/12-data-formats.md; "hyp" in a comment marks a hypothesis.
DATA = [
    (0xA000, 0xA002, "bytes", "UnreadHeader_A000", "3 bytes before the first stream; no code reads them (purpose unknown)"),
    (0xA003, 0xA1E0, "stream", "CharsetStream",
     "type B stream (table-driven RLE, see ExpandData) -> RAM $3000, 808 bytes = 101 glyphs; CHBASE=$30 in DliHandler1"),
    (0xA1E1, 0xA385, "stream", "MazeMapStream",
     "type A stream (inline RLE in Start) -> RAM $0800, 920 bytes = 23 rows x 40 columns, the mode-4 rows of DisplayList1; copied to $0C00/$1000/$1400"),
    # sprite shapes: 10 rows of 8 pixels (player/missile graphics)
    (0xBAC0, 0xBAC9, "shape", "GhostShape0", None), (0xBACA, 0xBAD3, "shape", "GhostShape1", None),
    (0xBAD4, 0xBADD, "shape", "GhostShape2", None), (0xBADE, 0xBAE7, "shape", "GhostShape3", None),
    (0xBAE8, 0xBAF1, "shape", "GhostShape4", None), (0xBAF2, 0xBAFB, "shape", "GhostEyesShape", None),
    (0xBAFC, 0xBB05, "shape", "PacShapeFull", None), (0xBB06, 0xBB0F, "shape", "PacShapeRight1", None),
    (0xBB10, 0xBB19, "shape", "PacShapeRight2", None), (0xBB1A, 0xBB23, "shape", "PacShapeLeft1", None),
    (0xBB24, 0xBB2D, "shape", "PacShapeLeft2", None), (0xBB2E, 0xBB37, "shape", "PacShapeUp1", None),
    (0xBB38, 0xBB41, "shape", "PacShapeUp2", None), (0xBB42, 0xBB4B, "shape", "PacShapeDown1", None),
    (0xBB4C, 0xBB55, "shape", "PacShapeDown2", "last byte ($BB55) is also read as the first entry of SmallTable_BB55"),
    (0xBB56, 0xBB56, "bytes", "PacMouthFrame2Offset",
     "$0A = 10 bytes: offset from a direction's first Pac-Man frame to its second. Middle entry of PacMouthOffsets ($BB55-$BB57 = 00,0A,00); the outer two entries are shared bytes (last row of PacShapeDown2, first byte of DeathPlotBytes)"),
    (0xBB57, 0xBB64, "bytes", "DeathPlotBytes",
     "14 bytes, one plotted per step of the death animation (DeathAnimation $AF26): row = nibble map $0600+X minus 1, in missile memory at Pac-Man's Y"),
    (0xBB65, 0xBB6E, "words", "PacShapePtrs", "pointers to the first frame of each Pac-Man direction (full, right, left, up, down)"),
    (0xBB6F, 0xBB82, "bytes", "ZeroPageInit80", "20 bytes copied to zero page $80-$93 (X=$13..0) by the routine at $ADE0"),
    (0xBB83, 0xBB8C, "bytes", "SearchList_BB83", "10 ascending values searched linearly with CMP (X=9..0)"),
    (0xBB8D, 0xBB96, "bytes", "SearchList_BB8D", "10 ascending values searched linearly with CMP (Y=9..0)"),
    (0xBB97, 0xBBAA, "words", "RecordPtrs_BB97", "10 pointers into RAM $060E-$0668, 10 bytes apart (indexed by 2*X)"),
    (0xBBAB, 0xBBD7, "bytes", "ThresholdLists",
     "lists of ascending values ended by $FF; read with CMP and BEQ on $FF (D_BBB8,Y); start offsets are chosen by the caller"),
    (0xBBD8, 0xBBE1, "bytes", "ProfileList_BBD8", "10 values rising to $11 and falling back to 0; read with CMP/BEQ $FF test (D_BBD8,Y)"),
    (0xBBE2, 0xBBE9, "bytes", "ColorsGame", "8 colours: PCOLR0-3 then COLOR0-3 (LoadShadowColors); $BBE2-$BBE5 also reloaded alone at $AF7D"),
    (0xBBEA, 0xBBED, "bytes", "ColorsTitle", "4 colours loaded into COLOR0-3 by InitDisplay2"),
    (0xBBEE, 0xBBF1, "bytes", "ColorsDli", "4 colours; EORed with COLRSH, ANDed with DRKMSK (attract mode), stored to zp_5E-zp_61 for the DLIs"),
    (0xBBF2, 0xBBF7, "bytes", "Window3Table", "read as 3-byte windows at offsets 0-3 into zp_CB-zp_CD (90 60 30 / 60 30 04 / 30 04 00 / 04 00 00)"),
    (0xBBF8, 0xBC06, "bytes", "ByteTable_BBF8", "15 entries indexed by a level-dependent value; result goes to zp_FD"),
    (0xBC07, 0xBC12, "shape", "StarShape", "12 rows; drawn as the last (15th) frame of the death animation (AF3A); the routine copies 16 rows, so 4 zero bytes of the next table are read as padding"),
    (0xBC13, 0xBC1E, "shape", "GhostScoreZeros", "the two '0' digits shared by all four ghost-eaten pop-ups; drawn by the eaten ghost's player"),
    (0xBC1F, 0xBC2A, "shape", "GhostScore200Digits", "pop-up '200': the '2' (drawn with the four missiles), index 0 of GhostScorePtrs"),
    (0xBC2B, 0xBC36, "shape", "GhostScore400Digits", "pop-up '400': the '4', index 1"),
    (0xBC37, 0xBC42, "shape", "GhostScore800Digits", "pop-up '800': the '8', index 2"),
    (0xBC43, 0xBC4E, "shape", "GhostScore1600Digits", "pop-up '1600': the '16', index 3"),
    (0xBC4F, 0xBC4F, "bytes", "Pad_BC4F", "zero byte: padding"),
    (0xBC50, 0xBC8F, "bytes", "TuneAudf1", "64 entries stored to AUDF1, stepped every 4th jiffy by the routine around $A7DF (hyp: start-up tune)"),
    (0xBC90, 0xBCCF, "bytes", "TuneAudf2", "64 entries stored to AUDF2 together with TuneAudf1"),
    (0xBCD0, 0xBCD7, "words", "GhostScorePtrs", "pointers to the four ghost-eaten pop-up shapes, indexed by 2*GhostsEaten (confirmed, see docs/12-data-formats.md)"),
    (0xBCD8, 0xBCDE, "bytes", "AudfSweepDown", "AUDF1 values, descending, ended by 0; chosen when zp_F6 = 0"),
    (0xBCDF, 0xBCE5, "bytes", "AudfSweepUp", "AUDF1 values, ascending, ended by 0; chosen when zp_F6 <> 0"),
    (0xBCE6, 0xBCED, "words", "RecordPtrs_BCE6", "4 pointers into RAM $0686-$06A3 (indexed by 2*X)"),
    (0xBCEE, 0xBD0D, "bytes", "RandomPositions", "16 pairs (x,y) selected by RANDOM AND $0F; stored to zp_C2,X and zp_C6,X"),
    (0xBD0E, 0xBD15, "bytes", "CornerPositions", "4 pairs (x,y) = ($BE,$2C) ($3A,$2C) ($BE,$C4) ($3A,$C4), the four corners; stored to zp_C2,X and zp_C6,X"),
    (0xBD16, 0xBD25, "bytes", "RowOffsets", "16 ascending offsets added to a column index to read the grid at $06AE,Y"),
    (0xBD26, 0xBD44, "bytes", "CharCodeProfile", "31 character codes rising $3A to $4C and falling back; written to screen RAM from $0F92 as code and code+1"),
    (0xBD45, 0xBD6C, "bytes", "LevelGlyphRecords", "8 records of 5 character codes, copied to $0DF1; record chosen through LevelRecordOffsets"),
    (0xBD6D, 0xBD79, "bytes", "LevelRecordOffsets", "13 offsets (multiples of 5) indexed by zp_30 (level), clamped to 12"),
    (0xBD7A, 0xBDB8, "bytes", "PixelPatternTable", "63 pattern bytes used by ExpandData; index 63 is never used"),
    (0xBDB9, 0xBDBF, "bytes", "LevelIndexTable1", "7 entries indexed by zp_30 (level) clamped to 6; result indexes $07AE,X"),
    (0xBDC0, 0xBDC6, "bytes", "LevelIndexTable2", "7 entries indexed like LevelIndexTable1"),
    (0xBDC7, 0xBDD0, "text", "TextHighScore", None),
    (0xBDD1, 0xBDD5, "bytes", "DliChbaseTable", "CHBASE value for each DLI of DisplayList2 (zp_18 = 1..4: $E0, $30, $E0, $30); entry 0 = $18 matches DliHandler2"),
    (0xBDD6, 0xBDE6, "text6", "TextChangeDifficulty", "ANTIC mode 6 screen codes: low 6 bits = glyph of the OS font ($E000 band), top 2 bits = colour register; copied to $1D05"),
    (0xBDE7, 0xBDF6, "text6", "TextPressStartTo", "mode 6; copied to $1D56 (row 18)"),
    (0xBDF7, 0xBE04, "text6", "TextCopyright",
     "mode 6; copied to $1D57 (row 18, col 3) while the first title screen is shown; reads (C) ATARI 1982, all colour 3 (confirmed on screen)"),
    (0xBE05, 0xBE12, "bytes", "LevelIconCodes",
     "14 entries indexed by StartLevel ($1B, 0..13): the icon shown in the middle of the menu; entry N is the first of two glyphs (codes N and N+1 at $1CC6/$1CC7, row 11, charset $30). OPTION steps StartLevel through 0,1,2,4,6,8,10,12, so only those entries are reachable (confirmed on screen)"),
    (0xBE13, 0xBE74, "stream", "TitleCharsetStream", "type B stream -> RAM $1808, 160 bytes = 20 glyphs of the title character set (CHBASE=$18)"),
    (0xBE75, 0xBE94, "bytes", "TitleCharsetTail", "32 bytes copied to $18A8-$18C7 (4 more title glyphs)"),
    (0xBE95, 0xBF80, "bytes", "NibbleMapSource",
     "236 bytes; Start splits 256 bytes into 512 nibbles at RAM $0600-$07FF (hyp: maze/grid data); the last 20 bytes read belong to DisplayList2"),
    (0xBFC6, 0xBFD0, "text6", "TextPlayerGame", "mode 6; copied to $1C92 (2 PLAYER GAME) and, with colour bits changed ($40 added), to $1C56 (1 PLAYER GAME)"),
    (0xBFD1, 0xBFE0, "text6", "TextPressSelectFor", "mode 6; copied to $1C7A"),
    (0xBFE1, 0xBFF0, "text6", "TextPressOptionTo", "mode 6; copied to $1CF2"),
    (0xBFF1, 0xBFF9, "text6", "TextPlayGame", "mode 6; copied to $1D6D"),
]
