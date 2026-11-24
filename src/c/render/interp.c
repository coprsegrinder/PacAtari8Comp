/* render/interp.c - the in-between pictures of the FPS option; see interp.h. */
#include "interp.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "palette.h"

#define FIX 1024                  /* fixed-point steps in a picture pixel */

/* the bits of the layers' cov that make object o: player o, or the four missiles */
static uint8_t object_mask(int o)
{
    return o < 4 ? (uint8_t)(1u << o) : (uint8_t)0xF0u;
}

void interp_prepare(InterpFrame *f)
{
    int o, x, y;

    for (o = 0; o < INTERP_OBJECTS; o++) {
        InterpObject *ob = &f->obj[o];
        uint8_t m = object_mask(o);

        ob->present = 0;
        ob->count = 0;
        ob->x0 = RENDER_W;
        ob->y0 = RENDER_H;
        ob->x1 = ob->y1 = 0;
        for (y = 0; y < RENDER_H; y++) {
            const uint8_t *row = f->layers.cov + y * RENDER_W;
            for (x = 0; x < RENDER_W; x++) {
                if (row[x] & m) {
                    ob->count++;
                    if (x < ob->x0) { ob->x0 = x; }
                    if (x + 1 > ob->x1) { ob->x1 = x + 1; }
                    if (y < ob->y0) { ob->y0 = y; }
                    if (y + 1 > ob->y1) { ob->y1 = y + 1; }
                }
            }
        }
        ob->present = ob->count > 0;
    }
}

void interp_pair(const InterpFrame *a, const InterpFrame *b, InterpPair *p)
{
    int o, dx, dy, x, y;

    memset(p, 0, sizeof *p);
    for (o = 0; o < INTERP_OBJECTS; o++) {
        const InterpObject *oa = &a->obj[o], *ob = &b->obj[o];
        uint8_t m = object_mask(o);
        int best_cost = 0x7FFFFFFF, best_dx = 0, best_dy = 0, best_overlap = 0;

        if (!oa->present || !ob->present) {
            continue;
        }
        for (dy = -INTERP_MAX_MOVE; dy <= INTERP_MAX_MOVE; dy++) {
            for (dx = -INTERP_MAX_MOVE; dx <= INTERP_MAX_MOVE; dx++) {
                int overlap = 0, cost;

                for (y = oa->y0; y < oa->y1; y++) {
                    int yy = y + dy;
                    if (yy < 0 || yy >= RENDER_H) {
                        continue;
                    }
                    for (x = oa->x0; x < oa->x1; x++) {
                        int xx = x + dx;
                        if (xx >= 0 && xx < RENDER_W && (a->layers.cov[y * RENDER_W + x] & m) && (b->layers.cov[yy * RENDER_W + xx] & m)) {
                            overlap++;
                        }
                    }
                }
                cost = oa->count + ob->count - 2 * overlap;
                if (cost < best_cost || (cost == best_cost && dx * dx + dy * dy < best_dx * best_dx + best_dy * best_dy)) {
                    best_cost = cost;
                    best_dx = dx;
                    best_dy = dy;
                    best_overlap = overlap;
                }
            }
        }
        {
            int smaller = oa->count < ob->count ? oa->count : ob->count;
            int edge = best_dx == -INTERP_MAX_MOVE || best_dx == INTERP_MAX_MOVE || best_dy == -INTERP_MAX_MOVE || best_dy == INTERP_MAX_MOVE;
            if (best_overlap * 2 >= smaller && !edge) {      /* at least half of the smaller one is on the other, and the best shift is not at the end of the range (a jump) */
                p->ok[o] = 1;
                p->dx[o] = best_dx;
                p->dy[o] = best_dy;
            }
        }
    }
}

int interp_out_init(InterpOut *o)
{
    int c;

    memset(o, 0, sizeof *o);
    for (c = 0; c < 256; c++) {
        o->lut[c] = 0xFF000000u | ((uint32_t)NTSC_PALETTE[c][0] << 16) | ((uint32_t)NTSC_PALETTE[c][1] << 8) | (uint32_t)NTSC_PALETTE[c][2];
    }
    return 0;
}

