"""OV-68 (stage 67): THE COLLISION GEOMETRY OF THE GTIA, as a function of the scene - what the game reads in `$D000-$D00F` (the contact test reads M1PL and M2PL, the bonus pick-up M2PF) is computed by the hardware from the
pictures of the players and missiles and the playfield; a port has no such hardware, so this is the model it uses.  It is checked against the GTIA of the real game in Altirra on random scenes (tools/altirra_collide.cmd,
tools/analyze_collide.py, analysis/evidence-collide-summary.txt) and, in tools/scene_model.py, against the scenes the ROM itself draws.

The scene: the eight positions (HPOSP0-3, HPOSM0-3 in colour clocks), the player-missile pages (one byte a scan line: the missile page `$2300` and the four player pages `$2400-$27FF`) and the playfield (the character cells of the
game screen and the character set).  SIZEP / SIZEM are 0 in the game (a player 8 clocks wide, a missile 2 clocks wide): the model does not do the other sizes.

The rules (all verified on the real GTIA):
  - a player has 8 pixels a line, bit 7 leftmost, one pixel one colour clock: the pixel of bit b of player p lies at clock HPOSP[p] + (7 - b);
  - the four missiles share one byte a line, two bits each: missile m owns bits 2m+1 (left) and 2m (right) at clocks HPOSM[m] and HPOSM[m] + 1;
  - the playfield of ANTIC mode 4 (the maze rows): a character cell is 4 colour clocks wide and 8 scan lines high, its 8 bits a row are four pixels of two bits; the pixel value 1, 2, 3 is the colour register PF0, PF1, PF2
    (PF3 when the character's bit 7 is set and the value is 3), value 0 is the background: no collision; the screen starts at colour clock 48 and the first maze row at scan line 40 (page row 40);
  - only pixels at colour clocks 34 to 221 and on scan lines 8 to 247 count (the visible area including the borders: an object at HPOS 0 collides with nothing, nor does a row in the blank above or below; found on the real GTIA);
  - a collision bit is set for any scan line and clock at which two pixels coincide (priority does not matter);  M0PF..M3PF ($D000-$D003) bit k = the missile touched playfield colour k; P0PF..P3PF ($D004-$D007) the same for
    the players; M0PL..M3PL ($D008-$D00B) bit k = the missile touched player k (also its own number); P0PL..P3PL ($D00C-$D00F) bit k = the player touched player k (never its own number).
The registers hold the overlaps of everything shown since the last HITCLR (`$D01E`); the game clears them once a frame, after the contact test.
Usage: python -I tools/gtia_collisions.py   (a small self-test)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SCREEN_X0 = 48                 # the first colour clock of the playfield (normal width)
MAZE_LINE0 = 40                # the first scan line of the first mode-4 row, counted as the player-missile pages count (page row = scan line; the picture starts at line 8, the maze at line 8 + 32)
MAZE_ROWS, MAZE_COLS = 23, 40
VISIBLE_LINES = (8, 247)       # the scan lines at which an object's row counts: the upper bound is fitted (on 6,834 scenes with rows anywhere in the pages 247 gives 0 differences, 246 and 248 give 3 each); the picture starts at line 8
VISIBLE = (34, 221)            # the colour clocks at which an object's pixel counts (fitted on 2,500 wide scenes: (34, 221) gives 0 differences, every neighbouring pair 19 or more)


class Playfield:
    """the maze band of the game screen: 23 rows of 40 character codes drawn from a 128-glyph set (CHBASE $30)"""

    def __init__(self, cells, charset):
        self.cells = cells                    # 23 * 40 screen codes
        self.charset = charset                # 8 bytes a glyph, glyphs 0-127 (the bytes at $3000)

    def pf_bit(self, line, clock):
        """-> the playfield colour register bit (0-3) a pixel at (scan line, colour clock) has, or None (background, or outside the maze band)"""
        if not MAZE_LINE0 <= line < MAZE_LINE0 + 8 * MAZE_ROWS:
            return None
        x = clock - SCREEN_X0
        if not 0 <= x < 4 * MAZE_COLS:
            return None
        row, sub = divmod(line - MAZE_LINE0, 8)
        col, k = divmod(x, 4)
        code = self.cells[row * MAZE_COLS + col]
        v = (self.charset[(code & 0x7F) * 8 + sub] >> (6 - 2 * k)) & 3
        if v == 0:
            return None
        if v == 3:
            return 3 if code & 0x80 else 2
        return v - 1


def collision_registers(hpos, missile_page, player_pages, playfield, visible=None, lines=None):
    """-> the sixteen collision registers $D000-$D00F of a scene: hpos = [P0, P1, P2, P3, M0, M1, M2, M3], missile_page = 256 bytes, player_pages = four lists of 256 bytes;
    `visible` = (first, last) colour clock at which a pixel counts (the model's default: VISIBLE)"""
    lo, hi = visible or VISIBLE
    l0, l1 = lines or VISIBLE_LINES
    mpf = [0] * 4
    ppf = [0] * 4
    mpl = [0] * 4
    ppl = [0] * 4
    for line in range(l0, l1 + 1):
        mb = missile_page[line]
        pbs = [pg[line] for pg in player_pages]
        if not mb and not any(pbs):
            continue
        # the pixels of this line: clock -> (set of missiles, set of players)
        miss = {}
        for m in range(4):
            two = (mb >> (2 * m)) & 3
            for k in (0, 1):
                if two & (2 >> k) and lo <= hpos[4 + m] + k <= hi:          # bit 2m+1 is the left pixel
                    miss.setdefault(hpos[4 + m] + k, set()).add(m)
        play = {}
        for p in range(4):
            b = pbs[p]
            for j in range(8):
                if b & (0x80 >> j) and lo <= hpos[p] + j <= hi:
                    play.setdefault(hpos[p] + j, set()).add(p)
        for clock, ms in miss.items():
            pf = playfield.pf_bit(line, clock)
            ps = play.get(clock, ())
            for m in ms:
                if pf is not None:
                    mpf[m] |= 1 << pf
                for p in ps:
                    mpl[m] |= 1 << p
        for clock, ps in play.items():
            pf = playfield.pf_bit(line, clock)
            for p in ps:
                if pf is not None:
                    ppf[p] |= 1 << pf
                for q in ps:
                    if q != p:
                        ppl[p] |= 1 << q
    return mpf + ppf + mpl + ppl


def scene_pages(rows, patterns):
    """a scene as the stub puts it into the pages: rows = [first row of the missile picture, of players 0-3], patterns = five lists of 16 bytes -> (missile page, [player pages])"""
    pages = []
    for r, pat in zip(rows, patterns):
        page = [0] * 256
        for i, b in enumerate(pat):
            if r + i < 256:
                page[r + i] = b
        pages.append(page)
    return pages[0], pages[1:]


def selftest():
    cells = [0] * (MAZE_ROWS * MAZE_COLS)
    cs = bytes(8 * 128)
    pf = Playfield(cells, cs)
    mp = [0] * 256
    pp = [[0] * 256 for _ in range(4)]
    mp[100] = 0x30                                  # missile 2: bits 5 and 4
    pp[1][100] = 0xFF
    r = collision_registers([0, 100, 0, 0, 0, 0, 104, 0], mp, pp, pf)
    assert r[8 + 2] == 0b0010, r                    # M2PL bit 1: missile 2 at clocks 104-105 is inside player 1 (100-107)
    assert r[12 + 1] == 0 and r[12] == 0, r
    r = collision_registers([0, 100, 0, 0, 0, 0, 108, 0], mp, pp, pf)
    assert r[8 + 2] == 0, r                         # clock 108 is just right of the player
    print("gtia_collisions self-test ok")


if __name__ == "__main__":
    selftest()
