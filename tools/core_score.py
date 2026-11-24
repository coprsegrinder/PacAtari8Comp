"""OV-67 (stage 66): SCORING, DOTS AND POWER PELLETS ON THE NAMED WORLD (tools/core_world.py): the BCD addition into the score cells with the extra life, the lives icons, eating a dot, the dot count and the power pellet.
The logic of AddToScore $B423, DrawLives $AD15, EatDotAtPacMan $B33A, PowerPelletCheck $B39F / PowerPelletEaten $B3DE; the screen cells are w.status ($2000 + i) and w.maze ($0C00 + i)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_ref as R  # noqa: E402
import core_tables as T  # noqa: E402

SCORE_CELLS = (0x2A, 0x47)               # $202A and $2047: the six cells of player 1 and 2 (index into w.status)
LIFE_ICON_CELLS = (0x374, 0x376, 0x378)  # $0F74, $0F76, $0F78 minus $0C00 (index into w.maze)
LIFE_ICON = 0x9B


def draw_lives(w):
    """DrawLives $AD15: the lives left (after the current one) as up to three icons at the bottom left of the maze screen"""
    n = w.Lives[w.CurrentPlayer]
    icons = [LIFE_ICON if n >= k else 0 for k in (1, 2, 3)] if n <= 3 else [0, 0, 0]
    for cell, v in zip(LIFE_ICON_CELLS, icons):
        w.maze[cell] = v


def add_to_score(w):
    """AddToScore $B423: adds the six BCD digits of ScoreAdd to the player's six score cells (leading zeros blank), clears ScoreAdd, and gives the extra life when the 10,000s cell is not blank"""
    p = w.CurrentPlayer
    base = SCORE_CELLS[p]
    cells = [w.status[base + k] for k in range(6)]
    carry = 0
    new = list(cells)
    for y in range(5, -1, -1):
        s = (cells[y] & 0x0F) + carry + w.ScoreAdd[y]
        carry = 1 if s >= 10 else 0
        d = s % 10
        code = 0x10 | d
        if d == 0:
            code = 0 if y == 0 else (0x10 if (cells[y - 1] != 0 or carry) else 0)
        new[y] = code
    for k in range(6):
        w.status[base + k] = new[k]
        w.ScoreAdd[k] = 0
    w.BcdCarry = carry
    if w.ExtraLifeFlag[p] == 0 and new[1] != 0:
        w.ExtraLifeFlag[p] += 1
        w.Lives[p] = (w.Lives[p] + 1) & 0xFF
        draw_lives(w)


def count_dot(w):
    """the dot count of the player on turn (16 bits); the board is complete at 260 ($0104)"""
    p = w.CurrentPlayer
    w.DotsEatenLo[p], w.DotsEatenHi[p], done = R.count_dot(w.DotsEatenLo[p], w.DotsEatenHi[p])
    if w.DotsEatenHi[p] != 0 and w.DotsEatenLo[p] == 4:
        w.LevelComplete = 1


def eat_dot(w):
    """EatDotAtPacMan $B33A: in a new cell (both sub-cell counters 0): a dot (1) gives 10 points, the dot sound and the count; a power-pellet cell (2) is cleared (its eating is PowerPelletCheck's)"""
    if w.PacSubX or w.PacSubY:
        return
    px, py = w.EntityX[4], w.EntityY[4]
    if px == w.LastCellX and py == w.LastCellY:
        return
    w.LastCellY, w.LastCellX = py, px
    ptr = w.MazePtr[0] | w.MazePtr[1] << 8
    v = w.maze[ptr - 0x0C00]
    if v == 2:
        w.maze[ptr - 0x0C00] = 0
        return
    if v != 1:
        return
    w.ScoreAdd[4] = 1
    add_to_score(w)
    w.DotSoundActive = w.DotDelay = 1
    w.DotSoundStep = 0
    w.DotSoundAlt = 1 if w.DotSoundAlt == 0 else 0
    w.maze[ptr - 0x0C00] = 0
    count_dot(w)


def power_pellet_check(w):
    """PowerPelletCheck $B39F + PowerPelletEaten $B3DE: Pac-Man on one of the four pellet squares whose bit is still set in PelletFlags: 50 points, the frightened period starts (phase 1, the countdown of the level), every ghost that is not eaten turns frightened and reverses"""
    p = w.CurrentPlayer
    flags = w.PelletFlags[p]
    bit = None
    for i, (y, x) in enumerate(R.PELLET_SQUARES):
        if flags & (1 << i) and w.EntityY[4] == y and w.EntityX[4] == x:
            bit = 1 << i
            break
    if bit is None:
        return
    w.Scratch2A = flags
    w.PelletFlags[p] = (bit ^ 0x0F) & flags
    w.ScoreAdd[4] = 5
    add_to_score(w)
    w.FrightenPhase = 1
    w.GhostsEaten = 0xFF
    w.FrightenCountdown = R.fright_frames(w.Level[p])
    states, dirs = R.power_pellet_ghosts(list(w.GhostState), list(w.EntityDir[:4]))
    w.GhostState, w.EntityDir[:4] = states, dirs
    count_dot(w)
