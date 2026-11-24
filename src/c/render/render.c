/* render/render.c - see render.h. */
#include "render.h"

#include <string.h>

#include "../core/tables.h"
#include "palette.h"

#define DL_GAME_HANDLER 0xA573u   /* DliHandler1 */
#define DL_TITLE_HANDLER 0xA5CEu  /* DliHandler2 */
#define DLI_CHBASE_TABLE 0xBDD1u  /* DliChbaseTable */

#define PF_X0 ((48 - RENDER_FIRST_CLOCK) * 2)   /* the playfield (normal width, 160 clocks) starts at colour clock 48 */
#define PF_W 320

enum { REG_PF0 = 0, REG_PF1, REG_PF2, REG_PF3, REG_BK, REG_PM0, REG_PM1, REG_PM2, REG_PM3 };

typedef struct Regs {
    uint8_t c[9];    /* COLPF0-3, COLBK, COLPM0-3 */
    uint8_t chbase;
} Regs;

/* ---- memory the screen is fetched from ---- */

static uint8_t screen_byte(const World *w, unsigned a)
{
    a &= 0xFFFFu;
    if (a >= 0x0C00u && a < 0x1000u) {
        return w->maze[a - 0x0C00u];
    }
    if (a >= 0x1C00u && a < 0x2000u) {
        return w->title[a - 0x1C00u];
    }
    if (a >= 0x2000u && a < 0x2050u) {
        return w->status[a - 0x2000u];
    }
    if (a >= 0x0800u && a < 0x0C00u) {
        return w->maze_orig[a - 0x0800u];
    }
    return 0;
}

static uint8_t dl_byte(unsigned a)
{
    a &= 0xFFFFu;
    return (a >= 0xBA00u && a < 0xC000u) ? table_rom((uint16_t)a) : 0;
}

static uint8_t chargen_byte(const Renderer *r, unsigned a)
{
    if (a >= 0x1800u && a < 0x1C00u) {
        return r->chargen_title[a - 0x1800u];
    }
    if (a >= 0x3000u && a < 0x3400u) {
        return r->chargen_game[a - 0x3000u];
    }
    if (a >= 0xE000u && a < 0xE400u) {
        return r->chargen_font[a - 0xE000u];
    }
    return 0;
}

/* ---- the colour registers ---- */

static uint8_t chip_colour(const World *w, uint8_t shadow)
{
    return (uint8_t)((shadow ^ w->COLRSH) & w->DRKMSK);
}

static void take_shadows(const World *w, uint8_t c[9], uint8_t *chbase)
{
    int k;

    for (k = 0; k < 5; k++) {
        c[k] = chip_colour(w, w->shadow[0xC4 + k]);        /* COLOR0-4 */
    }
    for (k = 0; k < 4; k++) {
        c[5 + k] = chip_colour(w, w->shadow[0xC0 + k]);    /* PCOLR0-3 */
    }
    /* CHBAS ($02F4): the game never writes it; the OS sets it to $E0 (its own font) at reset, and the status rows are drawn with that font until the first interrupt of the frame.  The World starts from
     * a power-on RAM without the OS reset, so its shadow is 0: use the OS value (a game that did write CHBAS would be honoured by a non-zero shadow). */
    *chbase = w->shadow[0xF4] != 0 ? w->shadow[0xF4] : 0xE0;
}

/* what the display-list interrupt handlers of the game write after their WSYNC (docs/35, src/asm/pacman.s $A573-$A5FC); `band` is BandCounter */
static void dli_effect(const World *w, unsigned handler, int band, Regs *g)
{
    if (handler == DL_GAME_HANDLER) {
        switch (band) {
        case 0:
            g->chbase = 0x30;
            break;
        case 1:
            g->c[REG_PF1] = chip_colour(w, w->ItemColor);
            g->c[REG_PF2] = w->DliColors[0];
            break;
        case 2:
            g->c[REG_PF1] = w->DliColors[1];
            break;
        case 3:
            g->c[REG_PF0] = w->DliColors[3];
            g->c[REG_PF3] = w->DliColors[2];
            break;
        default:                                            /* the last band: COLPM3..COLPM0 and COLPF3 := 0 (X = band - 1 counts down to 0) */
            {
                int x;
                for (x = band - 1; x >= 0 && x <= 3; x--) {
                    g->c[REG_PM0 + x] = 0;
                }
                g->c[REG_PF3] = 0;
            }
            break;
        }
    } else if (handler == DL_TITLE_HANDLER) {
        if (band == 0) {
            g->chbase = 0x18;
            g->c[REG_PF2] = w->DliColors[0];
            g->c[REG_PF1] = w->DliColors[1];
        } else {
            g->chbase = table_rom((uint16_t)(DLI_CHBASE_TABLE + (unsigned)band));
        }
    }
}

