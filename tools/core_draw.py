"""OV-69 (stage 69-70): THE DRAWING IN PORT FORM on the named World of tools/core_world.py - what the original's drawing routines leave in the player-missile pages (`w.pm`: the missile page `$2300` then the four player
pages, one byte a scan line), in the eight position registers (`w.hpos`: HPOSP0-3, HPOSM0-3) and in the picture buffers (`w.picbuf`: Pac-Man's rows at `$0400`, the ghost being drawn at `$0410`).  This is the SCENE that
tools/gtia_collisions.py (docs/50) turns into the collision registers.  tools/check_draw.py compares every function with the ROM routine on the concrete 6502.
  draw_ghost            the picture part of StepAndDrawEntity `$B93F-$B998`: the ghost's shape (direction, frightened, eyes, the feet row of the leg phase) into the player page at EntityY
  step_and_draw_entity  StepAndDrawEntity `$B902`: one step in a direction and the picture (the step is skipped while DrawOnly is set)
  draw_pacman           the picture part of MovePacMan `$B2E9-$B338`: Pac-Man's shape (a mouth frame of a direction, or the full disc) into the missile page at PacY, the four missile positions
  draw_all_in_place     DrawAllInPlace `$AD49`: the four ghosts without a step, then the full disc
  draw_popup            the picture part of GhostEaten `$A886`: the score picture of the eaten ghost in the missile page, the zeros in the ghost's player page, the positions
  death_animation_draw  the picture part of DeathAnimation `$AEF7`: the pictures of the 16-step death into the missile page
  clip_entity_at_tunnel / clip_entities_on_tunnel_row   ClipEntityAtTunnel `$AB57`, ClipEntitiesOnTunnelRow `$AB48`: at the tunnel row the pictures are cut at the mouths and the entity wraps round
  fill_player_pages / clear_player_memory   FillPlayerPages `$B100`, ClearPlayerMemory `$B0F1`
A write that would fall outside the pages (a first row so high that the 16 rows run past `$27FF`) is not modelled: the game never has one."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_tables as T  # noqa: E402

PM_LEN = 0x500
PIC_GHOST = 0x10                  # picbuf index of $0410
PIC_PAC = 0x00                    # picbuf index of $0400
PAC_SHAPE_PTRS = 0xBB65
GHOST_SHAPES = 0xBAC0
GHOST_SCORE_ZEROS = 0xBC13
GHOST_SCORE_PTRS = 0xBCD0
PAC_MOUTH_OFFSETS = 0xBB55
PAC_SHAPE_UP2 = 0xBB38
STAR_SHAPE = 0xBC07
DEATH_PLOT_BYTES = 0xBB57
DEATH_PLOT_ROWS = 0x0600
DIR_OFFSET = {1: 0x00, 2: 0x0A, 4: 0x14, 8: 0x1E}


def rom(a):
    """a byte of the ROM tables; an address outside them (a pointer read out of a table by a state the game never has) reads 0"""
    a &= 0xFFFF
    return T.rom(a) if 0xBA00 <= a < 0xC000 else 0


def rom_word(a):
    return rom(a) | rom(a + 1) << 8


def _put(w, addr, v):
    """a store into the player-missile pages at a 16-bit address (a pointer plus a row): outside $2300-$27FF nothing is modelled"""
    i = addr - 0x2300
    if 0 <= i < PM_LEN:
        w.pm[i] = v & 0xFF


def _get(w, addr):
    i = addr - 0x2300
    return w.pm[i] if 0 <= i < PM_LEN else 0


# ------------------------------------------------------------------------------------------------ the ghosts
def draw_ghost(w, x, a):
    """StepAndDrawEntity $B93F: A = the direction's shape offset ($00 up, $0A down, $14 left, $1E right)"""
    st = w.GhostState[x]
    if st & 0x80:
        a = 0x28                                         # frightened
    if st & 0x40:                                        # eyes only (bit 6): the shape at $32, no feet row
        a, feet = 0x32, 0
    else:
        feet = 0xAA if w.LegPhase else 0x54
    w.picbuf[0x1C] = feet
    src = GHOST_SHAPES + a
    for k in range(10):
        w.picbuf[0x12 + k] = rom(src + k)
    w.hpos[x] = w.EntityX[x]
    dst = ((0x24 + x) & 0xFF) << 8 | w.EntityY[x]
    for k in range(16):
        _put(w, dst + k, w.picbuf[PIC_GHOST + k])


