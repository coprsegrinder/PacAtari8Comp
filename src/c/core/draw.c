/* core/draw.c - the drawing (stage 76b: the part the ghosts need).  Twin of tools/core_draw.py: read the two side by side. */
#include "draw.h"

#include "tables.h"
#include "constants.h"

#define GHOST_SHAPES 0xBAC0

uint8_t draw_rom(int32_t addr)
{
    addr &= 0xFFFF;
    return (addr >= 0xBA00 && addr < 0xC000) ? table_rom((uint16_t)addr) : 0;
}

uint16_t draw_rom_word(int32_t addr)
{
    return (uint16_t)(draw_rom(addr) | (draw_rom(addr + 1) << 8));
}

void draw_put(World *w, int32_t addr, uint8_t v)
{
    int32_t i = addr - 0x2300;
    if (i >= 0 && i < DRAW_PM_LEN) {
        w->pm[i] = v;
    }
}

uint8_t draw_get(const World *w, int32_t addr)
{
    int32_t i = addr - 0x2300;
    return (i >= 0 && i < DRAW_PM_LEN) ? w->pm[i] : 0;
}

void draw_ghost(World *w, int x, int a)
{
    uint8_t st = w->GhostState[x];
    uint8_t feet;
    int32_t dst, src;
    int k;

    if (st & GS_FRIGHTENED_BIT) {
        a = 0x28;                                  /* frightened */
    }
    if (st & 0x40) {
        a = 0x32;                                  /* eyes only: no feet row */
        feet = 0;
    } else {
        feet = w->LegPhase ? 0xAA : 0x54;
    }
    w->picbuf[0x1C] = feet;
    src = GHOST_SHAPES + a;
    for (k = 0; k < 10; k++) {
        w->picbuf[0x12 + k] = draw_rom(src + k);
    }
    w->hpos[x] = w->EntityX[x];
    dst = (int32_t)((((unsigned)CLIP_PAGE_OFFSET + (unsigned)x) & 0xFFu) << 8) | w->EntityY[x];
    for (k = 0; k < 16; k++) {
        draw_put(w, dst + k, w->picbuf[DRAW_PIC_GHOST + k]);
    }
}

void step_and_draw_entity(World *w, int i, int32_t d)
{
    int offset;
    switch (d) {
    case 1: offset = 0x00; break;
    case 2: offset = 0x0A; break;
    case 4: offset = 0x14; break;
    case 8: offset = 0x1E; break;
    default: return;
    }
    if (!w->DrawOnly) {
        if (d == 1) {
            w->EntityY[i] = (uint8_t)(w->EntityY[i] - 2u);
        } else if (d == 2) {
            w->EntityY[i] = (uint8_t)(w->EntityY[i] + 2u);
        } else if (d == 4) {
            w->EntityX[i] = (uint8_t)(w->EntityX[i] - 1u);
        } else {
            w->EntityX[i] = (uint8_t)(w->EntityX[i] + 1u);
        }
    }
    draw_ghost(w, i, offset);
}

/* ------------------------------------------------------------------------------------------------ Pac-Man (76c) */
#define PAC_SHAPE_PTRS 0xBB65
#define GHOST_SCORE_ZEROS 0xBC13
#define GHOST_SCORE_PTRS 0xBCD0
#define PAC_SHAPE_UP2 0xBB38
#define STAR_SHAPE 0xBC07
#define DEATH_PLOT_BYTES 0xBB57
#define DEATH_PLOT_ROWS 0x0600

void draw_pacman(World *w, int32_t y, int32_t a)
{
    int32_t ptr = ((int32_t)draw_rom_word(PAC_SHAPE_PTRS + y) + a) & 0xFFFF;
    int32_t dst;
    uint32_t v, t, c;
    int k;
    static const int slots[3] = {6, 5, 4};

    for (k = 0; k < 10; k++) {
        w->picbuf[DRAW_PIC_PAC + 3 + k] = draw_rom(ptr + k);
    }
    dst = 0x2300 | w->EntityY[4];
    /* clc; HPOSM3 = PacX; adc #2 -> HPOSM2; adc #2 -> HPOSM1; adc #2 -> HPOSM0 (the carry of one add goes into the next) */
    v = w->EntityX[4];
    c = 0;
    w->hpos[7] = (uint8_t)v;
    for (k = 0; k < 3; k++) {
        t = v + 2u + c;
        v = t & 0xFFu;
        c = t >> 8;
        w->hpos[slots[k]] = (uint8_t)v;
    }
    for (k = 0; k < 16; k++) {
        draw_put(w, dst + k, w->picbuf[DRAW_PIC_PAC + k]);
    }
}

void draw_pacman_full(World *w)
{
    draw_pacman(w, 0, 0);
}

void draw_all_in_place(World *w)
{
    int x;
    w->DrawOnly = 1;
    for (x = 3; x >= 0; x--) {
        step_and_draw_entity(w, x, w->EntityDir[x]);
    }
    w->DrawOnly = 0;
    draw_pacman_full(w);
}