/* ---- one scan line of the playfield ---- */

typedef struct Line {
    uint8_t pri[RENDER_W];   /* 0 background, 1-4 playfield 0-3 */
    uint8_t col[RENDER_W];   /* the colour byte of a playfield pixel */
} Line;

static void put2(Line *l, int clock, uint8_t pri, uint8_t col)    /* one colour clock = two pixels */
{
    int x = PF_X0 + clock * 2;

    if (x >= 0 && x + 1 < RENDER_W) {
        l->pri[x] = l->pri[x + 1] = pri;
        l->col[x] = l->col[x + 1] = col;
    }
}

static void put1(Line *l, int hx, uint8_t pri, uint8_t col)       /* one hires pixel */
{
    int x = PF_X0 + hx;

    if (x >= 0 && x < RENDER_W) {
        l->pri[x] = pri;
        l->col[x] = col;
    }
}

static void playfield_line(const Renderer *r, const World *w, const Regs *g, int mode, unsigned mp, int row_line, Line *l)
{
    int i, b;
    uint8_t chact = w->shadow[0xF3];

    if (mode == 2) {
        unsigned base = (unsigned)(g->chbase & 0xFCu) << 8;
        for (i = 0; i < 40; i++) {
            uint8_t code = screen_byte(w, mp + (unsigned)i);
            unsigned glyph = code & 0x7Fu;
            int ln = (chact & 4u) ? 7 - row_line : row_line;
            uint8_t bits = chargen_byte(r, base + glyph * 8u + (unsigned)ln);
            if (code & 0x80u) {
                if (chact & 2u) {
                    bits = (uint8_t)~bits;
                }
                if (chact & 1u) {
                    bits = 0;
                }
            }
            for (b = 0; b < 8; b++) {
                int on = (bits >> (7 - b)) & 1;
                if (on) {          /* hue of COLPF2, luminance of COLPF1 */
                    put1(l, i * 8 + b, 2, (uint8_t)((g->c[REG_PF2] & 0xF0u) | (g->c[REG_PF1] & 0x0Fu)));
                } else {
                    put1(l, i * 8 + b, 3, g->c[REG_PF2]);
                }
            }
        }
    } else if (mode == 4) {
        unsigned base = (unsigned)(g->chbase & 0xFCu) << 8;
        for (i = 0; i < 40; i++) {
            uint8_t code = screen_byte(w, mp + (unsigned)i);
            uint8_t bits = chargen_byte(r, base + (unsigned)(code & 0x7Fu) * 8u + (unsigned)row_line);
            for (b = 0; b < 4; b++) {
                int v = (bits >> (6 - 2 * b)) & 3;
                uint8_t pri, col;
                switch (v) {
                case 0: pri = 0; col = g->c[REG_BK]; break;
                case 1: pri = 1; col = g->c[REG_PF0]; break;
                case 2: pri = 2; col = g->c[REG_PF1]; break;
                default:
                    if (code & 0x80u) { pri = 4; col = g->c[REG_PF3]; } else { pri = 3; col = g->c[REG_PF2]; }
                    break;
                }
                put2(l, i * 4 + b, pri, col);
            }
        }
    } else if (mode == 6 || mode == 7) {
        unsigned base = (unsigned)(g->chbase & 0xFEu) << 8;
        int gl = mode == 7 ? row_line / 2 : row_line;
        for (i = 0; i < 20; i++) {
            uint8_t code = screen_byte(w, mp + (unsigned)i);
            uint8_t bits = chargen_byte(r, base + (unsigned)(code & 0x3Fu) * 8u + (unsigned)gl);
            int reg = (code >> 6) & 3;
            for (b = 0; b < 8; b++) {
                if ((bits >> (7 - b)) & 1) {
                    put2(l, i * 8 + b, (uint8_t)(reg + 1), g->c[reg]);
                } else {
                    put2(l, i * 8 + b, 0, g->c[REG_BK]);
                }
            }
        }
    }
}

/* ---- the players and missiles, and the priority ---- */

#define COV_P(k) (1u << (k))
#define COV_M(k) (1u << (4 + (k)))

