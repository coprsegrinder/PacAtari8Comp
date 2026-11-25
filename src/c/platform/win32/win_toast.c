/* platform/win32/win_toast.c - the achievement toast, drawn into the game's picture (docs/74); see win_toast.h. */
#include <stdio.h>
#include <string.h>
#include <windows.h>

#include "win_toast.h"

#define QUEUE 8
#define SHOW_MS 4500u
#define FADE_IN_MS 150u
#define FADE_OUT_MS 600u
#define BASE_ALPHA 240u
#define PIC_W 384
#define PIC_H 240
#define MAX_W 380
#define MAX_H 48
#define AT_X 14                                  /* the top left of the picture */
#define AT_Y 12

static const uint8_t *font_data;
static char q_name[QUEUE][32], q_desc[QUEUE][56];
static int qn, active, total, bw, bh;
static ULONGLONG t0;
static unsigned long pictures;
static uint8_t base[MAX_W * MAX_H * 4];          /* the toast at its own size, BGRA, alpha in the fourth byte */

static const char *const TROPHY[12] = {
    "############",
    ".##########.",
    ".##########.",
    ".##########.",
    "..########..",
    "...######...",
    "....####....",
    ".....##.....",
    ".....##.....",
    "....####....",
    "...######...",
    "...######...",
};

static void put(int x, int y, unsigned r, unsigned g, unsigned b)
{
    if (x >= 0 && x < bw && y >= 0 && y < bh) {
        uint8_t *p = base + 4 * ((size_t)y * (size_t)bw + (size_t)x);
        p[0] = (uint8_t)b;
        p[1] = (uint8_t)g;
        p[2] = (uint8_t)r;
        p[3] = (uint8_t)BASE_ALPHA;
    }
}

static void text(int x, int y, const char *t, unsigned r, unsigned g, unsigned b)
{
    for (; *t != '\0'; t++, x += 8) {
        unsigned c = (unsigned char)*t;
        int row, bit;

        if (c < 0x20u || c > 0x5Fu || font_data == NULL) {
            continue;
        }
        for (row = 0; row < 8; row++) {
            uint8_t bits = font_data[(c - 0x20u) * 8u + (unsigned)row];
            for (bit = 0; bit < 8; bit++) {
                if ((bits >> (7 - bit)) & 1) {
                    put(x + bit, y + row, r, g, b);
                }
            }
        }
    }
}

/* the toast at its own size: a dark box with a gold rim, a gold cup, "ACHIEVEMENT UNLOCKED", the name and the description (the first version's look) */
static void build(const char *name, const char *desc)
{
    size_t ln = strlen(name), ld = strlen(desc), longest = ln > ld ? ln : ld;
    int x, y;

    if (longest < 20u) {
        longest = 20u;
    }
    bw = 26 + 8 * (int)longest + 10;
    bh = 42;
    if (bw > MAX_W) {
        bw = MAX_W;
    }
    for (y = 0; y < bh; y++) {
        for (x = 0; x < bw; x++) {
            int edge = x == 0 || y == 0 || x == bw - 1 || y == bh - 1;
            put(x, y, edge ? 255u : 12u, edge ? 200u : 12u, edge ? 60u : 20u);
        }
    }
    for (y = 0; y < 12; y++) {
        for (x = 0; x < 12; x++) {
            if (TROPHY[y][x] == '#') {
                put(7 + x, 15 + y, 255u, y < 4 ? 225u : 190u, y < 4 ? 90u : 20u);
            }
        }
    }
    text(26, 5, "ACHIEVEMENT UNLOCKED", 255u, 200u, 60u);
    text(26, 17, name, 255u, 255u, 255u);
    text(26, 29, desc, 170u, 170u, 170u);
}

void wtoast_init(const uint8_t *font)
{
    font_data = font;
}

void wtoast_show(const char *name, const char *desc)
{
    if (qn < QUEUE) {
        snprintf(q_name[qn], sizeof q_name[qn], "%s", name);
        snprintf(q_desc[qn], sizeof q_desc[qn], "%s", desc);
        qn++;
    }
}

void wtoast_tick(void)
{
    ULONGLONG now = GetTickCount64();
    int i;

    if (active && now - t0 >= SHOW_MS) {
        active = 0;
    }
    if (!active && qn > 0) {
        build(q_name[0], q_desc[0]);
        for (i = 1; i < qn; i++) {
            memcpy(q_name[i - 1], q_name[i], sizeof q_name[0]);
            memcpy(q_desc[i - 1], q_desc[i], sizeof q_desc[0]);
        }
        qn--;
        active = 1;
        t0 = now;
        total++;
    }
}

int wtoast_active(void)
{
    return active;
}

unsigned long wtoast_age_ms(void)
{
    return active ? (unsigned long)(GetTickCount64() - t0) : 0ul;
}

void wtoast_box(int *x, int *y, int *w, int *h)
{
    *x = AT_X;
    *y = AT_Y;
    *w = bw;
    *h = bh;
}

int wtoast_overlay(uint8_t *bgra, int w, int h)
{
    ULONGLONG el;
    unsigned fade, a;
    int x0, y0, x1, y1, X, Y, changed = 0;

    if (!active || w < 1 || h < 1) {
        return 0;
    }
    el = GetTickCount64() - t0;
    if (el >= SHOW_MS) {
        return 0;
    }
    fade = el < FADE_IN_MS ? (unsigned)(el * 255u / FADE_IN_MS) : el > SHOW_MS - FADE_OUT_MS ? (unsigned)((SHOW_MS - el) * 255u / FADE_OUT_MS) : 255u;
    x0 = (int)((long)AT_X * w / PIC_W);
    y0 = (int)((long)AT_Y * h / PIC_H);
    x1 = (int)((long)(AT_X + bw) * w / PIC_W);
    y1 = (int)((long)(AT_Y + bh) * h / PIC_H);
    if (x1 > w) {
        x1 = w;
    }
    if (y1 > h) {
        y1 = h;
    }
    for (Y = y0; Y < y1; Y++) {
        int sy = (int)((long)(2 * (Y - y0) + 1) * PIC_H / (2L * h));                  /* the pixel of the toast this one shows (the middle of it, nearest) */
        const uint8_t *srow;
        uint8_t *d;

        sy = sy < 0 ? 0 : sy >= bh ? bh - 1 : sy;
        srow = base + 4 * (size_t)sy * (size_t)bw;
        d = bgra + 4 * ((size_t)Y * (size_t)w + (size_t)x0);
        for (X = x0; X < x1; X++, d += 4) {
            int sx = (int)((long)(2 * (X - x0) + 1) * PIC_W / (2L * w));
            const uint8_t *s;

            sx = sx < 0 ? 0 : sx >= bw ? bw - 1 : sx;
            s = srow + 4 * (size_t)sx;
            a = s[3] * fade / 255u;
            d[0] = (uint8_t)((s[0] * a + d[0] * (255u - a)) / 255u);
            d[1] = (uint8_t)((s[1] * a + d[1] * (255u - a)) / 255u);
            d[2] = (uint8_t)((s[2] * a + d[2] * (255u - a)) / 255u);
            changed++;
        }
    }
    pictures++;
    return changed;
}

int wtoast_count(void)
{
    return total;
}

unsigned long wtoast_pictures(void)
{
    return pictures;
}

void wtoast_shutdown(void)
{
}
