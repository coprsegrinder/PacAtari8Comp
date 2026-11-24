/* core/pacman.c - Pac-Man's movement (stage 76c).  Twin of tools/core_pacman.py: read the two side by side. */
#include "pacman.h"

#include "draw.h"
#include "ref.h"
#include "tables.h"
#include "constants.h"

#define PAC_MOUTH_OFFSETS 0xBB55

static int32_t get_ptr(const World *w)
{
    return w->MazePtr[0] | (w->MazePtr[1] << 8);
}

static void set_ptr(World *w, int32_t v)
{
    v &= 0xFFFF;
    w->MazePtr[0] = (uint8_t)(v & 0xFF);
    w->MazePtr[1] = (uint8_t)(v >> 8);
}

void read_joystick(World *w, uint8_t mask)
{
    uint8_t a = (uint8_t)((w->stick[w->CurrentPlayer] ^ 0x0Fu) & 0xFFu);
    int bits;

    if (a == 0) {
        return;
    }
    bits = (a & 1) + ((a >> 1) & 1) + ((a >> 2) & 1) + ((a >> 3) & 1);
    if (bits == 2) {
        return;                                     /* a diagonal (two directions) is ignored */
    }
    w->ATRACT = a;                                  /* any stick input resets the attract-mode timer */
    w->PacWantedDir = a;
    if (a & mask) {
        w->EntityDir[4] = a;
    }
}

/* one step of 1 pixel sideways or 2 pixels vertically, with the sub-cell counter (0-3) and the maze pointer; held (PacHold) -> no step */
static void step(World *w, int d)
{
    if (w->PacHold) {
        return;
    }
    if (d == 1) {
        w->EntityY[4] = (uint8_t)(w->EntityY[4] - 2u);
        if (w->PacSubY == 0) {
            w->PacSubY = 3;
        } else {
            w->PacSubY = (uint8_t)(w->PacSubY - 1u);
            if (w->PacSubY == 0 && w->EntityY[4] != w->LastCellY) {
                set_ptr(w, get_ptr(w) - PACMAN_ROW);
            }
        }
    } else if (d == 2) {
        w->EntityY[4] = (uint8_t)(w->EntityY[4] + 2u);
        if (w->PacSubY == 3) {
            w->PacSubY = 0;
            if (w->EntityY[4] != w->LastCellY) {
                set_ptr(w, get_ptr(w) + PACMAN_ROW);
            }
        } else {
            w->PacSubY = (uint8_t)(w->PacSubY + 1u);
        }
    } else if (d == 8) {
        if (w->EntityX[4] == PACMAN_TUNNEL_RIGHT) {
            w->EntityX[4] = PACMAN_TUNNEL_LEFT;
            w->MazePtr[0] = PACMAN_MAZE_PTR_AFTER_RIGHT;
        }
        w->EntityX[4] = (uint8_t)(w->EntityX[4] + 1u);
        if (w->PacSubX == 3) {
            w->PacSubX = 0;
            if (w->EntityX[4] != w->LastCellX) {
                set_ptr(w, get_ptr(w) + 1);
            }
        } else {
            w->PacSubX = (uint8_t)(w->PacSubX + 1u);
        }
    } else if (d == 4) {
        if (w->EntityX[4] == PACMAN_TUNNEL_LEFT) {
            w->EntityX[4] = PACMAN_TUNNEL_RIGHT;
            w->MazePtr[0] = PACMAN_MAZE_PTR_AFTER_LEFT;
        }
        w->EntityX[4] = (uint8_t)(w->EntityX[4] - 1u);
        if (w->PacSubX == 0) {
            w->PacSubX = 3;
        } else {
            w->PacSubX = (uint8_t)(w->PacSubX - 1u);
            if (w->PacSubX == 0 && w->EntityX[4] != w->LastCellX) {
                set_ptr(w, get_ptr(w) - 1);
            }
        }
    }
}

/* the index (twice) of the direction's pictures in PacShapePtrs; -1 for a value that is not a direction */
static int picture_of(int d)
{
    switch (d) {
    case DIR_UP: return 6;
    case DIR_DOWN: return 8;
    case DIR_LEFT: return 4;
    case DIR_RIGHT: return 2;
    default: return -1;
    }
}

void move_pacman(World *w)
{
    int on, d, pic;
    uint8_t mask, both, c;

    if (w->PacFrozen & 0x80) {
        return;
    }
    mask = ref_junction_exits(1, w->EntityX[4], w->EntityY[4], w->EntityDir[4], 0, &on);
    if (w->PacWantedDir & mask) {                    /* a remembered turn that is possible here: take it */
        if (w->PacWantedDir != w->EntityDir[4]) {
            both = (uint8_t)(w->PacWantedDir | w->EntityDir[4]);
            if ((both & (DIR_UP | DIR_DOWN)) && (both & (DIR_LEFT | DIR_RIGHT))) {    /* a turn across (vertical <-> horizontal): the cornering flag */
                w->PacCornering = both;
            }
        }
        w->EntityDir[4] = w->PacWantedDir;
    }
    read_joystick(w, mask);
    d = w->EntityDir[4];
    pic = picture_of(d);
    if (!(d & mask)) {                               /* blocked: no step, the wide-open mouth frame ($0A) of the direction */
        if (pic >= 0) {
            draw_pacman(w, pic, 0x0A);
        } else {
            draw_pacman_full(w);
        }
        return;
    }
    if (pic < 0) {
        draw_pacman_full(w);
        return;
    }
    step(w, d);
    c = w->ChompPhase;                               /* the mouth: 0 closed (the full disc), 1 and 3 the first frame, 2 the second; 3 is followed by 0 */
    if (c == 0) {
        w->ChompPhase = 1;
        draw_pacman_full(w);
    } else {
        draw_pacman(w, pic, table_rom((uint16_t)(PAC_MOUTH_OFFSETS + c - 1)));
        w->ChompPhase = c == 3 ? 0 : (uint8_t)(c + 1u);
    }
}
