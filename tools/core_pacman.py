"""OV-67 (stage 66): PAC-MAN'S MOVEMENT IN PORT FORM on the named World of tools/core_world.py: the joystick, the wanted direction, the cornering flag, one step with the sub-cell counters, the maze pointer and the tunnel wrap,
and the chomp phase.  `move_pacman` is MovePacMan $B179 with the drawing of the mouth shape and the missiles (core_draw, OV-69).  tools/check_pacman.py runs it against the ROM routine.
Directions 1 up, 2 down, 4 left, 8 right.  Pac-Man is entity 4: PacX = EntityX[4], PacY = EntityY[4], PacDirection = EntityDir[4]."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_draw as D  # noqa: E402
import core_ref as R  # noqa: E402
import core_tables as T  # noqa: E402

TUNNEL_LEFT, TUNNEL_RIGHT = 0x2A, 0xCA
MAZE_PTR_AFTER_LEFT, MAZE_PTR_AFTER_RIGHT = 0xB7, 0x8F       # low byte of MazePtr after the wrap through the left / right tunnel mouth
ROW = 0x28


def _ptr(w):
    return w.MazePtr[0] | w.MazePtr[1] << 8


def _set_ptr(w, v):
    v &= 0xFFFF
    w.MazePtr[0], w.MazePtr[1] = v & 0xFF, v >> 8


def read_joystick(w, mask):
    """the stick of the player on turn (the four low bits are 0 for a pressed direction): ignored when none or exactly two directions are pressed (a diagonal); otherwise it is the wanted direction and, when the
    maze allows it here, the direction at once"""
    a = (w.stick[w.CurrentPlayer] ^ 0x0F) & 0xFF
    if a == 0:
        return
    if bin(a & 0x0F).count("1") == 2:
        return
    w.ATRACT = a                                     # any stick input resets the attract-mode timer
    w.PacWantedDir = a
    if a & mask:
        w.EntityDir[4] = a


def _step(w, d):
    """one step of 1 pixel sideways or 2 pixels vertically, with the sub-cell counter (0-3) and the maze pointer; held (PacHold) -> no step"""
    if w.PacHold:
        return
    y = w.EntityY
    x = w.EntityX
    if d == 1:
        y[4] = (y[4] - 2) & 0xFF
        if w.PacSubY == 0:
            w.PacSubY = 3
        else:
            w.PacSubY -= 1
            if w.PacSubY == 0 and y[4] != w.LastCellY:
                _set_ptr(w, _ptr(w) - ROW)
    elif d == 2:
        y[4] = (y[4] + 2) & 0xFF
        if w.PacSubY == 3:
            w.PacSubY = 0
            if y[4] != w.LastCellY:
                _set_ptr(w, _ptr(w) + ROW)
        else:
            w.PacSubY += 1
    elif d == 8:
        if x[4] == TUNNEL_RIGHT:
            x[4] = TUNNEL_LEFT
            w.MazePtr[0] = MAZE_PTR_AFTER_RIGHT
        x[4] = (x[4] + 1) & 0xFF
        if w.PacSubX == 3:
            w.PacSubX = 0
            if x[4] != w.LastCellX:
                _set_ptr(w, _ptr(w) + 1)
        else:
            w.PacSubX += 1
    elif d == 4:
        if x[4] == TUNNEL_LEFT:
            x[4] = TUNNEL_RIGHT
            w.MazePtr[0] = MAZE_PTR_AFTER_LEFT
        x[4] = (x[4] - 1) & 0xFF
        if w.PacSubX == 0:
            w.PacSubX = 3
        else:
            w.PacSubX -= 1
            if w.PacSubX == 0 and x[4] != w.LastCellX:
                _set_ptr(w, _ptr(w) - 1)


def move_pacman(w):
    """MovePacMan $B179: one frame of Pac-Man's movement"""
    if w.PacFrozen & 0x80:
        return
    mask, _ = R.junction_exits(True, w.EntityX[4], w.EntityY[4], w.EntityDir[4], 0)
    if w.PacWantedDir & mask:                        # a remembered turn that is possible here: take it
        if w.PacWantedDir != w.EntityDir[4]:
            both = w.PacWantedDir | w.EntityDir[4]
            if both & 0x03 and both & 0x0C:          # a turn across (vertical <-> horizontal): the cornering flag
                w.PacCornering = both
        w.EntityDir[4] = w.PacWantedDir
    read_joystick(w, mask)
    d = w.EntityDir[4]
    picture = {1: 6, 2: 8, 4: 4, 8: 2}                # the index (twice) of the direction's pictures in PacShapePtrs
    if not d & mask:                                 # blocked: no step, the wide-open mouth frame ($0A) of the direction
        if d in picture:
            D.draw_pacman(w, picture[d], 0x0A)
        else:
            D.draw_pacman_full(w)
        return
    if d not in picture:
        D.draw_pacman_full(w)
        return
    _step(w, d)
    c = w.ChompPhase                                 # the mouth: 0 closed (the full disc), 1 and 3 the first frame, 2 the second; 3 is followed by 0
    if c == 0:
        w.ChompPhase = 1
        D.draw_pacman_full(w)
    else:
        D.draw_pacman(w, picture[d], T.rom(D.PAC_MOUTH_OFFSETS + c - 1))
        w.ChompPhase = 0 if c == 3 else (c + 1) & 0xFF