def step_and_draw_entity(w, i, d=None):
    """StepAndDrawEntity $B902: one step in the direction d (default EntityDir: 1 up 2 down 4 left 8 right; 1 pixel sideways, 2 vertically, none while DrawOnly is set) and the ghost's picture; another direction does neither"""
    d = w.EntityDir[i] if d is None else d
    if d not in DIR_OFFSET:
        return
    if not w.DrawOnly:
        if d == 1:
            w.EntityY[i] = (w.EntityY[i] - 2) & 0xFF
        elif d == 2:
            w.EntityY[i] = (w.EntityY[i] + 2) & 0xFF
        elif d == 4:
            w.EntityX[i] = (w.EntityX[i] - 1) & 0xFF
        else:
            w.EntityX[i] = (w.EntityX[i] + 1) & 0xFF
    draw_ghost(w, i, DIR_OFFSET[d])


# ------------------------------------------------------------------------------------------------ Pac-Man
def draw_pacman(w, y, a):
    """MovePacMan $B2E9: Y = twice the index of the picture in PacShapePtrs (0 full disc, 2 right, 4 left, 6 up, 8 down), A = the offset of the mouth frame (0 or $0A)"""
    ptr = (rom_word(PAC_SHAPE_PTRS + y) + a) & 0xFFFF
    for k in range(10):
        w.picbuf[PIC_PAC + 3 + k] = rom(ptr + k)
    dst = 0x2300 | w.EntityY[4]
    pacx = w.EntityX[4]
    # clc; HPOSM3 = PacX; adc #2 -> HPOSM2; adc #2 -> HPOSM1; adc #2 -> HPOSM0 (the carry of one add goes into the next)
    v = pacx
    c = 0
    w.hpos[7] = v
    for slot in (6, 5, 4):
        t = v + 2 + c
        v, c = t & 0xFF, t >> 8
        w.hpos[slot] = v
    for k in range(16):
        _put(w, dst + k, w.picbuf[PIC_PAC + k])


def draw_pacman_full(w):
    """MovePacMan $B2CE: the full disc"""
    draw_pacman(w, 0, 0)


def draw_all_in_place(w):
    """DrawAllInPlace $AD49: DrawOnly set, the four ghosts drawn where they stand, DrawOnly cleared, Pac-Man's full disc"""
    w.DrawOnly = 1
    for x in (3, 2, 1, 0):
        step_and_draw_entity(w, x, w.EntityDir[x])
    w.DrawOnly = 0
    draw_pacman_full(w)


# ------------------------------------------------------------------------------------------------ the pop-up of an eaten ghost
def draw_popup(w, x):
    """GhostEaten $A886-$A8EA, the picture part: the positions of the four missiles and of the ghost's player round Pac-Man and the 16 rows of the score picture (missile page) and of the zeros (the ghost's player page) at
    PacY (+-2 towards the ghost's row)"""
    pacx = w.EntityX[4]
    t = pacx - 4
    a, c = t & 0xFF, 1 if t >= 0 else 0                  # sec; sbc #4: the carry is 1 when there was no borrow
    w.hpos[7] = a
    c = 0                                                # clc
    for slot in (6, 5, 4):                               # ldy #2 .. 0: sta HPOSM0,y
        t = a + 2 + c
        a, c = t & 0xFF, t >> 8
        w.hpos[slot] = a
    t = a + 2 + c
    w.hpos[x] = t & 0xFF
    py, ey = w.EntityY[4], w.EntityY[x]
    a = py if py == ey else ((py + 2) if py < ey else (py - 2)) & 0xFF
    n = (w.GhostsEaten * 2) & 0xFF
    src = rom_word(GHOST_SCORE_PTRS + n)
    mptr = 0x2300 | a
    pptr = (((x + 0x24) & 0xFF) << 8) | a
    for k in range(15, -1, -1):
        _put(w, mptr + k, rom(src + k))
        _put(w, pptr + k, rom(GHOST_SCORE_ZEROS + k))