int interp_out_size(InterpOut *o, int ow, int oh)
{
    uint32_t *b, *w;

    if (ow == o->ow && oh == o->oh && o->base != NULL) {
        return 0;
    }
    free(o->base);
    free(o->work);
    o->base = o->work = NULL;
    o->ow = o->oh = 0;
    o->base_valid = 0;
    o->nrect = 0;
    if (ow < 1 || oh < 1) {
        return 0;
    }
    b = (uint32_t *)malloc((size_t)ow * (size_t)oh * sizeof(uint32_t));
    w = (uint32_t *)malloc((size_t)ow * (size_t)oh * sizeof(uint32_t));
    if (b == NULL || w == NULL) {
        free(b);
        free(w);
        return 1;
    }
    o->base = b;
    o->work = w;
    o->ow = ow;
    o->oh = oh;
    return 0;
}

void interp_out_free(InterpOut *o)
{
    free(o->base);
    free(o->work);
    o->base = o->work = NULL;
    o->ow = o->oh = 0;
    o->base_valid = 0;
}

/* the source pixel (picture pixels) of output pixel i of n along an axis of `src` pixels, less an offset in 1/FIX pixels; floor, so that offset 0 gives the same pixel for the base and for the redrawn parts */
static int src_index(int i, int n, int src, int off_fix)
{
    long long u = ((2LL * i + 1LL) * src * FIX) / (2LL * n) - off_fix;
    long long q = u / FIX;

    if (u < 0 && u % FIX != 0) {
        q--;
    }
    return (int)q;
}

static void build_base(InterpOut *o, const InterpFrame *f)
{
    int ox, oy, last_sy = -1;
    int *xmap = (int *)malloc((size_t)o->ow * sizeof(int));

    if (xmap == NULL) {
        return;
    }
    for (ox = 0; ox < o->ow; ox++) {
        xmap[ox] = src_index(ox, o->ow, RENDER_W, 0);
    }
    for (oy = 0; oy < o->oh; oy++) {
        int sy = src_index(oy, o->oh, RENDER_H, 0);
        uint32_t *row = o->base + (size_t)oy * (size_t)o->ow;
        if (sy == last_sy && oy > 0) {
            memcpy(row, row - o->ow, (size_t)o->ow * sizeof(uint32_t));
        } else {
            const uint8_t *src = f->colour + sy * RENDER_W;
            for (ox = 0; ox < o->ow; ox++) {
                row[ox] = o->lut[src[xmap[ox]]];
            }
        }
        last_sy = sy;
    }
    free(xmap);
}

/* redraw the rectangle [x0, x1) x [y0, y1) of work from the layers of f, the objects drawn at their offsets (1/FIX pixels) */
static void redraw(InterpOut *o, const InterpFrame *f, const int offx[INTERP_OBJECTS], const int offy[INTERP_OBJECTS], int x0, int y0, int x1, int y1)
{
    int ox, oy, k;

    for (oy = y0; oy < y1; oy++) {
        int sy = src_index(oy, o->oh, RENDER_H, 0);
        uint32_t *row = o->work + (size_t)oy * (size_t)o->ow;
        for (ox = x0; ox < x1; ox++) {
            int sx = src_index(ox, o->ow, RENDER_W, 0);
            uint8_t cov = 0;

            for (k = 0; k < INTERP_OBJECTS; k++) {
                int px, py;
                if (!f->obj[k].present) {
                    continue;
                }
                px = src_index(ox, o->ow, RENDER_W, offx[k]);
                py = src_index(oy, o->oh, RENDER_H, offy[k]);
                if (px >= 0 && px < RENDER_W && py >= 0 && py < RENDER_H) {
                    cov |= (uint8_t)(f->layers.cov[py * RENDER_W + px] & object_mask(k));
                }
            }
            row[ox] = o->lut[render_compose(f->layers.regs[sy], f->layers.prior, f->layers.pri[sy * RENDER_W + sx], f->layers.col[sy * RENDER_W + sx], cov)];
        }
    }
}

