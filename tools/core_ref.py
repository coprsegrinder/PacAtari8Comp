"""Stage 66: THE CORE ALGORITHMS OF THE GAME IN PORT FORM - pure functions on plain values (no memory image, no 6502 addresses), the data in tools/core_tables.py.
This is the reference a C port is written from; tests/test_core.py and tools/check_core.py run every function against the ROM routine on the concrete 6502 (tools/cpu6502.py).
Areas: levels (pacing, release timers, frightened time, bonus), scoring (BCD, extra life, the values), ghost AI (junction exits, steering, forced chase, the frightened period), the dot count.
Directions: 1 up, 2 down, 4 left, 8 right.  Ghost states: see docs/17 (bit 7 frightened, bit 6 eaten, 0x02 chase, 0x08 / 0x10 patrol, 0x20 corner ...).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_tables as T  # noqa: E402

UP, DOWN, LEFT, RIGHT = 1, 2, 4, 8
GS_FRIGHT = 0x80
GS_EYES = 0x42
GS_CHASE = 0x02
DOTS_PER_BOARD = 260                       # the board is complete when the count (16 bits) reaches 260
PELLET_SQUARES = ((0x3C, 0x3A), (0x3C, 0xBE), (0xA4, 0x3A), (0xA4, 0xBE))     # (y, x) of the four power pellets, bit 0 .. 3 of the pellet flags
GHOST_POINTS = (200, 400, 800, 1600)
DOT_POINTS, PELLET_POINTS = 10, 50


# ------------------------------------------------------------------------------------------------ levels
def pacing_delay(entity, level, cycle):
    """frames per step: entity 4 is Pac-Man, 0-3 the ghosts; `level` is the 8-bit counter (0 = board 1), clamped to 6; cycle 0-3"""
    lv = min(level, 6)
    base = (T.PAC_DELAY_BASE if entity == 4 else T.GHOST_DELAY_BASE)[lv]
    return T.MOVE_DELAY[base + cycle]


def move_delay_tick(entity, level, cycle, count):
    """one frame of the pacing of an entity: returns (moves_this_frame, new_cycle, new_count).  The count falls by one; at 0 the entity moves, the cycle advances (0..3) and the count is reloaded."""
    count = (count - 1) & 0xFF
    if count != 0:
        return False, cycle, count
    cycle = 0 if cycle == 3 else cycle + 1
    return True, cycle, pacing_delay(entity, level, cycle)


def release_timers(level):
    """the release timers of ghosts 1, 2, 3 (ghost 0 is out at once), in units of 4 frames: a 3-byte window of the table that slides with the board, clamped at board 4"""
    y = min(level, 3)
    return (T.HOUSE_RELEASE[y + 2], T.HOUSE_RELEASE[y + 1], T.HOUSE_RELEASE[y])


def fright_frames(level):
    """frames of solid frightened colour; `level` is NOT clamped (past 15 the table runs on into the ROM bytes that follow: the real game's behaviour on boards 16-256)"""
    return T.FRIGHT_FRAMES[level & 0xFF]


def fright_end_phase(level):
    """the phase at which the frightened period ends (0 = practically endless: the phase counter has to wrap); NOT clamped"""
    return T.FRIGHT_END[level & 0xFF]


def fright_total_frames(level):
    """frames of the whole frightened period (docs/14); None for an end phase of 0 (ends after the 8-bit phase counter wraps, about 6,100 frames of flashing)"""
    end = fright_end_phase(level)
    if end == 0:
        return None
    return fright_frames(level) + (end - 2) * 24 + 2 if end >= 2 else fright_frames(level) + end


def bonus_glyph(level):
    return T.BONUS_GLYPH[min(level, 12)]


def bonus_points(level):
    """the bonus score of the board as a number (thousands and hundreds digits)"""
    i = 2 * min(level, 12)
    return T.BONUS_SCORE[i] * 1000 + T.BONUS_SCORE[i + 1] * 100


def bonus_popup_glyphs(level):
    """the five screen codes of the pop-up of the bonus score"""
    o = T.BONUS_SCORE_GLYPH_OFFSETS[min(level, 12)]
    return T.BONUS_SCORE_GLYPHS[o:o + 5]


# ------------------------------------------------------------------------------------------------ scoring
def score_add(score, points, extra_given, lives):
    """a six-digit decimal score (it wraps at 1,000,000).  The extra life is given the first time the 10,000s CELL on the screen is not blank after an addition.  The cell is blank only while every digit to its left is 0, and the
    code tests the OLD cell to its left: so the cell is not blank when the new score is 10,000 or more, or when the old score was 100,000 or more (a wrap from 999,992 to 1,992 gives a life, if none was given).
    Returns (score, extra_given, lives)."""
    new = (score + points) % 1000000
    if extra_given == 0 and (new >= 10000 or score >= 100000):
        return new, 1, (lives + 1) & 0xFF
    return new, extra_given, lives


def ghost_points(n):
    """the points of the ghost eaten with the running count n (0 .. 3 -> 200, 400, 800, 1600; the count is an 8-bit counter that starts at $FF for a new period, so the first ghost is n = 0 and every value from 3 on, wrapped ones included, scores 1600)"""
    return GHOST_POINTS[n] if n < 4 else 1600


# ------------------------------------------------------------------------------------------------ ghost AI
def junction_exits(is_pacman, x, y, direction, state):
    """exits of the lattice point under an entity -> (mask, on_lattice_point).  Ghosts cannot reverse (NO_REVERSE); on the door row beside the door ($76 / $82) a normal ghost loses its up exit, a frightened one has only up."""
    if y in T.JUNCTION_Y:
        r = T.JUNCTION_Y.index(y)
        if x in T.JUNCTION_X:
            mask, on = T.JUNCTION_EXITS[10 * r + T.JUNCTION_X.index(x)], True
        else:
            mask, on = 0x0C, False
    else:
        mask, on = (0x03, False) if x in T.JUNCTION_X else (0x0C, False)
    if not is_pacman:
        mask &= T.NO_REVERSE[direction]
        if y == 0x64 and x in (0x76, 0x82):
            mask = 1 if (state & GS_FRIGHT) else ((mask & 0x0E) or 1)
    return mask, on


def wants(ey, ex, ty, tx, state):
    """the wanted vertical and horizontal direction (0 = none): towards the target, away from it when frightened"""
    fr = bool(state & GS_FRIGHT)
    wv = 0 if ey == ty else ((DOWN if fr else UP) if ey > ty else (UP if fr else DOWN))
    wh = 0 if ex == tx else ((RIGHT if fr else LEFT) if ex > tx else (LEFT if fr else RIGHT))
    return wv, wh


def steer(ey, ex, ty, tx, state, mask, rnd):
    """the direction a ghost takes at a junction: head for the target (away from it when frightened); both axes wanted and possible -> RANDOM bit 7 picks; neither -> a random exit of `mask`.
    `rnd` is an iterator of POKEY RANDOM values (one or none is used)."""
    wv, wh = wants(ey, ex, ty, tx, state)
    if wv and mask & wv:
        if wh and mask & wh:
            return wh if next(rnd) & 0x80 else wv
        return wv
    if wh and mask & wh:
        return wh
    r = next(rnd) & mask
    if r == 0:
        r = mask
    for d in (UP, DOWN, LEFT, RIGHT):
        if r & d:
            return d
    return RIGHT


def force_chase(states, x):
    """ForceChase: ghosts x, x-1 .. 0 in the states 8 / 0x10 / 0x20 (patrol start, patrol, corner) go to chase; returns the new list"""
    out = list(states)
    for i in range(x, -1, -1):
        if out[i] in (0x08, 0x10, 0x20):
            out[i] = GS_CHASE
    return out


def power_pellet_ghosts(states, dirs):
    """a power pellet: every ghost that is not eaten becomes frightened (bit 7); it reverses unless it chases (bit 2 of the new state) or is the plain house ghost ($80).  -> (states, dirs)"""
    s2, d2 = list(states), list(dirs)
    for g in range(3, -1, -1):
        s = states[g]
        if s & 0x40:
            continue
        s |= GS_FRIGHT
        s2[g] = s
        if (s >> 2) & 1:
            continue
        if (s >> 3) & 0x3B == 0:
            continue
        d2[g] = T.REVERSE_DIR[dirs[g]]
    return s2, d2


def frightened_end(states):
    """the end of the frightened period: a plain frightened house ghost ($80) goes back to 0; every other frightened ghost with a bit of $BB set goes to the corner state 0x20; a frightened ghost with none of them keeps its state"""
    out = list(states)
    for g in range(3, -1, -1):
        s = out[g]
        if s & 0x80:
            if s == 0x80:
                out[g] = 0
            elif s & 0xBB:
                out[g] = 0x20
    return out


# ------------------------------------------------------------------------------------------------ the dot count
def count_dot(lo, hi):
    """the 16-bit count of dots and pellets eaten on the board -> (lo, hi, board_complete)"""
    lo = (lo + 1) & 0xFF
    if lo == 0:
        hi = (hi + 1) & 0xFF
    return lo, hi, (hi != 0 and lo == 4)
