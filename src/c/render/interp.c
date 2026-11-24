/* render/interp.c - the in-between pictures of the FPS option; see interp.h. */
#include "interp.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "palette.h"

#define FIX 1024                  /* fixed-point steps in a picture pixel */

int interp_similar_percent = INTERP_SIMILAR;

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
        ob->present = 0;
        ob->count = 0;
        ob->x0 = RENDER_W;
        ob->y0 = RENDER_H;
        ob->x1 = ob->y1 = 0;
    }
    for (y = 0; y < RENDER_H; y++) {                             /* one pass: most of the picture has no object on it */
        const uint8_t *row = f->layers.cov + y * RENDER_W;
        for (x = 0; x < RENDER_W; x++) {
            uint8_t v = row[x];
            if (v == 0) {
                continue;
            }
            for (o = 0; o < INTERP_OBJECTS; o++) {
                if (v & object_mask(o)) {
                    InterpObject *ob = &f->obj[o];
                    ob->count++;
                    if (x < ob->x0) { ob->x0 = x; }
                    if (x + 1 > ob->x1) { ob->x1 = x + 1; }
                    if (y < ob->y0) { ob->y0 = y; }
                    if (y + 1 > ob->y1) { ob->y1 = y + 1; }
                }
            }
        }
    }
    for (o = 0; o < INTERP_OBJECTS; o++) {
        f->obj[o].present = f->obj[o].count > 0;
    }
}

void interp_pair(const InterpFrame *a, const InterpFrame *b, InterpPair *p)
{
    int o, dx, dy, x, y;

    memset(p, 0, sizeof *p);
    for (o = 0; o < INTERP_OBJECTS; o++) {
        const InterpObject *oa = &a->obj[o], *ob = &b->obj[o];
        uint8_t m = object_mask(o);
        int best_cost = 0x7FFFFFFF, best_dx = 0, best_dy = 0, best_overlap = 0, similar;

        if (!oa->present || !ob->present) {
            continue;
        }
        if (oa->count == ob->count && oa->x0 == ob->x0 && oa->y0 == ob->y0 && oa->x1 == ob->x1 && oa->y1 == ob->y1) {   /* the same shape in the same place (an object that did not move): no search */
            int same = 1;
            for (y = oa->y0; y < oa->y1 && same; y++) {
                for (x = oa->x0; x < oa->x1; x++) {
                    if ((a->layers.cov[y * RENDER_W + x] & m) != (b->layers.cov[y * RENDER_W + x] & m)) {
                        same = 0;
                        break;
                    }
                }
            }
            if (same) {
                p->ok[o] = 1;
                p->similar[o] = 100;
                continue;
            }
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
            similar = oa->count + ob->count - best_overlap > 0 ? 100 * best_overlap / (oa->count + ob->count - best_overlap) : 0;
            p->similar[o] = similar;
            if (best_overlap * 2 >= smaller && similar >= interp_similar_percent && !edge) {      /* the same shape, to a good share (not a ghost and its eyes, not Pac-Man and a score), moved, and the best shift is not at the end of the range (a jump) */
                p->ok[o] = 1;
                p->dx[o] = best_dx;
                p->dy[o] = best_dy;
            }
        }
    }
}

