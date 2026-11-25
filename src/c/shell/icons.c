/* shell/icons.c - the icons of the Controls page (docs/71); see icons.h. */
#include <string.h>

#include "icons.h"

typedef struct Rgb { unsigned r, g, b; } Rgb;

static const Rgb GREY = {150, 150, 150};
static const Rgb LIGHT = {230, 230, 230};
static const Rgb DARK = {48, 48, 56};
static const Rgb WHITE = {255, 255, 255};
static const Rgb BLACK = {0, 0, 0};

static void px(IconCanvas *c, int x, int y, Rgb v)
{
    if (x >= 0 && x < c->w && y >= 0 && y < c->h) {
        uint8_t *p = c->bgra + 4 * ((size_t)y * (size_t)c->w + (size_t)x);
        p[0] = (uint8_t)v.b;
        p[1] = (uint8_t)v.g;
        p[2] = (uint8_t)v.r;
    }
}

static void rect(IconCanvas *c, int x, int y, int w, int h, Rgb v)
{
    int i, j;

    for (j = 0; j < h; j++) {
        for (i = 0; i < w; i++) {
            px(c, x + i, y + j, v);
        }
    }
}

static void frame(IconCanvas *c, int x, int y, int w, int h, Rgb v)
{
    rect(c, x, y, w, 1, v);
    rect(c, x, y + h - 1, w, 1, v);
    rect(c, x, y, 1, h, v);
    rect(c, x + w - 1, y, 1, h, v);
}

/* a disc or a ring inside the square x, y, d x d (d even or odd): the pixels whose centre is within the radius; ring: only the outermost pixels */
static void disc(IconCanvas *c, int x, int y, int d, Rgb v, int ring)
{
    int i, j;
    long r2 = (long)d * d;                                   /* (2 * radius)^2 */

    for (j = 0; j < d; j++) {
        for (i = 0; i < d; i++) {
            long dx = 2L * i + 1 - d, dy = 2L * j + 1 - d, dd = dx * dx + dy * dy;
            long inner = (long)(d - 3) * (d - 3);
            if (dd <= r2 && (!ring || dd >= inner)) {
                px(c, x + i, y + j, v);
            }
        }
    }
}

static void line(IconCanvas *c, int x0, int y0, int x1, int y1, Rgb v)
{
    int dx = x1 > x0 ? x1 - x0 : x0 - x1, dy = y1 > y0 ? y1 - y0 : y0 - y1;
    int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, err = dx - dy;

    for (;;) {
        int e2;
        px(c, x0, y0, v);
        if (x0 == x1 && y0 == y1) {
            break;
        }
        e2 = 2 * err;
        if (e2 > -dy) {
            err -= dy;
            x0 += sx;
        }
        if (e2 < dx) {
            err += dx;
            y0 += sy;
        }
    }
}

int icon_text(IconCanvas *c, int x, int y, const char *t, unsigned r, unsigned g, unsigned b)
{
    int x0 = x;
    Rgb v;

    v.r = r;
    v.g = g;
    v.b = b;
    for (; *t != '\0'; t++) {
        unsigned ch = (unsigned char)*t;
        int row, bit;

        if (ch < 0x20u || ch > 0x5Fu) {
            continue;
        }
        if (c->font != NULL) {
            for (row = 0; row < 8; row++) {
                uint8_t bits = c->font[(ch - 0x20u) * 8u + (unsigned)row];
                for (bit = 0; bit < 8; bit++) {
                    if ((bits >> (7 - bit)) & 1) {
                        px(c, x + bit, y + row, v);
                    }
                }
            }
        }
        x += 8;
    }
    return x - x0;
}

static int label_len(const ControlGlyph *g)
{
    int n = 0;

    if (g->label != NULL) {
        for (; g->label[n] != '\0'; n++) {
        }
    }
    return n;
}

