"""Exact software model of GhostSeesPacMan ($BA19) built from the ROM bytes (step C11, tables around $BBAB-$BBF7).
Usage as a library:  from sight_model import sees, SightResult
sees(ghost, gx, gy, gdir, px, py, rtclok2) -> True when the code reaches $BAB7 (state := 2, ChaseTimer := $A0).
The model reads the ROM bytes at the addresses the code uses and keeps scanning past the end of a list exactly like the 6502 does,
so any accidental use of neighbouring tables is reproduced.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

rd = S.rd
YS = [rd(0xBB83 + i) for i in range(10)]     # JunctionYList
XS = [rd(0xBB8D + i) for i in range(10)]     # JunctionXList
X_BASE, Y_BASE = 0xBBB8, 0xBBD8              # D_BBB8 (used for horizontal sight), ProfileList_BBD8 (vertical sight)


def _finish(ghost, rtclok2):
    """$BAAF: ghost 2 only reacts when RTCLOK2 bit 7 is clear."""
    return not (ghost == 2 and rtclok2 >= 0x80)


def _scan(base, y, first, second, stop_when):
    """Generic list scan: returns (value, reached_FF). `stop_when(v)` ends the scan at the first element satisfying it."""
    y &= 0xFF
    while True:
        v = rd(base + y)
        if v == 0xFF:
            return v, True
        if stop_when(v):
            return v, False
        y = (y + 1) & 0xFF
        if y == 0:                      # BNE falls through after 256 iterations (never happens with this data)
            return v, False


def sees(ghost, gx, gy, gdir, px, py, rtclok2=0):
    if gy == py:                                           # $BA26: same row
        y = next((i for i in range(9, -1, -1) if YS[i] == py), None)
        if y is None:
            return False
        if gx < px:                                        # ghost is left of Pac-Man
            if gdir != 8:
                return False
            v, ff = _scan(X_BASE, y, gx, px, lambda v: v >= gx)
            if ff:
                return _finish(ghost, rtclok2)
            return _finish(ghost, rtclok2) if v >= px else False
        if gdir != 4:                                      # ghost is right of (or at) Pac-Man
            return False
        v, ff = _scan(X_BASE, y, px, gx, lambda v: v >= px)
        if ff:
            return _finish(ghost, rtclok2)
        return _finish(ghost, rtclok2) if v >= gx else False
    if gx == px:                                           # $BA6B: same column
        y = next((i for i in range(9, -1, -1) if XS[i] == px), None)
        if y is None:
            return False
        if gy >= py:                                       # ghost below (or level with) Pac-Man
            if gdir != 1:
                return False
            v, ff = _scan(Y_BASE, y, py, gy, lambda v: v >= py)
            if ff:
                return _finish(ghost, rtclok2)
            return _finish(ghost, rtclok2) if v >= gy else False
        if gdir != 2:                                      # ghost above Pac-Man
            return False
        v, ff = _scan(Y_BASE, y, gy, py, lambda v: v >= gy)
        if ff:
            return _finish(ghost, rtclok2)
        return _finish(ghost, rtclok2) if v >= py else False
    return False