void interp_render(InterpOut *o, const InterpFrame *a, const InterpFrame *b, const InterpPair *pair, double phi, unsigned long id_a, InterpDirty *d)
{
    const InterpFrame *near_f = a;
    unsigned long near_id = id_a;
    int offx[INTERP_OBJECTS], offy[INTERP_OBJECTS], k, i;
    int rebuilt = 0;
    double sx_scale, sy_scale;

    memset(d, 0, sizeof *d);
    if (o->base == NULL || a == NULL) {
        return;
    }
    if (b != NULL && pair != NULL && phi >= 0.5) {
        near_f = b;
        near_id = id_a + 1;
    }
    sx_scale = (double)o->ow / RENDER_W;
    sy_scale = (double)o->oh / RENDER_H;
    for (k = 0; k < INTERP_OBJECTS; k++) {
        offx[k] = offy[k] = 0;
        if (b != NULL && pair != NULL && pair->ok[k] && near_f->obj[k].present) {
            double f = near_f == a ? phi : phi - 1.0;       /* the nearer frame's object is |f| of the move away from its own place */
            /* the offset is a whole number of pixels of the picture shown: two moments that put the object on the same pixels make the same picture */
            double px = floor(f * pair->dx[k] * sx_scale + 0.5), py = floor(f * pair->dy[k] * sy_scale + 0.5);
            offx[k] = (int)floor(px * FIX / sx_scale + 0.5);
            offy[k] = (int)floor(py * FIX / sy_scale + 0.5);
        }
    }
    if (o->base_valid && o->base_id == near_id && memcmp(offx, o->last_offx, sizeof offx) == 0 && memcmp(offy, o->last_offy, sizeof offy) == 0) {
        return;                                             /* the same picture as the last one: nothing to do, nothing changed */
    }
    memcpy(o->last_offx, offx, sizeof offx);
    memcpy(o->last_offy, offy, sizeof offy);
    if (!o->base_valid || o->base_id != near_id) {
        build_base(o, near_f);
        o->base_id = near_id;
        o->base_valid = 1;
        memcpy(o->work, o->base, (size_t)o->ow * (size_t)o->oh * sizeof(uint32_t));
        o->nrect = 0;
        rebuilt = 1;
    } else {
        for (i = 0; i < o->nrect; i++) {                    /* put back what the objects of the last picture covered */
            int yy;
            for (yy = o->rect[i][1]; yy < o->rect[i][3]; yy++) {
                memcpy(o->work + (size_t)yy * (size_t)o->ow + o->rect[i][0], o->base + (size_t)yy * (size_t)o->ow + o->rect[i][0], (size_t)(o->rect[i][2] - o->rect[i][0]) * sizeof(uint32_t));
            }
            memcpy(d->r[d->n++], o->rect[i], sizeof o->rect[i]);
        }
        o->nrect = 0;
    }
    for (k = 0; k < INTERP_OBJECTS; k++) {
        const InterpObject *ob = &near_f->obj[k];
        double ox0, ox1, oy0, oy1;
        int rx0, ry0, rx1, ry1;

        if (!ob->present || (offx[k] == 0 && offy[k] == 0)) {
            continue;
        }
        ox0 = ob->x0 + (offx[k] < 0 ? (double)offx[k] / FIX : 0.0);        /* the box the object covers: where it is in its frame and where it is drawn */
        ox1 = ob->x1 + (offx[k] > 0 ? (double)offx[k] / FIX : 0.0);
        oy0 = ob->y0 + (offy[k] < 0 ? (double)offy[k] / FIX : 0.0);
        oy1 = ob->y1 + (offy[k] > 0 ? (double)offy[k] / FIX : 0.0);
        rx0 = (int)(ox0 * sx_scale) - 1;
        rx1 = (int)(ox1 * sx_scale) + 2;
        ry0 = (int)(oy0 * sy_scale) - 1;
        ry1 = (int)(oy1 * sy_scale) + 2;
        if (rx0 < 0) { rx0 = 0; }
        if (ry0 < 0) { ry0 = 0; }
        if (rx1 > o->ow) { rx1 = o->ow; }
        if (ry1 > o->oh) { ry1 = o->oh; }
        if (rx0 >= rx1 || ry0 >= ry1) {
            continue;
        }
        redraw(o, near_f, offx, offy, rx0, ry0, rx1, ry1);
        o->rect[o->nrect][0] = rx0;
        o->rect[o->nrect][1] = ry0;
        o->rect[o->nrect][2] = rx1;
        o->rect[o->nrect][3] = ry1;
        o->nrect++;
        memcpy(d->r[d->n++], o->rect[o->nrect - 1], sizeof o->rect[0]);
    }
    if (rebuilt) {
        d->full = 1;
        d->n = 0;
    }
}