int icon_width(const ControlGlyph *g)
{
    switch (g->icon) {
    case IC_KEY: return 8 * label_len(g) + 6;
    case IC_ARROWS: return 18;
    case IC_OPTIONS:
    case IC_SHARE:
    case IC_CREATE: return 18;
    case IC_SLASH:
    case IC_PLUS: return 8;
    case IC_NONE: return 0;
    default: return ICON_H;                                  /* the round ones */
    }
}

/* a face button: a coloured disc with its letter */
static void face(IconCanvas *c, int x, int y, Rgb colour, const char *letter, Rgb ink)
{
    disc(c, x, y, ICON_H, colour, 0);
    (void)icon_text(c, x + 3, y + 3, letter, ink.r, ink.g, ink.b);
}

/* a PlayStation button: a dark disc with a grey rim and the symbol in its colour */
static void ps_base(IconCanvas *c, int x, int y)
{
    disc(c, x, y, ICON_H, DARK, 0);
    disc(c, x, y, ICON_H, GREY, 1);
}

static void arrow_small(IconCanvas *c, int cx, int cy, int dx, int dy, Rgb v)      /* a 3-pixel-high triangle pointing in direction dx, dy at cx, cy */
{
    if (dx == 0) {
        px(c, cx, cy, v);
        px(c, cx - 1, cy - dy, v);
        px(c, cx, cy - dy, v);
        px(c, cx + 1, cy - dy, v);
    } else {
        px(c, cx, cy, v);
        px(c, cx - dx, cy - 1, v);
        px(c, cx - dx, cy, v);
        px(c, cx - dx, cy + 1, v);
    }
}

/* the pill of Options / Share / Create: a rounded grey body with its own little mark */
static void pill(IconCanvas *c, int x, int y, int kind)
{
    int i;

    rect(c, x + 2, y + 2, 14, 10, DARK);
    frame(c, x + 2, y + 2, 14, 10, GREY);
    px(c, x + 2, y + 2, BLACK);
    px(c, x + 15, y + 2, BLACK);
    px(c, x + 2, y + 11, BLACK);
    px(c, x + 15, y + 11, BLACK);
    if (kind == IC_OPTIONS) {                                /* three lines */
        for (i = 0; i < 3; i++) {
            rect(c, x + 5, y + 4 + 2 * i, 8, 1, LIGHT);
        }
    } else if (kind == IC_SHARE) {                           /* an arrow leaving a box */
        frame(c, x + 5, y + 6, 8, 5, LIGHT);
        line(c, x + 9, y + 9, x + 9, y + 3, WHITE);
        px(c, x + 8, y + 4, WHITE);
        px(c, x + 10, y + 4, WHITE);
        px(c, x + 7, y + 5, WHITE);
        px(c, x + 11, y + 5, WHITE);
    } else {                                                 /* Create: two sliders */
        rect(c, x + 5, y + 5, 8, 1, LIGHT);
        rect(c, x + 5, y + 8, 8, 1, LIGHT);
        rect(c, x + 7, y + 4, 2, 3, WHITE);
        rect(c, x + 10, y + 7, 2, 3, WHITE);
    }
}

