"""Stage 66, reworked 2026-11-22: the data tables the core algorithms of tools/core_ref.py index, DERIVED FROM THE ROM AT IMPORT (no ROM byte is kept in this file).
The ROM tables are slices of the cartridge image; the RAM tables are what `Start` builds at $0600 from the nibble stream at $BE95 (tools/decode_streams.py).  The lists below say where each table is.
tests/test_core.py checks every table against the memory of the concrete 6502 after `Start`; the C port installs the same tables from the same ROM (src/c/assets/rom_install.c)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

TABLES = [  # name, source ('rom' or 'ram'), address, length, comment
    ("MOVE_DELAY", "ram", 0x07AE, 24, "frames per step, four-step cycles (RAM image of NibblesMoveDelay)"),
    ("PAC_DELAY_BASE", "rom", 0xBDB9, 7, "offsets into MOVE_DELAY for Pac-Man by level (clamped to 6)"),
    ("GHOST_DELAY_BASE", "rom", 0xBDC0, 7, "offsets into MOVE_DELAY for the ghosts by level (clamped to 6)"),
    ("HOUSE_RELEASE", "rom", 0xBBF2, 6, "ghost-house release timers: 3-byte windows picked by min(level, 3)"),
    ("FRIGHT_FRAMES", "rom", 0xBBF8, 256, "frames of solid frightened colour by level; the lookup is NOT clamped, past the 15 entries it reads the ROM bytes that follow"),
    ("FRIGHT_END", "ram", 0x0672, 256, "phase at which the frightened period ends, by level; NOT clamped (20 entries, then the RAM that follows: start and patrol routes)"),
    ("BONUS_GLYPH", "rom", 0xBD26, 13, "first glyph code of the bonus item by level (clamped to 12)"),
    ("BONUS_SCORE", "ram", 0x0794, 26, "13 (thousands, hundreds) BCD digit pairs by level (clamped to 12)"),
    ("BONUS_SCORE_GLYPH_OFFSETS", "rom", 0xBD6D, 13, "offsets into BONUS_SCORE_GLYPHS by level (clamped to 12)"),
    ("BONUS_SCORE_GLYPHS", "rom", 0xBD45, 40, "five screen codes each: the pop-up of the bonus score"),
    ("JUNCTION_Y", "rom", 0xBB83, 10, "y of the ten lattice rows"),
    ("JUNCTION_X", "rom", 0xBB8D, 10, "x of the ten lattice columns"),
    ("JUNCTION_EXITS", "ram", 0x060E, 100, "exit masks (1 up, 2 down, 4 left, 8 right), 10 rows of 10 columns"),
    ("NO_REVERSE", "ram", 0x07C6, 9, "mask of the exits a ghost may take, indexed by its direction (1, 2, 4, 8): the opposite one is removed"),
    ("REVERSE_DIR", "ram", 0x07CF, 9, "the opposite direction, indexed by direction"),
]


IMAGES = [  # name, source, address, length, comment: byte images read with their run-on (the code indexes past the end of a table into what follows)
    ("RAM_0600", "ram", 0x0600, 0x200, "the RAM tables Start expands ($0600-$07FF): JunctionExits, FrightenEndPhase, StartRoutes $0686, PatrolRoutes $06AE, BonusScore, MoveDelay, NoReverseMask, ReverseDir"),
    ("ROM_BA00", "rom", 0xBA00, 0x600, "the ROM tables and pictures of the core routines ($BA00-$BFFF): the ghost and Pac-Man pictures $BAC0-$BB54, the death and pop-up pictures, junction lists, sight lists and offsets (read with run-on), release timers, frightened frames, StartRoutePtrs $BCE6, PatrolStartPositions $BCEE, CornerPositions $BD0E, PatrolRouteOffsets $BD16"),
]


_RAM = S.split_nibbles(0xBE95)[0]                 # $0600-$07FF: 256 source bytes, two nibbles each


def _bytes(src, addr, n):
    if src == "ram":
        assert 0x0600 <= addr and addr + n <= 0x0600 + len(_RAM), (addr, n)
        return _RAM[addr - 0x0600:addr - 0x0600 + n]
    assert 0xA000 <= addr and addr + n <= 0xC000, (addr, n)
    return S.ROM[addr - 0xA000:addr - 0xA000 + n]


for _name, _src, _addr, _n, _why in TABLES:
    globals()[_name] = tuple(_bytes(_src, _addr, _n))
for _name, _src, _addr, _n, _why in IMAGES:
    globals()[_name] = bytes(_bytes(_src, _addr, _n))


def ram(addr):
    """a byte of the RAM tables by its address ($0600-$07FF)"""
    return RAM_0600[addr - 0x0600]


def rom(addr):
    """a byte of the ROM tables by its address ($BA00-$BFFF)"""
    return ROM_BA00[addr - 0xBA00]