static void objects_line(const World *w, int line, uint8_t cov[RENDER_W])
{
    uint8_t dma = w->shadow[0x2F];
    int k, b;

    memset(cov, 0, RENDER_W);
    if (!(dma & 0x10u) || line < 0 || line > 255) {      /* single-line resolution only */
        return;
    }
    if (dma & 0x08u) {
        for (k = 0; k < 4; k++) {
            uint8_t bits = w->pm[(k + 1) * 256 + line];
            for (b = 0; b < 8; b++) {
                if ((bits >> (7 - b)) & 1) {
                    int x = (w->hpos[k] + b - RENDER_FIRST_CLOCK) * 2;
                    if (x >= 0 && x + 1 < RENDER_W) {
                        cov[x] |= (uint8_t)COV_P(k);
                        cov[x + 1] |= (uint8_t)COV_P(k);
                    }
                }
            }
        }
    }
    if (dma & 0x04u) {
        uint8_t m = w->pm[line];
        for (k = 0; k < 4; k++) {
            for (b = 0; b < 2; b++) {                    /* the two bits of a missile, the high one is on the left */
                if ((m >> (2 * k + 1 - b)) & 1) {
                    int x = (w->hpos[4 + k] + b - RENDER_FIRST_CLOCK) * 2;
                    if (x >= 0 && x + 1 < RENDER_W) {
                        cov[x] |= (uint8_t)COV_M(k);
                        cov[x + 1] |= (uint8_t)COV_M(k);
                    }
                }
            }
        }
    }
}

/* the order of the five kinds of thing, highest first (GTIA PRIOR bits 0-3): P0-P3 are players (and their missiles), F0-F3 playfields, 8 = background */
static const char *priority_order(uint8_t prior)
{
    if (prior & 1u) {
        return "0123" "4567";
    }
    if (prior & 2u) {
        return "01" "4567" "23";
    }
    if (prior & 4u) {
        return "4567" "0123";
    }
    if (prior & 8u) {
        return "45" "0123" "67";
    }
    return "0123" "4567";
}

static uint8_t pixel_colour(const Regs *g, uint8_t prior, uint8_t pri, uint8_t col, uint8_t cov)
{
    const char *order = priority_order(prior);
    int five = (prior & 0x10u) != 0;
    int i;

    for (i = 0; i < 8; i++) {
        int t = order[i] - '0';
        if (t < 4) {                                       /* player t (and, without the fifth player, missile t) */
            if ((cov & COV_P(t)) || (!five && (cov & COV_M(t)))) {
                return g->c[REG_PM0 + t];
            }
        } else {                                           /* playfield t - 4 */
            int f = t - 4;
            if (pri == f + 1) {
                return col;
            }
            if (f == 3 && five && (cov & 0xF0u)) {         /* the fifth player: the four missiles with the colour and the rank of playfield 3 */
                return g->c[REG_PF3];
            }
        }
    }
    return g->c[REG_BK];
}

/* ---- the frame ---- */

void render_init(Renderer *r, const uint8_t image[65536])
{
    memset(r, 0, sizeof *r);
    memcpy(r->chargen_title, image + 0x1800, 1024);
    memcpy(r->chargen_game, image + 0x3000, 1024);
    memcpy(r->chargen_font, image + 0xE000, 1024);
}

void render_reset(Renderer *r)
{
    r->have_latched = 0;
}

uint8_t render_compose(const uint8_t regs[9], uint8_t prior, uint8_t pri, uint8_t col, uint8_t cov)
{
    Regs g;

    memcpy(g.c, regs, sizeof g.c);
    g.chbase = 0;
    return pixel_colour(&g, prior, pri, col, cov);
}

void render_frame(Renderer *r, const World *w, uint8_t colour[RENDER_W * RENDER_H])
{
    render_frame_layers(r, w, colour, NULL);
}

