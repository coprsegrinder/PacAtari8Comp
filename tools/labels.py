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
GAME_ZP = {0x3C: "SrcPtrL", 0x3D: "SrcPtrH", 0x3E: "DstPtrL", 0x3F: "DstPtrH"}


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
}