# ------------------------------------------------------------------------------------------------ the death
def death_animation_draw(w):
    """DeathAnimation $AEF7 picture part: called with DeathAnimActive set; the frame is DeathAnimFrame after the counters of core_sound.death_animation have run"""
    base = 0x2300 | w.EntityY[4]
    f = w.DeathAnimFrame
    if f == 0:
        for k in range(9, -1, -1):
            _put(w, base + 3 + k, rom(PAC_SHAPE_UP2 + k))
    elif f == 0x0F:
        for k in range(15, -1, -1):
            _put(w, base + k, rom(STAR_SHAPE + k))
    else:
        x = (f - 1) & 0xFF
        row = (T.ram(DEATH_PLOT_ROWS + x) - 1) & 0xFF
        _put(w, base + row, rom(DEATH_PLOT_BYTES + x))


def death_animation_clear(w):
    """DeathAnimation $AF48: the last step clears the 16 rows"""
    base = 0x2300 | w.EntityY[4]
    for k in range(16):
        _put(w, base + k, 0)


# ------------------------------------------------------------------------------------------------ the tunnel
def clip_entity_at_tunnel(w, x, a):
    """ClipEntityAtTunnel $AB57 (A = the value the caller holds: EntityY = $74): the 16 rows of entity x at the tunnel row are masked so that the picture is cut at the mouth of the tunnel; an entity that has gone round
    wraps to the other mouth (Pac-Man's maze pointer too)"""
    w.ClipPtr[0] = a & 0xFF
    w.ClipPtr[1] = (((0xFF if x == 4 else x) + 0x24) & 0xFF)
    w.ClipMask = 0xFF
    ex = w.EntityX[x]
    w.ClipCounter = ex
    done = False
    if ex >= 0xC0:
        while True:
            if 0xC0 == w.ClipCounter:
                break
            w.ClipCounter = (w.ClipCounter - 1) & 0xFF
            c = w.ClipMask >> 7
            w.ClipMask = (w.ClipMask << 1) & 0xFF
            if c:
                continue
            if w.EntityX[x] >= 0xCA and w.EntityDir[x] == 8:
                w.EntityX[x] = 0x2A
                if x == 4:
                    w.MazePtr[0] = 0x8F
            break
    else:
        if ex >= 0x39:
            return                                       # not at a mouth: no masking
        while True:
            if 0x38 == w.ClipCounter:
                break
            w.ClipCounter = (w.ClipCounter + 1) & 0xFF
            c = w.ClipMask & 1
            w.ClipMask >>= 1
            if c:
                continue
            if w.EntityX[x] == 0x2A and w.EntityDir[x] == 4:
                w.EntityX[x] = 0xCA
                if x == 4:
                    w.MazePtr[0] = 0xB7
            break
    base = w.ClipPtr[1] << 8 | w.ClipPtr[0]
    for k in range(15, -1, -1):
        _put(w, base + k, _get(w, base + k) & w.ClipMask)
    return done


def clip_entities_on_tunnel_row(w):
    """ClipEntitiesOnTunnelRow $AB48: every entity (Pac-Man 4 first, then the ghosts 3 .. 0) on row $74"""
    for x in range(4, -1, -1):
        if w.EntityY[x] == 0x74:
            clip_entity_at_tunnel(w, x, 0x74)


# ------------------------------------------------------------------------------------------------ clearing
def fill_player_pages(w, a, x):
    """FillPlayerPages $B100 with A and X: the byte A into rows X .. $FF of all five pages"""
    for r in range(x, 0x100):
        for p in range(5):
            w.pm[p * 0x100 + r] = a & 0xFF


def clear_player_memory(w):
    """ClearPlayerMemory $B0F1: all five pages to 0, then rows $F0-$FF of each to $FE"""
    fill_player_pages(w, 0, 0)
    fill_player_pages(w, 0xFE, 0xF0)


# ------------------------------------------------------------------------------------------------ the scene for the collision model
def scene(w, charset):
    """the scene the GTIA shows after a frame, for tools/gtia_collisions.py (docs/50): (the eight positions, the missile page, the four player pages, the playfield of the maze band); `charset` = the 1,024 bytes of the game
    character set (the asset pack, docs/47)"""
    import gtia_collisions as G
    pages = [w.pm[i * 0x100:(i + 1) * 0x100] for i in range(5)]
    return list(w.hpos), pages[0], pages[1:], G.Playfield(list(w.maze[:G.MAZE_ROWS * G.MAZE_COLS]), charset)