int icon_draw(IconCanvas *c, int x, int y, const ControlGlyph *g)
{
    int w = icon_width(g);
    static const Rgb xa = {64, 176, 64}, xb = {220, 60, 52}, xx = {60, 120, 220}, xy = {240, 200, 40};
    static const Rgb ps_cross = {110, 160, 255}, ps_circle = {255, 90, 90}, ps_square = {240, 140, 220}, ps_tri = {70, 220, 150};

    switch (g->icon) {
    case IC_KEY: {
        rect(c, x, y, w, ICON_H, DARK);
        frame(c, x, y, w, ICON_H, LIGHT);
        (void)icon_text(c, x + 3, y + 3, g->label != NULL ? g->label : "", 255, 255, 255);
        break;
    }
    case IC_ARROWS:                                          /* a key with the four arrows on it */
        rect(c, x, y, w, ICON_H, DARK);
        frame(c, x, y, w, ICON_H, LIGHT);
        arrow_small(c, x + 9, y + 2, 0, -1, WHITE);
        arrow_small(c, x + 9, y + 11, 0, 1, WHITE);
        arrow_small(c, x + 2, y + 7, -1, 0, WHITE);
        arrow_small(c, x + 15, y + 7, 1, 0, WHITE);
        break;
    case IC_DPAD:                                            /* the cross: arms 4 wide */
        rect(c, x + 5, y, 4, ICON_H, GREY);
        rect(c, x, y + 5, ICON_H, 4, GREY);
        rect(c, x + 6, y + 1, 2, 3, DARK);
        break;
    case IC_STICK:                                           /* the cap of a stick seen from above */
        disc(c, x, y, ICON_H, GREY, 1);
        disc(c, x + 3, y + 3, 8, GREY, 0);
        disc(c, x + 5, y + 5, 4, DARK, 0);
        break;
    case IC_XA: face(c, x, y, xa, "A", BLACK); break;
    case IC_XB: face(c, x, y, xb, "B", BLACK); break;
    case IC_XX: face(c, x, y, xx, "X", BLACK); break;
    case IC_XY: face(c, x, y, xy, "Y", BLACK); break;
    case IC_XMENU:                                           /* the right middle button: a ring with three lines */
        disc(c, x, y, ICON_H, DARK, 0);
        disc(c, x, y, ICON_H, GREY, 1);
        rect(c, x + 4, y + 4, 6, 1, WHITE);
        rect(c, x + 4, y + 6, 6, 1, WHITE);
        rect(c, x + 4, y + 8, 6, 1, WHITE);
        break;
    case IC_XVIEW:                                           /* the left middle button: a ring with two windows */
        disc(c, x, y, ICON_H, DARK, 0);
        disc(c, x, y, ICON_H, GREY, 1);
        frame(c, x + 3, y + 3, 6, 5, WHITE);
        frame(c, x + 5, y + 5, 6, 5, WHITE);
        break;
    case IC_CROSS:
        ps_base(c, x, y);
        line(c, x + 4, y + 4, x + 9, y + 9, ps_cross);
        line(c, x + 9, y + 4, x + 4, y + 9, ps_cross);
        line(c, x + 5, y + 4, x + 9, y + 8, ps_cross);
        line(c, x + 8, y + 4, x + 4, y + 8, ps_cross);
        break;
    case IC_CIRCLE:
        ps_base(c, x, y);
        disc(c, x + 3, y + 3, 8, ps_circle, 1);
        break;
    case IC_SQUARE:
        ps_base(c, x, y);
        frame(c, x + 3, y + 3, 8, 8, ps_square);
        frame(c, x + 4, y + 4, 6, 6, ps_square);
        break;
    case IC_TRIANGLE:
        ps_base(c, x, y);
        line(c, x + 7, y + 3, x + 3, y + 10, ps_tri);
        line(c, x + 7, y + 3, x + 11, y + 10, ps_tri);
        line(c, x + 3, y + 10, x + 11, y + 10, ps_tri);
        line(c, x + 4, y + 9, x + 10, y + 9, ps_tri);
        break;
    case IC_OPTIONS:
    case IC_SHARE:
    case IC_CREATE:
        pill(c, x, y, g->icon);
        break;
    case IC_SLASH:
        line(c, x + 5, y + 3, x + 2, y + 10, GREY);
        break;
    case IC_PLUS:
        rect(c, x + 1, y + 6, 6, 2, GREY);
        rect(c, x + 3, y + 4, 2, 6, GREY);
        break;
    default:
        break;
    }
    return w;
}

int icon_row_width(const ControlGlyph *g, int n, int gap)
{
    int i, w = 0;

    for (i = 0; i < n; i++) {
        w += icon_width(&g[i]);
        if (i + 1 < n) {
            w += gap;
        }
    }
    return w;
}

int icon_row_draw(IconCanvas *c, int x, int y, const ControlGlyph *g, int n, int gap)
{
    int i, x0 = x;

    for (i = 0; i < n; i++) {
        x += icon_draw(c, x, y, &g[i]) + gap;
    }
    return x - gap - x0;
}