void interp_box_x(const uint32_t *src, int src_w, int h, int k, uint32_t *dst)
{
    int x, y, i, dw = src_w / k;

    for (y = 0; y < h; y++) {
        const uint32_t *row = src + (size_t)y * (size_t)src_w;
        uint32_t *out = dst + (size_t)y * (size_t)dw;
        for (x = 0; x < dw; x++) {
            unsigned b = 0, g = 0, r = 0;
            for (i = 0; i < k; i++) {
                uint32_t p = row[x * k + i];
                b += p & 0xFFu;
                g += (p >> 8) & 0xFFu;
                r += (p >> 16) & 0xFFu;
            }
            out[x] = 0xFF000000u | (((r + (unsigned)k / 2u) / (unsigned)k) << 16) | (((g + (unsigned)k / 2u) / (unsigned)k) << 8) | ((b + (unsigned)k / 2u) / (unsigned)k);
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

void interp_follow(InterpFrame *cur, const InterpFrame *prev)
{
    InterpPair pr;
    int k;

    if (prev != NULL) {
        interp_pair(prev, cur, &pr);
    } else {
        memset(&pr, 0, sizeof pr);
    }
    for (k = 0; k < INTERP_OBJECTS; k++) {
        cur->mv[k] = 0;
        cur->px[k] = cur->py[k] = 0;
        if (!cur->obj[k].present) {
            cur->run[k] = prev != NULL ? prev->run[k] + 1 : 1;     /* gone: the next time it appears is a new run */
        } else if (prev != NULL && prev->obj[k].present && pr.ok[k]) {
            cur->run[k] = prev->run[k];
            cur->px[k] = prev->px[k] + pr.dx[k];
            cur->py[k] = prev->py[k] + pr.dy[k];
            cur->mv[k] = pr.dx[k] != 0 || pr.dy[k] != 0;
        } else {
            cur->run[k] = prev != NULL ? prev->run[k] + 1 : 1;     /* appeared, jumped or did not match: a new run */
        }
    }
}

#define EVENT_SPAN 10             /* how many frames back and forward the moves of an object are looked for */
#define MAX_GAP 8                 /* the longest time between two moves that is smoothed over (frames) */

/* where object k is at the game time t: the moves of an object are the frames at which it changed place (the game moves each object in steps, every second or third frame); between two moves it is
 * drawn on the straight way from one place to the next (so it glides the whole time between the moves and arrives when the game put it there); when the next move is not yet made (the game is only
 * a frame or two ahead of the picture) the way is the one of the move before it.  Positions are counted from the start of the object's run (interp_follow).  Returns 0 when the object is not in a run at t */
static int object_target(InterpGet get, void *ctx, unsigned long f, unsigned long newest, double t, int k, double *tx, double *ty);

int interp_place(InterpGet get, void *ctx, double t, unsigned long newest, int k, double *x, double *y)
{
    return t >= 0.0 && object_target(get, ctx, (unsigned long)floor(t), newest, t, k, x, y);
}

static int object_target(InterpGet get, void *ctx, unsigned long f, unsigned long newest, double t, int k, double *tx, double *ty)
{
    const InterpFrame *ff = get(ctx, f), *fj;
    unsigned long j, e0 = 0, e1 = 0, em = 0;
    int h0 = 0, h1 = 0, hm = 0, run;
    double p0x, p0y;

    if (ff == NULL || !ff->obj[k].present) {
        return 0;
    }
    run = ff->run[k];
    if (f + 1 <= newest) {                                       /* the next frame is made: when the object is not the same object in it (it appears, vanishes, jumps, becomes another shape) it stays where the game has it */
        fj = get(ctx, f + 1);
        if (fj != NULL && (!fj->obj[k].present || fj->run[k] != run)) {
            *tx = ff->px[k];
            *ty = ff->py[k];
            return 1;
        }
    }
    for (j = f; j > 0 && j + EVENT_SPAN > f; j--) {              /* the last move at or before f */
        fj = get(ctx, j);
        if (fj == NULL || !fj->obj[k].present || fj->run[k] != run) {
            break;
        }
        if (fj->mv[k]) {
            e0 = j;
            h0 = 1;
            break;
        }
    }
    if (h0) {
        for (j = e0 - 1; j > 0 && j + EVENT_SPAN > e0; j--) {    /* and the one before it */
            fj = get(ctx, j);
            if (fj == NULL || !fj->obj[k].present || fj->run[k] != run) {
                break;
            }
            if (fj->mv[k]) {
                em = j;
                hm = 1;
                break;
            }
        }
    }
    for (j = f + 1; j <= newest && j <= f + EVENT_SPAN; j++) {   /* the next move that is already made */
        fj = get(ctx, j);
        if (fj == NULL || !fj->obj[k].present || fj->run[k] != run) {
            break;
        }
        if (fj->mv[k]) {
            e1 = j;
            h1 = 1;
            break;
        }
    }
    p0x = ff->px[k];
    p0y = ff->py[k];
    if (h0) {
        fj = get(ctx, e0);
        p0x = fj->px[k];
        p0y = fj->py[k];
    }
    if (h1) {
        const InterpFrame *f1 = get(ctx, e1);
        double p1x = f1->px[k], p1y = f1->py[k];
        if (h0 && e1 - e0 <= MAX_GAP) {                           /* between two moves: the straight way, over the whole time */
            double u = (t - (double)e0) / (double)(e1 - e0);
            *tx = p0x + (p1x - p0x) * u;
            *ty = p0y + (p1y - p0y) * u;
        } else {                                                  /* a first move, or after a long wait: still until the last frame before it */
            double s = (double)e1 - 1.0, u = t > s ? t - s : 0.0;
            const InterpFrame *fs = get(ctx, e1 - 1);
            double sx = fs != NULL && fs->run[k] == run ? fs->px[k] : p1x, sy = fs != NULL && fs->run[k] == run ? fs->py[k] : p1y;
            *tx = sx + (p1x - sx) * u;
            *ty = sy + (p1y - sy) * u;
        }
        return 1;
    }
    if (h0 && hm && e0 - em <= MAX_GAP) {                         /* no next move yet: on the way the move before it took, no further than the one step */
        const InterpFrame *fm = get(ctx, em);
        double g = (double)(e0 - em), u = (t - (double)e0) / g;
        if (u > 1.0) {
            u = 1.0;
        }
        *tx = p0x + (p0x - fm->px[k]) * u;
        *ty = p0y + (p0y - fm->py[k]) * u;
        return 1;
    }
    *tx = ff->px[k];
    *ty = ff->py[k];
    return 1;
}

void interp_render(InterpOut *o, InterpGet get, void *ctx, double t, unsigned long newest, InterpDirty *d)
{
    const InterpFrame *near_f;
    unsigned long f, near_id;
    int offx[INTERP_OBJECTS], offy[INTERP_OBJECTS], k, i;
    int rebuilt = 0;
    double sx_scale, sy_scale;

    memset(d, 0, sizeof *d);
    if (o->base == NULL || t < 0.0) {
        return;
    }
    f = (unsigned long)floor(t);
    near_id = (t - (double)f >= 0.5) ? f + 1 : f;
    if (near_id > newest || get(ctx, near_id) == NULL) {
        near_id = f;
    }
    near_f = get(ctx, near_id);
    if (near_f == NULL) {
        return;
    }
    sx_scale = (double)o->ow / RENDER_W;
    sy_scale = (double)o->oh / RENDER_H;
    for (k = 0; k < INTERP_OBJECTS; k++) {
        double tx, ty;
        offx[k] = offy[k] = 0;
        if (near_f->obj[k].present && f <= newest && !o->still && object_target(get, ctx, f, newest, t, k, &tx, &ty)) {
            /* the offset is the way the object is from the place its nearer frame has it, a whole number of pixels of the picture shown: two moments that put the object on the same pixels make the same picture */
            double dx = tx - near_f->px[k], dy = ty - near_f->py[k];
            double px, py;
            if (near_f->run[k] != get(ctx, f)->run[k] || fabs(dx) > 2.0 * INTERP_MAX_MOVE || fabs(dy) > 2.0 * INTERP_MAX_MOVE) {
                continue;
            }
            px = floor(dx * sx_scale + 0.5);
            py = floor(dy * sy_scale + 0.5);
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
