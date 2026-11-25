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
    uint32_t *b, *w, *sc;
    int *xm;

    if (ow == o->ow && oh == o->oh && o->base != NULL) {
        return 0;
    }
    free(o->base);
    free(o->work);
    free(o->scratch);
    free(o->xmap);
    o->base = o->work = o->scratch = NULL;
    o->xmap = NULL;
    o->ow = o->oh = 0;
    o->base_valid = 0;
    o->nrect = 0;
    if (ow < 1 || oh < 1) {
        return 0;
    }
    b = (uint32_t *)malloc((size_t)ow * (size_t)oh * sizeof(uint32_t));
    w = (uint32_t *)malloc((size_t)ow * (size_t)oh * sizeof(uint32_t));
    sc = (uint32_t *)malloc((size_t)ow * (size_t)oh * sizeof(uint32_t));
    xm = (int *)malloc((size_t)ow * (size_t)(1 + INTERP_OBJECTS) * sizeof(int));
    if (b == NULL || w == NULL || sc == NULL || xm == NULL) {
        free(b);
        free(w);
        free(sc);
        free(xm);
        return 1;
    }
    o->base = b;
    o->work = w;
    o->scratch = sc;
    o->xmap = xm;
    o->ow = ow;
    o->oh = oh;
    return 0;
}