void render_frame_layers(Renderer *r, const World *w, uint8_t colour[RENDER_W * RENDER_H], RenderLayers *L)
{
    Regs g;
    Line l;
    uint8_t cov[RENDER_W];
    unsigned dl = (unsigned)w->shadow[0x30] | ((unsigned)w->shadow[0x31] << 8);
    unsigned handler = (unsigned)w->shadow[0x00] | ((unsigned)w->shadow[0x01] << 8);
    uint8_t dma = w->shadow[0x2F];
    uint8_t prior = w->shadow[0x6F];
    int line = RENDER_FIRST_LINE, band = 0, done = 0, guard = 0;
    unsigned mp = 0;
    int y, x;

    /* the colour registers at the start of the frame: the OS copied the shadows of the previous frame in the vertical blank */
    if (r->have_latched) {
        memcpy(g.c, r->latched, sizeof g.c);
        g.chbase = r->latched_chbase;
    } else {
        take_shadows(w, g.c, &g.chbase);
    }
    take_shadows(w, r->latched, &r->latched_chbase);
    r->have_latched = 1;

    for (y = 0; y < RENDER_H; y++) {                       /* an empty screen to start with */
        memset(colour + y * RENDER_W, g.c[REG_BK], RENDER_W);
    }
    if (L != NULL) {
        memset(L->pri, 0, sizeof L->pri);
        memset(L->col, g.c[REG_BK], sizeof L->col);
        memset(L->cov, 0, sizeof L->cov);
        for (y = 0; y < RENDER_H; y++) {
            memcpy(L->regs[y], g.c, sizeof g.c);
        }
        L->prior = prior;
    }

    if (!(dma & 0x20u)) {
        done = 1;                                          /* no display-list DMA: nothing but the background (and no interrupts) */
    }
    while (!done && line < RENDER_FIRST_LINE + RENDER_H && guard++ < 512) {
        uint8_t ins = dl_byte(dl);
        int mode = ins & 0x0F, lines, dli = (ins & 0x80) != 0, ln;
        unsigned n = 0;

        dl = (dl + 1u) & 0xFFFFu;
        if (mode == 1) {                                   /* JMP, or JVB: wait for the vertical blank */
            unsigned target = (unsigned)dl_byte(dl) | ((unsigned)dl_byte(dl + 1u) << 8);
            if (ins & 0x40u) {
                done = 1;
            } else {
                dl = target;
            }
            continue;
        }
        if (mode == 0) {
            lines = ((ins >> 4) & 7) + 1;
        } else {
            if (ins & 0x40u) {
                mp = (unsigned)dl_byte(dl) | ((unsigned)dl_byte(dl + 1u) << 8);
                dl = (dl + 2u) & 0xFFFFu;
            }
            switch (mode) {
            case 2: lines = 8; n = 40; break;
            case 3: lines = 10; n = 40; break;
            case 4: lines = 8; n = 40; break;
            case 5: lines = 16; n = 40; break;
            case 6: lines = 8; n = 20; break;
            case 7: lines = 16; n = 20; break;
            default: lines = 1; n = 0; break;              /* graphics modes the game does not use: one blank line */
            }
        }
        for (ln = 0; ln < lines && line < RENDER_FIRST_LINE + RENDER_H; ln++, line++) {
            uint8_t *out = colour + (line - RENDER_FIRST_LINE) * RENDER_W;
            memset(l.pri, 0, sizeof l.pri);
            memset(l.col, g.c[REG_BK], sizeof l.col);
            if (mode >= 2 && (dma & 3u)) {
                playfield_line(r, w, &g, mode, mp, ln, &l);
            }
            objects_line(w, line, cov);
            for (x = 0; x < RENDER_W; x++) {
                out[x] = pixel_colour(&g, prior, l.pri[x], l.col[x], cov[x]);
            }
            if (L != NULL) {
                int row = line - RENDER_FIRST_LINE;
                memcpy(L->pri + row * RENDER_W, l.pri, RENDER_W);
                memcpy(L->col + row * RENDER_W, l.col, RENDER_W);
                memcpy(L->cov + row * RENDER_W, cov, RENDER_W);
                memcpy(L->regs[row], g.c, sizeof g.c);
            }
        }
        if (n > 0) {
            mp = (mp & 0xF000u) | ((mp + n) & 0x0FFFu);   /* ANTIC's address counter wraps inside 4 KB */
        }
        if (dli) {                                         /* the interrupt is taken on the last line of the row; its writes land before the next line is drawn */
            dli_effect(w, handler, band, &g);
            band++;
        }
    }
}

void render_to_rgb(const uint8_t colour[RENDER_W * RENDER_H], uint8_t rgb[RENDER_W * RENDER_H * 3])
{
    int i;

    for (i = 0; i < RENDER_W * RENDER_H; i++) {
        rgb[3 * i] = NTSC_PALETTE[colour[i]][0];
        rgb[3 * i + 1] = NTSC_PALETTE[colour[i]][1];
        rgb[3 * i + 2] = NTSC_PALETTE[colour[i]][2];
    }
}
