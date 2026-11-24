/* core/gtia.c - the collision geometry of the GTIA (stage 77a).  Twin of tools/gtia_collisions.py: read the two side by side. */
#include "gtia.h"

#include <string.h>

#define CLOCKS 272   /* clock positions: HPOS 0-255 plus a player's 8 pixels */

/* the playfield colour register bit (0-3) a pixel at (scan line, colour clock) has, or -1 (background, or outside the maze band) */
static int pf_bit(const GtiaScene *s, int line, int clock)
{
    int x, row, sub, col, k, code, v;

    if (line < GTIA_MAZE_LINE0 || line >= GTIA_MAZE_LINE0 + 8 * GTIA_MAZE_ROWS) {
        return -1;
    }
    x = clock - GTIA_SCREEN_X0;
    if (x < 0 || x >= 4 * GTIA_MAZE_COLS) {
        return -1;
    }
    row = (line - GTIA_MAZE_LINE0) / 8;
    sub = (line - GTIA_MAZE_LINE0) % 8;
    col = x / 4;
    k = x % 4;
    code = s->cells[row * GTIA_MAZE_COLS + col];
    v = (s->charset[(code & 0x7F) * 8 + sub] >> (6 - 2 * k)) & 3;
    if (v == 0) {
        return -1;
    }
    if (v == 3) {
        return (code & 0x80) ? 3 : 2;
    }
    return v - 1;
}

void gtia_collision_registers(const GtiaScene *s, int visible_lo, int visible_hi, int line_lo, int line_hi, uint8_t out[16])
{
    uint8_t mpf[4] = {0, 0, 0, 0}, ppf[4] = {0, 0, 0, 0}, mpl[4] = {0, 0, 0, 0}, ppl[4] = {0, 0, 0, 0};
    uint8_t miss[CLOCKS], play[CLOCKS];
    int line, m, p, q, j, k, clock, pf, i;

    for (line = line_lo; line <= line_hi; line++) {
        int mb = s->missile_page[line];
        int pbs[4];
        pbs[0] = s->player_pages[0][line];
        pbs[1] = s->player_pages[1][line];
        pbs[2] = s->player_pages[2][line];
        pbs[3] = s->player_pages[3][line];
        if (!mb && !pbs[0] && !pbs[1] && !pbs[2] && !pbs[3]) {
            continue;
        }
        /* the pixels of this line: clock -> (set of missiles, set of players) */
        memset(miss, 0, sizeof miss);
        memset(play, 0, sizeof play);
        for (m = 0; m < 4; m++) {
            int two = (mb >> (2 * m)) & 3;
            for (k = 0; k < 2; k++) {
                clock = s->hpos[4 + m] + k;
                if ((two & (2 >> k)) && visible_lo <= clock && clock <= visible_hi) {      /* bit 2m+1 is the left pixel */
                    miss[clock] = (uint8_t)(miss[clock] | (1 << m));
                }
            }
        }
        for (p = 0; p < 4; p++) {
            for (j = 0; j < 8; j++) {
                clock = s->hpos[p] + j;
                if ((pbs[p] & (0x80 >> j)) && visible_lo <= clock && clock <= visible_hi) {
                    play[clock] = (uint8_t)(play[clock] | (1 << p));
                }
            }
        }
        for (clock = 0; clock < CLOCKS; clock++) {
            if (miss[clock]) {
                pf = pf_bit(s, line, clock);
                for (m = 0; m < 4; m++) {
                    if (miss[clock] & (1 << m)) {
                        if (pf >= 0) {
                            mpf[m] = (uint8_t)(mpf[m] | (1 << pf));
                        }
                        for (p = 0; p < 4; p++) {
                            if (play[clock] & (1 << p)) {
                                mpl[m] = (uint8_t)(mpl[m] | (1 << p));
                            }
                        }
                    }
                }
            }
            if (play[clock]) {
                pf = pf_bit(s, line, clock);
                for (p = 0; p < 4; p++) {
                    if (play[clock] & (1 << p)) {
                        if (pf >= 0) {
                            ppf[p] = (uint8_t)(ppf[p] | (1 << pf));
                        }
                        for (q = 0; q < 4; q++) {
                            if (q != p && (play[clock] & (1 << q))) {
                                ppl[p] = (uint8_t)(ppl[p] | (1 << q));
                            }
                        }
                    }
                }
            }
        }
    }
    for (i = 0; i < 4; i++) {
        out[i] = mpf[i];
        out[4 + i] = ppf[i];
        out[8 + i] = mpl[i];
        out[12 + i] = ppl[i];
    }
}

void gtia_scene_of_world(const World *w, const uint8_t charset[GTIA_CHARSET_SIZE], GtiaScene *s)
{
    s->hpos = w->hpos;
    s->missile_page = w->pm;
    s->player_pages[0] = w->pm + 0x100;
    s->player_pages[1] = w->pm + 0x200;
    s->player_pages[2] = w->pm + 0x300;
    s->player_pages[3] = w->pm + 0x400;
    s->cells = w->maze;                       /* the first 920 cells are the maze band */
    s->charset = charset;
}

void gtia_latch_init(GtiaLatch *l)
{
    memset(l->reg, 0, sizeof l->reg);
}

void gtia_latch_frame_done(GtiaLatch *l, const World *w, const uint8_t charset[GTIA_CHARSET_SIZE])
{
    GtiaScene s;
    uint8_t shown[16];
    uint32_t k;
    int i;

    for (k = 0; k < w->pokey_n; k++) {
        if (w->pokey_addr[k] == 0xD01E) {
            gtia_latch_init(l);
            break;
        }
    }
    gtia_scene_of_world(w, charset, &s);
    gtia_collision_registers(&s, GTIA_VISIBLE_LO, GTIA_VISIBLE_HI, GTIA_LINE_LO, GTIA_LINE_HI, shown);
    for (i = 0; i < 16; i++) {
        l->reg[i] = (uint8_t)(l->reg[i] | shown[i]);
    }
}

void gtia_latch_to_world(const GtiaLatch *l, World *w)
{
    memcpy(w->collide, l->reg, sizeof w->collide);
}