void interp_out_free(InterpOut *o)
{
    free(o->base);
    free(o->work);
    free(o->scratch);
    free(o->xmap);
    o->base = o->work = o->scratch = NULL;
    o->xmap = NULL;
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

/* the rectangle [x0, x1) x [y0, y1) of base (and of work) made from the colours of the frame f */
static void base_rect(InterpOut *o, const InterpFrame *f, int x0, int y0, int x1, int y1)
{
    int ox, oy;

    for (oy = y0; oy < y1; oy++) {
        const uint8_t *src = f->colour + src_index(oy, o->oh, RENDER_H, 0) * RENDER_W;
        uint32_t *brow = o->base + (size_t)oy * (size_t)o->ow;
        for (ox = x0; ox < x1; ox++) {
            brow[ox] = o->lut[src[src_index(ox, o->ow, RENDER_W, 0)]];
        }
        memcpy(o->work + (size_t)oy * (size_t)o->ow + x0, brow + x0, (size_t)(x1 - x0) * sizeof(uint32_t));
    }
}

/* the places where the colours of two frames differ, as rectangles of the shown picture: in each band of 8 rows the runs of tiles of 8 picture pixels that differ (a gap of one tile is bridged), a little wider all
 * round.  At most `max` rectangles: when there would be more, one rectangle round them all.  Returns how many */
static int changed_places(const InterpOut *o, const InterpFrame *a, const InterpFrame *b, int rects[][4], int max)
{
    int nr = 0, band, x, y, t;
    double sx_scale = (double)o->ow / RENDER_W, sy_scale = (double)o->oh / RENDER_H;
    int minx = o->ow, miny = o->oh, maxx = 0, maxy = 0;

    for (band = 0; band < RENDER_H / 8; band++) {
        uint8_t tile[RENDER_W / 8];
        int any = 0;

        memset(tile, 0, sizeof tile);
        for (y = band * 8; y < band * 8 + 8; y++) {
            const uint8_t *pa = a->colour + y * RENDER_W, *pb = b->colour + y * RENDER_W;
            if (memcmp(pa, pb, RENDER_W) != 0) {
                for (x = 0; x < RENDER_W; x++) {
                    if (pa[x] != pb[x]) {
                        tile[x >> 3] = 1;
                        any = 1;
                    }
                }
            }
        }
        for (t = 0; any && t < RENDER_W / 8; t++) {
            int t1;
            if (!tile[t]) {
                continue;
            }
            t1 = t;
            while (t1 + 1 < RENDER_W / 8 && (tile[t1 + 1] || (t1 + 2 < RENDER_W / 8 && tile[t1 + 2]))) {
                t1++;
            }
            if (nr < max) {
                rects[nr][0] = (int)(t * 8 * sx_scale) - 2;
                rects[nr][1] = (int)(band * 8 * sy_scale) - 2;
                rects[nr][2] = (int)((t1 + 1) * 8 * sx_scale) + 3;
                rects[nr][3] = (int)((band * 8 + 8) * sy_scale) + 3;
            }
            if (nr >= max || nr == max - 1) {
                /* keep going only to learn the bounding box */
            }
            {
                int r0 = (int)(t * 8 * sx_scale) - 2, r1 = (int)(band * 8 * sy_scale) - 2, r2 = (int)((t1 + 1) * 8 * sx_scale) + 3, r3 = (int)((band * 8 + 8) * sy_scale) + 3;
                if (r0 < minx) { minx = r0; }
                if (r1 < miny) { miny = r1; }
                if (r2 > maxx) { maxx = r2; }
                if (r3 > maxy) { maxy = r3; }
            }
            nr++;
            t = t1;
        }
    }
    if (nr > max) {
        rects[0][0] = minx;
        rects[0][1] = miny;
        rects[0][2] = maxx;
        rects[0][3] = maxy;
        nr = 1;
    }
    for (t = 0; t < nr; t++) {
        if (rects[t][0] < 0) { rects[t][0] = 0; }
        if (rects[t][1] < 0) { rects[t][1] = 0; }
        if (rects[t][2] > o->ow) { rects[t][2] = o->ow; }
        if (rects[t][3] > o->oh) { rects[t][3] = o->oh; }
    }
    return nr;
}

/* the nearer frame changed from `oldf` to `f`: only the places that differ and the places the objects were drawn at are made again, and said in d: the whole picture (13 MB at 2304 x 1440) is not made and sent
 * to the screen sixty times a second for a few moving things.  0 when it is not worth it (more than half of the picture changes) */
static int rebuild_partial(InterpOut *o, const InterpFrame *oldf, const InterpFrame *f, InterpDirty *d)
{
    int rects[INTERP_MAX_RECTS][4], nr, i;
    long area = 0;

    nr = changed_places(o, oldf, f, rects, 48);
    for (i = 0; i < o->nrect && nr < INTERP_MAX_RECTS; i++) {
        memcpy(rects[nr++], o->rect[i], sizeof rects[0]);
    }
    for (i = 0; i < nr; i++) {
        if (rects[i][2] > rects[i][0] && rects[i][3] > rects[i][1]) {
            area += (long)(rects[i][2] - rects[i][0]) * (rects[i][3] - rects[i][1]);
        }
    }
    if (area * 2 > (long)o->ow * o->oh || d->n + nr > INTERP_MAX_RECTS) {
        return 0;
    }
    for (i = 0; i < nr; i++) {
        if (rects[i][2] > rects[i][0] && rects[i][3] > rects[i][1]) {
            base_rect(o, f, rects[i][0], rects[i][1], rects[i][2], rects[i][3]);
            memcpy(d->r[d->n++], rects[i], sizeof rects[0]);
        }
    }
    o->nrect = 0;
    return 1;
}

/* redraw the rectangle [x0, x1) x [y0, y1) of `dst` (a picture of the size of work: work or scratch) from the layers of f, the objects drawn at their offsets (1/FIX pixels) */
static void redraw_to(InterpOut *o, uint32_t *dst, const InterpFrame *f, const int offx[INTERP_OBJECTS], const int offy[INTERP_OBJECTS], int x0, int y0, int x1, int y1)
{
    int ox, oy, k, n = x1 - x0;
    int *bx = o->xmap, *objx[INTERP_OBJECTS];

    for (k = 0; k < INTERP_OBJECTS; k++) {
        objx[k] = o->xmap + (size_t)(k + 1) * (size_t)o->ow;
    }
    for (ox = x0; ox < x1; ox++) {
        bx[ox - x0] = src_index(ox, o->ow, RENDER_W, 0);
        for (k = 0; k < INTERP_OBJECTS; k++) {
            if (f->obj[k].present) {
                objx[k][ox - x0] = src_index(ox, o->ow, RENDER_W, offx[k]);
            }
        }
    }
    (void)n;
    for (oy = y0; oy < y1; oy++) {
        int sy = src_index(oy, o->oh, RENDER_H, 0);
        uint32_t *row = dst + (size_t)oy * (size_t)o->ow;
        int py[INTERP_OBJECTS], act[INTERP_OBJECTS], nact = 0;

        for (k = 0; k < INTERP_OBJECTS; k++) {
            py[k] = f->obj[k].present ? src_index(oy, o->oh, RENDER_H, offy[k]) : -1;
            if (py[k] >= f->obj[k].y0 && py[k] < f->obj[k].y1) {                 /* only the objects that have this row */
                act[nact++] = k;
            }
        }
        for (ox = x0; ox < x1; ox++) {
            int sx = bx[ox - x0], ai;
            uint8_t cov = 0;

            for (ai = 0; ai < nact; ai++) {
                int px;
                k = act[ai];
                px = objx[k][ox - x0];
                if (px >= f->obj[k].x0 && px < f->obj[k].x1) {
                    cov |= (uint8_t)(f->layers.cov[py[k] * RENDER_W + px] & object_mask(k));
                }
            }
            row[ox] = o->lut[render_compose(f->layers.regs[sy], f->layers.prior, f->layers.pri[sy * RENDER_W + sx], f->layers.col[sy * RENDER_W + sx], cov)];
        }
    }
}

static void redraw(InterpOut *o, const InterpFrame *f, const int offx[INTERP_OBJECTS], const int offy[INTERP_OBJECTS], int x0, int y0, int x1, int y1)
{
    redraw_to(o, o->work, f, offx, offy, x0, y0, x1, y1);
}

/* the rectangle [x0, x1) x [y0, y1) of work becomes the mixture of `from` (base, or work itself) and scratch, scratch with the weight a8 / 256 (per channel) */
static void mix_rect(InterpOut *o, const uint32_t *from, int x0, int y0, int x1, int y1, int a8)
{
    int ox, oy;
    uint32_t wa = (uint32_t)(256 - a8), wb = (uint32_t)a8;

    for (oy = y0; oy < y1; oy++) {
        uint32_t *a = o->work + (size_t)oy * (size_t)o->ow;
        const uint32_t *fr = from + (size_t)oy * (size_t)o->ow;
        const uint32_t *b = o->scratch + (size_t)oy * (size_t)o->ow;
        for (ox = x0; ox < x1; ox++) {
            uint32_t pa = fr[ox], pb = b[ox];
            a[ox] = pa;
            if (pa != pb) {
                uint32_t r = (((pa >> 16) & 255u) * wa + ((pb >> 16) & 255u) * wb + 128u) >> 8;
                uint32_t g = (((pa >> 8) & 255u) * wa + ((pb >> 8) & 255u) * wb + 128u) >> 8;
                uint32_t bl = ((pa & 255u) * wa + (pb & 255u) * wb + 128u) >> 8;
                a[ox] = 0xFF000000u | (r << 16) | (g << 8) | bl;
            }
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

/* the offsets (1/FIX of a picture pixel) at which the objects of frame g are drawn at the game time t, from the frame f the time is in */
static void object_offsets(const InterpOut *o, InterpGet get, void *ctx, unsigned long f, unsigned long newest, double t, const InterpFrame *g, int offx[INTERP_OBJECTS], int offy[INTERP_OBJECTS])
{
    double sx_scale = (double)o->ow / RENDER_W, sy_scale = (double)o->oh / RENDER_H;
    int k;

    for (k = 0; k < INTERP_OBJECTS; k++) {
        double tx, ty;
        offx[k] = offy[k] = 0;
        if (g->obj[k].present && f <= newest && !o->still && object_target(get, ctx, f, newest, t, k, &tx, &ty)) {
            /* the offset is the way the object is from the place its frame has it, a whole number of pixels of the picture shown: two moments that put the object on the same pixels make the same picture */
            double dx = tx - g->px[k], dy = ty - g->py[k];
            double px, py;
            if (g->run[k] != get(ctx, f)->run[k] || fabs(dx) > 2.0 * INTERP_MAX_MOVE || fabs(dy) > 2.0 * INTERP_MAX_MOVE) {
                continue;
            }
            px = floor(dx * sx_scale + 0.5);
            py = floor(dy * sy_scale + 0.5);
            offx[k] = (int)floor(px * FIX / sx_scale + 0.5);
            offy[k] = (int)floor(py * FIX / sy_scale + 0.5);
        }
    }
}

/* the box of object ob of its frame drawn at the offset (where it is in its frame and where it is drawn), in the shown picture; 0 when nothing */
static int object_box(const InterpOut *o, const InterpObject *ob, int offx, int offy, int r[4])
{
    double sx_scale = (double)o->ow / RENDER_W, sy_scale = (double)o->oh / RENDER_H;
    double ox0 = ob->x0 + (offx < 0 ? (double)offx / FIX : 0.0), ox1 = ob->x1 + (offx > 0 ? (double)offx / FIX : 0.0);
    double oy0 = ob->y0 + (offy < 0 ? (double)offy / FIX : 0.0), oy1 = ob->y1 + (offy > 0 ? (double)offy / FIX : 0.0);

    r[0] = (int)(ox0 * sx_scale) - 1;
    r[2] = (int)(ox1 * sx_scale) + 2;
    r[1] = (int)(oy0 * sy_scale) - 1;
    r[3] = (int)(oy1 * sy_scale) + 2;
    if (r[0] < 0) { r[0] = 0; }
    if (r[1] < 0) { r[1] = 0; }
    if (r[2] > o->ow) { r[2] = o->ow; }
    if (r[3] > o->oh) { r[3] = o->oh; }
    return r[0] < r[2] && r[1] < r[3];
}

void interp_render(InterpOut *o, InterpGet get, void *ctx, double t, unsigned long newest, InterpDirty *d)
{
    const InterpFrame *near_f, *f1 = NULL;
    unsigned long f, near_id;
    int offx[INTERP_OBJECTS], offy[INTERP_OBJECTS], boffx[INTERP_OBJECTS], boffy[INTERP_OBJECTS], k, i;
    int rebuilt = 0, a8 = 0;

    memset(d, 0, sizeof *d);
    memset(boffx, 0, sizeof boffx);
    memset(boffy, 0, sizeof boffy);
    if (o->base == NULL || t < 0.0) {
        return;
    }
    f = (unsigned long)floor(t);
    near_id = (t - (double)f >= 0.5) ? f + 1 : f;
    if (near_id > newest || get(ctx, near_id) == NULL) {
        near_id = f;
    }
    if (o->blend && f + 1 <= newest && get(ctx, f) != NULL && get(ctx, f + 1) != NULL) {
        a8 = (int)((t - (double)f) * 256.0 + 0.5);
        if (a8 > 255) {
            a8 = 255;
        }
        if (a8 > 0) {
            f1 = get(ctx, f + 1);
            near_id = f;                                    /* the picture is the mixture of f and f + 1, and what is the same in both is the base of f */
        }
    }
    near_f = get(ctx, near_id);
    if (near_f == NULL) {
        return;
    }
    object_offsets(o, get, ctx, f, newest, t, near_f, offx, offy);
    if (f1 != NULL) {
        object_offsets(o, get, ctx, f, newest, t, f1, boffx, boffy);
    }
    if (o->base_valid && o->base_id == near_id && o->last_a8 == a8 && memcmp(offx, o->last_offx, sizeof offx) == 0 && memcmp(offy, o->last_offy, sizeof offy) == 0
        && memcmp(boffx, o->last_boffx, sizeof boffx) == 0 && memcmp(boffy, o->last_boffy, sizeof boffy) == 0) {
        return;                                             /* the same picture as the last one: nothing to do, nothing changed */
    }
    memcpy(o->last_offx, offx, sizeof offx);
    memcpy(o->last_offy, offy, sizeof offy);
    memcpy(o->last_boffx, boffx, sizeof boffx);
    memcpy(o->last_boffy, boffy, sizeof boffy);
    o->last_a8 = a8;
    if (o->base_valid && o->base_id != near_id && o->base_id < near_id + 64 && get(ctx, o->base_id) != NULL && rebuild_partial(o, get(ctx, o->base_id), near_f, d)) {
        o->base_id = near_id;                                /* only the places that changed were made again (they are in d) */
    } else if (!o->base_valid || o->base_id != near_id) {
        build_base(o, near_f);
        o->base_id = near_id;
        o->base_valid = 1;
        memcpy(o->work, o->base, (size_t)o->ow * (size_t)o->oh * sizeof(uint32_t));
        o->nrect = 0;
        d->n = 0;
        rebuilt = 1;
    } else {
        for (i = 0; i < o->nrect; i++) {                    /* put back what the objects of the last picture covered */
            int yy;
            for (yy = o->rect[i][1]; yy < o->rect[i][3]; yy++) {
                memcpy(o->work + (size_t)yy * (size_t)o->ow + o->rect[i][0], o->base + (size_t)yy * (size_t)o->ow + o->rect[i][0], (size_t)(o->rect[i][2] - o->rect[i][0]) * sizeof(uint32_t));
            }
            if (d->n < INTERP_MAX_RECTS) {
                memcpy(d->r[d->n++], o->rect[i], sizeof o->rect[i]);
            } else {
                d->full = 1;
            }
        }
        o->nrect = 0;
    }
    if (f1 != NULL) {
        /* the mixture: the places where the two frames differ, and where their objects are drawn, are made from each frame (the objects of each at the place of this moment) and mixed by how far the moment is */
        int rects[INTERP_MAX_RECTS][4], nr = changed_places(o, near_f, f1, rects, 40), r[4];

        for (i = 0; i < nr && o->nrect < INTERP_MAX_RECTS && d->n < INTERP_MAX_RECTS; i++) {      /* what differs between the frames, objects not moved: the frame f's picture (the base) and the colours of f + 1 */
            int oy;
            if (rects[i][2] <= rects[i][0] || rects[i][3] <= rects[i][1]) {
                continue;
            }
            for (oy = rects[i][1]; oy < rects[i][3]; oy++) {
                const uint8_t *src = f1->colour + src_index(oy, o->oh, RENDER_H, 0) * RENDER_W;
                uint32_t *dst = o->scratch + (size_t)oy * (size_t)o->ow;
                int ox;
                for (ox = rects[i][0]; ox < rects[i][2]; ox++) {
                    dst[ox] = o->lut[src[src_index(ox, o->ow, RENDER_W, 0)]];
                }
            }
            mix_rect(o, o->base, rects[i][0], rects[i][1], rects[i][2], rects[i][3], a8);
            memcpy(o->rect[o->nrect++], rects[i], sizeof rects[0]);
            memcpy(d->r[d->n++], rects[i], sizeof rects[0]);
        }
        for (k = 0; k < INTERP_OBJECTS; k++) {                                                      /* the objects that are drawn at a place of this moment: each frame's drawing of them, mixed */
            int bx0[4], bx1[4], have0 = 0, have1 = 0;
            if (o->nrect >= INTERP_MAX_RECTS - 1 || d->n >= INTERP_MAX_RECTS - 1) {
                break;
            }
            if (near_f->obj[k].present && (offx[k] != 0 || offy[k] != 0)) {
                have0 = object_box(o, &near_f->obj[k], offx[k], offy[k], bx0);
            }
            if (f1->obj[k].present && (boffx[k] != 0 || boffy[k] != 0)) {
                have1 = object_box(o, &f1->obj[k], boffx[k], boffy[k], bx1);
            }
            if (!have0 && !have1) {
                continue;
            }
            if (have0 && have1) {
                r[0] = bx0[0] < bx1[0] ? bx0[0] : bx1[0];
                r[1] = bx0[1] < bx1[1] ? bx0[1] : bx1[1];
                r[2] = bx0[2] > bx1[2] ? bx0[2] : bx1[2];
                r[3] = bx0[3] > bx1[3] ? bx0[3] : bx1[3];
            } else {
                memcpy(r, have0 ? bx0 : bx1, sizeof r);
            }
            redraw(o, near_f, offx, offy, r[0], r[1], r[2], r[3]);
            redraw_to(o, o->scratch, f1, boffx, boffy, r[0], r[1], r[2], r[3]);
            mix_rect(o, o->work, r[0], r[1], r[2], r[3], a8);
            memcpy(o->rect[o->nrect++], r, sizeof r);
            memcpy(d->r[d->n++], r, sizeof r);
        }
    } else {
        for (k = 0; k < INTERP_OBJECTS; k++) {
            const InterpObject *ob = &near_f->obj[k];
            int r[4];

            if (!ob->present || (offx[k] == 0 && offy[k] == 0) || !object_box(o, ob, offx[k], offy[k], r)) {
                continue;
            }
            redraw(o, near_f, offx, offy, r[0], r[1], r[2], r[3]);
            memcpy(o->rect[o->nrect++], r, sizeof r);
            memcpy(d->r[d->n++], r, sizeof r);
        }
    }
    if (rebuilt) {
        d->full = 1;
        d->n = 0;
    }
}