/* ------------------------------------------------------------------------------------------------ the pop-up of an eaten ghost */
void draw_popup(World *w, int x)
{
    uint32_t a, t, c;
    int k;
    int32_t py, ey, src, mptr, pptr;
    int n;
    static const int slots[3] = {6, 5, 4};

    a = ((uint32_t)w->EntityX[4] - 4u) & 0xFFu;
    w->hpos[7] = (uint8_t)a;
    c = 0;
    for (k = 0; k < 3; k++) {
        t = a + 2u + c;
        a = t & 0xFFu;
        c = t >> 8;
        w->hpos[slots[k]] = (uint8_t)a;
    }
    t = a + 2u + c;
    w->hpos[x] = (uint8_t)(t & 0xFFu);
    py = w->EntityY[4];
    ey = w->EntityY[x];
    if (py == ey) {
        a = (uint32_t)py;
    } else if (py < ey) {
        a = (uint32_t)(py + 2) & 0xFFu;
    } else {
        a = (uint32_t)(py - 2) & 0xFFu;
    }
    n = (w->GhostsEaten * 2) & 0xFF;
    src = draw_rom_word(GHOST_SCORE_PTRS + n);
    mptr = 0x2300 | (int32_t)a;
    pptr = (int32_t)((((unsigned)x + 0x24u) & 0xFFu) << 8) | (int32_t)a;
    for (k = 15; k >= 0; k--) {
        draw_put(w, mptr + k, draw_rom(src + k));
        draw_put(w, pptr + k, draw_rom(GHOST_SCORE_ZEROS + k));
    }
}

/* ------------------------------------------------------------------------------------------------ the death */
void death_animation_draw(World *w)
{
    int32_t base = 0x2300 | w->EntityY[4];
    int f = w->DeathAnimFrame;
    int k;

    if (f == 0) {
        for (k = 9; k >= 0; k--) {
            draw_put(w, base + 3 + k, draw_rom(PAC_SHAPE_UP2 + k));
        }
    } else if (f == 0x0F) {
        for (k = 15; k >= 0; k--) {
            draw_put(w, base + k, draw_rom(STAR_SHAPE + k));
        }
    } else {
        int x = (f - 1) & 0xFF;
        int row = (table_ram((uint16_t)(DEATH_PLOT_ROWS + x)) - 1) & 0xFF;
        draw_put(w, base + row, draw_rom(DEATH_PLOT_BYTES + x));
    }
}

void death_animation_clear(World *w)
{
    int32_t base = 0x2300 | w->EntityY[4];
    int k;
    for (k = 0; k < 16; k++) {
        draw_put(w, base + k, 0);
    }
}

/* ------------------------------------------------------------------------------------------------ the tunnel */
void clip_entity_at_tunnel(World *w, int x, uint8_t a)
{
    int ex, c, k;
    int32_t base;

    w->ClipPtr[0] = a;
    w->ClipPtr[1] = (uint8_t)(((x == 4 ? 0xFF : x) + CLIP_PAGE_OFFSET) & 0xFF);
    w->ClipMask = 0xFF;
    ex = w->EntityX[x];
    w->ClipCounter = (uint8_t)ex;
    if (ex >= 0xC0) {
        for (;;) {
            if (w->ClipCounter == 0xC0) {
                break;
            }
            w->ClipCounter = (uint8_t)(w->ClipCounter - 1u);
            c = w->ClipMask >> 7;
            w->ClipMask = (uint8_t)(w->ClipMask << 1);
            if (c) {
                continue;
            }
            if (w->EntityX[x] >= TUNNEL_X_RIGHT && w->EntityDir[x] == DIR_RIGHT) {
                w->EntityX[x] = TUNNEL_X_LEFT;
                if (x == 4) {
                    w->MazePtr[0] = MAZE_PTR_RIGHT_EXIT_LO;
                }
            }
            break;
        }
    } else {
        if (ex >= 0x39) {
            return;                                        /* not at a mouth: no masking */
        }
        for (;;) {
            if (w->ClipCounter == 0x38) {
                break;
            }
            w->ClipCounter = (uint8_t)(w->ClipCounter + 1u);
            c = w->ClipMask & 1;
            w->ClipMask = (uint8_t)(w->ClipMask >> 1);
            if (c) {
                continue;
            }
            if (w->EntityX[x] == TUNNEL_X_LEFT && w->EntityDir[x] == DIR_LEFT) {
                w->EntityX[x] = TUNNEL_X_RIGHT;
                if (x == 4) {
                    w->MazePtr[0] = MAZE_PTR_LEFT_EXIT_LO;
                }
            }
            break;
        }
    }
    base = (int32_t)(w->ClipPtr[1] << 8) | w->ClipPtr[0];
    for (k = 15; k >= 0; k--) {
        draw_put(w, base + k, (uint8_t)(draw_get(w, base + k) & w->ClipMask));
    }
}

void clip_entities_on_tunnel_row(World *w)
{
    int x;
    for (x = 4; x >= 0; x--) {
        if (w->EntityY[x] == TUNNEL_Y) {
            clip_entity_at_tunnel(w, x, TUNNEL_Y);
        }
    }
}

/* ------------------------------------------------------------------------------------------------ clearing */
void fill_player_pages(World *w, uint8_t a, int x)
{
    int r, p;
    for (r = x; r < 0x100; r++) {
        for (p = 0; p < 5; p++) {
            w->pm[p * 0x100 + r] = a;
        }
    }
}

void clear_player_memory(World *w)
{
    fill_player_pages(w, 0, 0);
    fill_player_pages(w, 0xFE, 0xF0);
}
