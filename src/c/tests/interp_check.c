/* The in-between pictures of the FPS option (src/c/render/interp.c, docs/69): made from real frames of a played game.  Needs the asset blob (install_assets). */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "../assets/assets.h"
#include "../assets/rom_install.h"
#include "../render/interp.h"
#include "../render/palette.h"
#include "../shell/frontend.h"
#include "../shell/shell.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

#define NFRAMES 900
#define OW 768
#define OH 480
static uint8_t blob_buf[ASSET_BLOB_MAX], ram_image[65536];
static Assets assets;
static Shell sh;
static Renderer rend;
static InterpFrame *frames;          /* every frame of the game */
static unsigned long g_limit;        /* the newest frame the getter shows: the game is that far */

static const InterpFrame *get_game(void *ctx, unsigned long id)
{
    (void)ctx;
    return id <= g_limit && id < NFRAMES ? &frames[id] : NULL;
}

typedef struct Two {
    const InterpFrame *f[2];
} Two;

static const InterpFrame *get_two(void *ctx, unsigned long id)
{
    return id < 2 ? ((Two *)ctx)->f[id] : NULL;
}

static void play(void)
{
    Frontend f;
    FrontKeys k;
    FrameInput in;
    int n;

    shell_init(&sh, ram_image + 0x3000, 4242u, 0);
    render_init(&rend, ram_image);
    front_init(&f, 0);
    memset(&k, 0, sizeof k);
    for (n = 0; n < NFRAMES; n++) {
        k.start = (uint8_t)(n >= 100 && n < 106);
        k.pad[0].left = (uint8_t)(n >= 300 && n < 420);
        k.pad[0].up = (uint8_t)(n >= 420 && n < 520);
        front_frame(&f, &k, &in);
        shell_frame(&sh, &in);
        render_frame_layers(&rend, &sh.world, frames[n].colour, &frames[n].layers);
        interp_prepare(&frames[n]);
        interp_follow(&frames[n], n > 0 ? &frames[n - 1] : NULL);
    }
}

static uint32_t rgb_of(uint8_t c)
{
    return 0xFF000000u | ((uint32_t)NTSC_PALETTE[c][0] << 16) | ((uint32_t)NTSC_PALETTE[c][1] << 8) | NTSC_PALETTE[c][2];
}

/* the nearest-pixel picture of a frame at OW x OH, written here independently of interp.c */
static void reference(const InterpFrame *f, uint32_t *out)
{
    int x, y;

    for (y = 0; y < OH; y++) {
        for (x = 0; x < OW; x++) {
            int sx = (int)(((2LL * x + 1) * RENDER_W) / (2LL * OW)), sy = (int)(((2LL * y + 1) * RENDER_H) / (2LL * OH));
            out[(size_t)y * (size_t)OW + (size_t)x] = rgb_of(f->colour[sy * RENDER_W + sx]);
        }
    }
}

static size_t diff(const uint32_t *a, const uint32_t *b, size_t n)
{
    size_t i, d = 0;

    for (i = 0; i < n; i++) {
        d += a[i] != b[i];
    }
    return d;
}

/* centroid (in output pixels) of the pixels that are this colour */
static int centroid_n(const uint32_t *p, int ow, int oh, uint32_t colour, double *cx, double *cy)
{
    int x, y;
    double sx = 0, sy = 0;
    long c = 0;

    for (y = 0; y < oh; y++) {
        for (x = 0; x < ow; x++) {
            if (p[(size_t)y * (size_t)ow + (size_t)x] == colour) {
                sx += x;
                sy += y;
                c++;
            }
        }
    }
    if (c == 0) {
        return 0;
    }
    *cx = sx / (double)c;
    *cy = sy / (double)c;
    return 1;
}

static int centroid(const uint32_t *p, uint32_t colour, double *cx, double *cy)
{
    return centroid_n(p, OW, OH, colour, cx, cy);
}

static uint32_t object_colour(const InterpFrame *f, int k)
{
    int x, y;

    for (y = f->obj[k].y0; y < f->obj[k].y1; y++) {
        for (x = f->obj[k].x0; x < f->obj[k].x1; x++) {
            if (f->layers.cov[y * RENDER_W + x] & (1u << k)) {
                return rgb_of(f->colour[y * RENDER_W + x]);
            }
        }
    }
    return 0;
}

/* the playfield alone: a picture of the title screen at any moment is the picture of the frame */
static void test_still(void)
{
    InterpOut o;
    InterpDirty d;
    uint32_t *ref = (uint32_t *)malloc((size_t)OW * OH * sizeof(uint32_t));
    const size_t px = (size_t)OW * OH;

    CHECK(ref != NULL && interp_out_init(&o) == 0 && interp_out_size(&o, OW, OH) == 0);
    g_limit = 90;
    reference(&frames[70], ref);
    interp_render(&o, get_game, NULL, 70.0, 90, &d);
    CHECK(d.full && diff(o.work, ref, px) == 0);
    interp_render(&o, get_game, NULL, 70.4, 90, &d);
    CHECK(!d.full && d.n == 0 && diff(o.work, ref, px) == 0);          /* the same picture again: nothing changed */
    reference(&frames[71], ref);
    interp_render(&o, get_game, NULL, 70.6, 90, &d);                   /* nothing moves on the title screen: the next frame's playfield */
    CHECK(diff(o.work, ref, px) == 0);
    interp_out_free(&o);
    free(ref);
}

/* a ghost between two of its steps: it glides the whole time, and is where the game put it when the game did */
static void test_glide(void)
{
    InterpOut o;
    InterpDirty d;
    uint32_t *ref = (uint32_t *)malloc((size_t)OW * OH * sizeof(uint32_t));
    unsigned long n, e0 = 0, e1 = 0;
    int k = 0, found = 0, i, steps, distinct = 0;
    const double s = (double)OW / RENDER_W;
    uint32_t colour = 0;
    double ax = 0, ay = 0, bx = 0, by = 0, lastx = -1e9, lasty = -1e9;

    CHECK(ref != NULL && interp_out_init(&o) == 0 && interp_out_size(&o, OW, OH) == 0);
    for (n = 450; n + 8 < NFRAMES && !found; n++) {                    /* a ghost with two steps in a row three frames apart */
        for (k = 0; k < 4; k++) {
            if (frames[n].mv[k] && frames[n + 3].mv[k] && !frames[n + 1].mv[k] && !frames[n + 2].mv[k] && frames[n + 3].run[k] == frames[n].run[k] && frames[n + 3].obj[k].present &&
                frames[n + 3].obj[k].count == frames[n].obj[k].count) {
                e0 = n;
                e1 = n + 3;
                found = 1;
                break;
            }
        }
    }
    CHECK(found);
    if (!found) {
        free(ref);
        return;
    }
    colour = object_colour(&frames[e0], k);
    CHECK(colour != 0);
    printf("  ghost %d: steps at frames %lu and %lu, from (%d, %d) to (%d, %d)\n", k, e0, e1, frames[e0].px[k], frames[e0].py[k], frames[e1].px[k], frames[e1].py[k]);
    g_limit = e1 + 2;                                                  /* the next step is made: the way is the straight one between the two steps */
    reference(&frames[e0], ref);
    CHECK(centroid(ref, colour, &ax, &ay));
    reference(&frames[e1], ref);
    CHECK(centroid(ref, colour, &bx, &by));
    steps = 4 * (int)(e1 - e0);
    for (i = 0; i <= steps; i++) {
        double t = (double)e0 + (double)i / 4.0, cx = 0, cy = 0, u = (double)i / (double)steps, ex = ax + (bx - ax) * u, ey = ay + (by - ay) * u;
        interp_render(&o, get_game, NULL, t, g_limit, &d);
        CHECK(centroid(o.work, colour, &cx, &cy));
        if (i == 0 || i == steps || i == steps / 2) {
            printf("    t = e0 + %.2f: centre (%.2f, %.2f); the straight way from (%.2f, %.2f) to (%.2f, %.2f) is at (%.2f, %.2f)\n", (double)i / 4.0, cx, cy, ax, ay, bx, by, ex, ey);
        }
        CHECK(fabs(cx - ex) <= 1.2 * s && fabs(cy - ey) <= 1.2 * s);   /* on the straight way (the shape may change by a pixel when the ghost's feet do) */
        if (fabs(cx - lastx) + fabs(cy - lasty) > 0.25) {
            distinct++;
        }
        lastx = cx;
        lasty = cy;
    }
    CHECK(distinct >= 3);                                              /* it is at several places in between (a step is 2 game pixels = 4 output pixels here); the native game has two places for these 3 frames */
    /* the next step not yet made: the ghost goes on the way it went, and no further than one step */
    {
        double cx0 = 0, cy0 = 0, cx1 = 0, cy1 = 0, v, one_step = hypot(bx - ax, by - ay);
        g_limit = e1;
        interp_render(&o, get_game, NULL, (double)e1, g_limit, &d);
        CHECK(centroid(o.work, colour, &cx0, &cy0));
        g_limit = e1 + 1;                                              /* the game is one frame ahead and the next step is not there yet */
        interp_render(&o, get_game, NULL, (double)e1 + 0.99, g_limit, &d);
        CHECK(centroid(o.work, colour, &cx1, &cy1));
        v = hypot(cx1 - cx0, cy1 - cy0);
        printf("    the next step not made yet: the ghost went %.2f output pixels in the frame after its step (one step is %.2f)\n", v, one_step);
        CHECK(v <= one_step + 1.5 * s);
        CHECK(fabs((cx1 - cx0) * (bx - ax)) + fabs((cy1 - cy0) * (by - ay)) >= 0.0 && ((cx1 - cx0) * (bx - ax) + (cy1 - cy0) * (by - ay) >= -1.0));   /* the way of the step before, not back */
    }
    interp_out_free(&o);
    free(ref);
}

/* the point of it: the motion of a ghost over 140 frames of play is smoother than the game's own, which moves it in steps; measured on the pictures (the centre of the ghost's colour, sampled at 180 a second):
 * the unevenness of the speed is the spread of the steps between pictures divided by their mean, over stretches of steady movement */
static double unevenness(int native, unsigned long newest_ahead, uint32_t colour, int k)
{
    InterpOut o;
    InterpDirty d;
    double xs[1200], ys[1200], total = 0.0;
    int n = 0, w, i, stretches = 0;
    double t;
    const int W = 36;
    const int UW = 1536, UH = 960;                       /* a 4 x picture: a step of the game is 8 pixels, not 4 */

    interp_out_init(&o);
    interp_out_size(&o, UW, UH);
    g_limit = NFRAMES - 1;
    for (t = 460.0; t < 600.0 && n < 1200; t += 1.0 / 3.0) {
        double cx = 0, cy = 0;
        unsigned long newest = (unsigned long)floor(t) + newest_ahead;
        interp_render(&o, get_game, NULL, native ? floor(t) : t, newest, &d);
        if (!centroid_n(o.work, UW, UH, colour, &cx, &cy)) {
            cx = cy = -1.0;
        }
        xs[n] = cx;
        ys[n] = cy;
        n++;
    }
    for (w = 0; w + W < n; w += W) {
        double v[36], m = 0.0, sd = 0.0;
        int ok = 1, steps = 0;
        unsigned long f0 = 460u + (unsigned long)w / 3u;
        for (i = 0; i < 12; i++) {
            steps += frames[f0 + (unsigned long)i].mv[k];
        }
        if (steps < 3) {
            continue;                                      /* a stretch with fewer than three steps in 12 frames is a stop or a start, not steady movement */
        }
        for (i = 0; i < W; i++) {
            if (xs[w + i] < 0 || xs[w + i + 1] < 0) {
                ok = 0;
                break;
            }
            v[i] = hypot(xs[w + i + 1] - xs[w + i], ys[w + i + 1] - ys[w + i]);
            m += v[i];
        }
        if (!ok) {
            continue;
        }
        m /= W;
        if (m < 0.1) {
            continue;                                      /* not moving steadily */
        }
        for (i = 0; i < W; i++) {
            sd += (v[i] - m) * (v[i] - m);
        }
        total += sqrt(sd / W) / m;
        stretches++;
    }
    interp_out_free(&o);
    return stretches > 0 ? total / stretches : -1.0;
}

static void test_smoothness(void)
{
    int k, best = -1;
    double nat, in1, in2;
    unsigned long n;
    long moves[4] = {0, 0, 0, 0};

    for (n = 460; n < 600; n++) {
        for (k = 0; k < 4; k++) {
            moves[k] += frames[n].mv[k];
        }
    }
    for (k = 0; k < 4; k++) {
        if (best < 0 || moves[k] > moves[best]) {
            best = k;
        }
    }
    CHECK(moves[best] >= 20);
    nat = unevenness(1, 0, object_colour(&frames[500], best), best);
    in1 = unevenness(0, 1, object_colour(&frames[500], best), best);
    in2 = unevenness(0, 2, object_colour(&frames[500], best), best);
    printf("  ghost %d, %ld steps in 140 frames: unevenness of its speed %.2f in the game's own pictures (a 4 x picture, 12-frame stretches with at least 3 steps); %.2f with the in-between pictures (game 1 frame ahead), %.2f (2 frames ahead)\n", best, moves[best], nat, in1, in2);
    CHECK(nat > 0.0 && in1 > 0.0 && in1 < nat * 0.5 && in2 <= in1 + 0.05);                 /* at least twice as even */
}

/* nothing is mixed: every pixel is a colour of the game */
static void test_no_mixing(void)
{
    InterpOut o;
    InterpDirty d;
    uint32_t lut[256];
    unsigned long n;
    long mixed = 0;
    int i, t;
    const size_t px = (size_t)OW * OH;

    for (i = 0; i < 256; i++) {
        lut[i] = rgb_of((uint8_t)i);
    }
    CHECK(interp_out_init(&o) == 0 && interp_out_size(&o, OW, OH) == 0);
    g_limit = NFRAMES - 1;
    for (n = 500; n < 530; n++) {
        for (t = 0; t < 8; t++) {
            size_t j;
            interp_render(&o, get_game, NULL, (double)n + (double)t / 8.0, g_limit, &d);
            for (j = 0; j < px; j++) {
                int c;
                for (c = 0; c < 256 && lut[c] != o.work[j]; c++) {
                }
                mixed += c == 256;
            }
        }
    }
    CHECK(mixed == 0);
    interp_out_free(&o);
}

/* an object that jumps or vanishes is not moved */
static void test_jumps(void)
{
    static InterpFrame two[2];
    InterpOut o;
    InterpDirty d;
    Two ctx;
    uint32_t *ref = (uint32_t *)malloc((size_t)OW * OH * sizeof(uint32_t));
    const size_t px = (size_t)OW * OH;
    int x, y, k;

    two[0] = frames[400];
    for (k = 0; k < 4 && !two[0].obj[k].present; k++) {
    }
    CHECK(k < 4 && ref != NULL);
    two[1] = two[0];                                       /* frame 2: player k thrown 40 pixels to the right (a tunnel, a respawn) */
    memset(two[1].layers.cov, 0, sizeof two[1].layers.cov);
    for (y = 0; y < RENDER_H; y++) {
        for (x = 0; x < RENDER_W; x++) {
            uint8_t v = two[0].layers.cov[y * RENDER_W + x];
            if (v & (1u << k)) {
                if (x + 40 < RENDER_W) {
                    two[1].layers.cov[y * RENDER_W + x + 40] |= (uint8_t)(1u << k);
                }
                v = (uint8_t)(v & ~(1u << k));
            }
            two[1].layers.cov[y * RENDER_W + x] |= v;
        }
    }
    interp_prepare(&two[1]);
    interp_follow(&two[0], NULL);
    interp_follow(&two[1], &two[0]);
    CHECK(two[1].run[k] != two[0].run[k] && !two[1].mv[k]);        /* a new run: not a move */
    ctx.f[0] = &two[0];
    ctx.f[1] = &two[1];
    CHECK(interp_out_init(&o) == 0 && interp_out_size(&o, OW, OH) == 0);
    interp_render(&o, get_two, &ctx, 0.25, 1, &d);
    reference(&two[0], ref);
    CHECK(diff(o.work, ref, px) == 0);                     /* not moved: exactly the nearer frame's picture */
    interp_render(&o, get_two, &ctx, 0.75, 1, &d);
    CHECK(o.base_id == 1);                                      /* the nearer frame is the other one now */
    memset(two[1].layers.cov, 0, sizeof two[1].layers.cov);        /* the object vanishes */
    interp_prepare(&two[1]);
    interp_follow(&two[1], &two[0]);
    CHECK(!two[1].obj[k].present && two[1].run[k] != two[0].run[k]);
    interp_out_free(&o);
    free(ref);
}

/* Pac-Man is eaten away and a score takes his place (a ghost eaten): the score is not Pac-Man moved, so it does not glide from his place (the owner saw it as a rubber band) */
static void test_score_replaces_pacman(void)
{
    static InterpFrame two[2];
    Two ctx;
    InterpOut o;
    InterpDirty d;
    double x = 0, y = 0;
    int px, py, k = 4, kept = 0;

    two[0] = frames[500];
    CHECK(two[0].obj[k].present && two[0].obj[k].count > 60);
    two[1] = two[0];
    memset(two[1].layers.cov, 0, sizeof two[1].layers.cov);
    for (py = two[0].obj[k].y0; py < two[0].obj[k].y1; py++) {                 /* frame 2: only the first rows of the shape, 6 pixels to the left: a small shape, as digits are */
        for (px = two[0].obj[k].x0; px < two[0].obj[k].x1; px++) {
            if ((two[0].layers.cov[py * RENDER_W + px] & 0xF0u) && py < two[0].obj[k].y0 + 4 && px >= 6) {
                two[1].layers.cov[py * RENDER_W + px - 6] |= two[0].layers.cov[py * RENDER_W + px] & 0xF0u;
                kept++;
            }
        }
    }
    CHECK(kept > 8 && kept < two[0].obj[k].count * 6 / 10);
    interp_prepare(&two[1]);
    interp_follow(&two[0], NULL);
    interp_follow(&two[1], &two[0]);
    CHECK(two[1].run[k] != two[0].run[k]);                                    /* not the same object: a new run */
    ctx.f[0] = &two[0];
    ctx.f[1] = &two[1];
    CHECK(interp_place(get_two, &ctx, 0.25, 1, k, &x, &y) && x == two[0].px[k] && y == two[0].py[k]);
    CHECK(interp_place(get_two, &ctx, 0.75, 1, k, &x, &y) && x == two[0].px[k] && y == two[0].py[k]);     /* no way between the two: it stays where the game has it */
    CHECK(interp_out_init(&o) == 0 && interp_out_size(&o, OW, OH) == 0);
    interp_render(&o, get_two, &ctx, 0.25, 1, &d);
    interp_render(&o, get_two, &ctx, 0.45, 1, &d);
    CHECK(!d.full && d.n == 0);                                                /* not a pixel of it moved before the other frame is the nearer one */
    interp_out_free(&o);
}

/* a 2304 x 1440 picture (a 6 x scale) takes how long: a picture of the same nearest frame, and one when the nearest frame changes */
static void test_cost(void)
{
    InterpOut o;
    InterpDirty d;
    const int sizes[3][2] = {{1152, 720}, {2304, 1440}, {3456, 2160}};
    int s, i;

    interp_out_init(&o);
    g_limit = NFRAMES - 1;
    for (s = 0; s < 3; s++) {
        clock_t t;
        double ms_move, ms_full;
        interp_out_size(&o, sizes[s][0], sizes[s][1]);
        interp_render(&o, get_game, NULL, 500.0, g_limit, &d);
        t = clock();
        for (i = 0; i < 200; i++) {
            interp_render(&o, get_game, NULL, 500.0 + 0.0123 * i, g_limit, &d);
        }
        ms_move = (double)(clock() - t) * 1000.0 / CLOCKS_PER_SEC / 200.0;
        t = clock();
        for (i = 0; i < 40; i++) {
            interp_render(&o, get_game, NULL, 520.0 + (double)i, g_limit, &d);
        }
        ms_full = (double)(clock() - t) * 1000.0 / CLOCKS_PER_SEC / 40.0;
        printf("  %dx%d: a picture of the same nearest frame %.3f ms, with a new nearest frame (base rebuilt) %.3f ms\n", sizes[s][0], sizes[s][1], ms_move, ms_full);
    }
    interp_out_free(&o);
}

/* the picture made k times as wide, brought back to its width: the colours of each group averaged */
static void test_box(void)
{
    uint32_t src[16], dst[4];
    const uint32_t a = 0xFF000000u, b = 0xFF0080FFu;                    /* black and a colour: B 0xFF, G 0x80, R 0x00 */
    int i;

    for (i = 0; i < 16; i++) {
        src[i] = i < 6 ? a : b;                                         /* black for 6 pixels, then the colour: the edge falls inside the second group of 4 */
    }
    interp_box_x(src, 16, 1, 4, dst);
    CHECK(dst[0] == a && dst[3] == b);                                  /* groups wholly in one colour are not changed */
    CHECK(dst[1] == (0xFF000000u | (0u << 16) | (((2u * 0x80u + 2u) / 4u) << 8) | ((2u * 0xFFu + 2u) / 4u)));    /* two of four: half of the colour */
    CHECK(dst[2] == b);
    {
        static uint32_t same[16];
        interp_box_x(src, 16, 1, 1, same);                              /* k = 1: a copy */
        CHECK(memcmp(same, src, sizeof same) == 0);
    }
}

/* what a CRT shader is given: the in-between picture made 8 times as wide, averaged back to 384 x 240.  On a still screen it is the game's picture exactly; with a ghost on its way it differs from the picture of
 * the nearer frame only around that ghost, and only in the pixels at its left and right edges (the average of a ghost colour and the background), never inside it */
static void test_crt_source(void)
{
    enum { K = 8, W = 384 * K };
    static uint32_t wide[W * 240], narrow[384 * 240], ref[384 * 240];
    InterpOut o;
    InterpDirty d;
    int x, y, found = 0, k = 0;
    unsigned long n, e0 = 0;

    CHECK(interp_out_init(&o) == 0 && interp_out_size(&o, W, 240) == 0);
    g_limit = 90;
    interp_render(&o, get_game, NULL, 70.3, 90, &d);
    interp_box_x(o.work, W, 240, K, narrow);
    for (y = 0; y < 240; y++) {
        for (x = 0; x < 384; x++) {
            ref[y * 384 + x] = rgb_of(frames[70].colour[y * 384 + x]);
        }
    }
    CHECK(memcmp(narrow, ref, sizeof ref) == 0);                              /* a still screen: the game's picture, pixel for pixel */
    for (n = 450; n + 8 < NFRAMES && !found; n++) {                           /* a ghost between two steps */
        for (k = 0; k < 4; k++) {
            if (frames[n].mv[k] && frames[n + 3].mv[k] && !frames[n + 1].mv[k] && !frames[n + 2].mv[k] && frames[n + 3].run[k] == frames[n].run[k] && frames[n + 3].obj[k].present && frames[n + 3].px[k] != frames[n].px[k] && frames[n + 3].py[k] == frames[n].py[k]) {
                e0 = n;
                found = 1;
                break;
            }
        }
    }
    CHECK(found);
    if (found) {
        long outside = 0, edge_blend = 0;
        g_limit = e0 + 5;
        interp_render(&o, get_game, NULL, (double)e0 + 1.0 + 0.0, g_limit, &d);        /* the frame after the step: the ghost is on the way to the next step */
        interp_render(&o, get_game, NULL, (double)e0 + 1.4, g_limit, &d);
        memcpy(wide, o.work, sizeof wide);
        interp_box_x(wide, W, 240, K, narrow);
        for (y = 0; y < 240; y++) {
            for (x = 0; x < 384; x++) {
                uint32_t want = rgb_of(frames[o.base_id].colour[y * 384 + x]);
                if (narrow[y * 384 + x] != want) {
                    int near_object = 0, q;
                    for (q = 0; q < INTERP_OBJECTS; q++) {                        /* around any of the objects: they all glide */
                        const InterpObject *oq = &frames[o.base_id].obj[q];
                        near_object |= oq->present && x >= oq->x0 - 4 && x <= oq->x1 + 4 && y >= oq->y0 - 1 && y <= oq->y1 + 1;
                    }
                    if (!near_object) {
                        outside++;
                    } else {
                        edge_blend++;
                    }
                }
            }
        }
        printf("  a ghost on its way: %ld pixels differ from the nearer frame's picture around it (the edges of the objects on their way), %ld elsewhere\n", edge_blend, outside);
        CHECK(outside == 0 && edge_blend > 0 && edge_blend < 400);
    }
    interp_out_free(&o);
}

/* the animation of the game is the game's: whatever the number of pictures a second (1, 2, 3, 5 and 7 to a game frame), every game frame is the nearer one for some picture, in order, none left out (the mouth of
 * Pac-Man goes through all its shapes as in the native picture: the shape of a picture is the shape of the nearer frame) */
static void test_every_frame_shown(void)
{
    static const int per_frame[5] = {1, 2, 3, 5, 7};          /* pictures to a game frame: 60, 120, 180, 300, 420 a second */
    int pf, bad_order = 0, left_out = 0, k;

    for (pf = 0; pf < 5; pf++) {
        InterpOut o;
        InterpDirty d;
        unsigned long last = 0, n = 0;
        long seen[400];

        memset(seen, 0, sizeof seen);
        CHECK(interp_out_init(&o) == 0 && interp_out_size(&o, 384, 240) == 0);
        g_limit = NFRAMES - 1;
        for (n = 500; n < 700; n++) {
            for (k = 0; k < per_frame[pf]; k++) {
                double t = (double)n + (double)k / (double)per_frame[pf];
                interp_render(&o, get_game, NULL, t, g_limit, &d);
                if (o.base_id < last || o.base_id > last + 1) {
                    bad_order += last != 0;
                }
                last = o.base_id;
                seen[o.base_id - 500 < 400 ? o.base_id - 500 : 399]++;
            }
        }
        for (n = 501; n < 699; n++) {
            left_out += seen[n - 500] == 0;                        /* a game frame no picture of which was the nearer one */
        }
        interp_out_free(&o);
    }
    CHECK(bad_order == 0);
    CHECK(left_out == 0);
}

/* fewer pictures a second than the game makes (30): the picture is the game's own frame, no object moved, at any moment: pixel for pixel the nearest-pixel picture of that frame */
static void test_still_mode(void)
{
    InterpOut o;
    InterpDirty d;
    uint32_t *ref = (uint32_t *)malloc((size_t)OW * OH * sizeof(uint32_t));
    unsigned long n;
    long wrong = 0, moved = 0;
    const size_t px = (size_t)OW * OH;

    CHECK(ref != NULL && interp_out_init(&o) == 0 && interp_out_size(&o, OW, OH) == 0);
    o.still = 1;
    g_limit = NFRAMES - 1;
    for (n = 500; n < 560; n += 2) {                                       /* every second frame, as the 30 choice shows them */
        double t = (double)n + (n % 4 == 0 ? 0.0 : 0.7);                   /* whatever the moment: the frame is the one the caller names (t is its number) */
        (void)t;
        interp_render(&o, get_game, NULL, (double)n, g_limit, &d);
        reference(&frames[n], ref);
        wrong += diff(o.work, ref, px) != 0;
        CHECK(o.base_id == n);
    }
    CHECK(wrong == 0);
    o.still = 0;                                                           /* and with objects allowed to glide, some of the same pictures differ from the game's frame */
    for (n = 500; n < 560; n += 2) {
        interp_render(&o, get_game, NULL, (double)n + 0.3, g_limit, &d);
        reference(&frames[n], ref);
        moved += diff(o.work, ref, px) != 0;
    }
    CHECK(moved > 0);
    interp_out_free(&o);
    free(ref);
}

/* the pictures made by changing only what changed (the nearer frame changes: the bands that differ, the places of the objects) are, pixel for pixel, the pictures made from nothing, over 600 pictures of play at 3 to a game frame
 * and at two sizes; and the places in d are enough to bring the last picture the program showed to this one (what is sent to the screen) */
static void test_partial_equals_full(void)
{
    static const int sizes[2][2] = {{OW, OH}, {1152, 720}};
    int si;

    for (si = 0; si < 2; si++) {
        InterpOut keep, fresh;
        InterpDirty d;
        uint32_t *shown;
        unsigned long n;
        int k, wrong = 0, short_d = 0, partial = 0, pics = 0;
        size_t px = (size_t)sizes[si][0] * (size_t)sizes[si][1];

        shown = (uint32_t *)malloc(px * sizeof(uint32_t));
        CHECK(shown != NULL && interp_out_init(&keep) == 0 && interp_out_init(&fresh) == 0);
        CHECK(interp_out_size(&keep, sizes[si][0], sizes[si][1]) == 0 && interp_out_size(&fresh, sizes[si][0], sizes[si][1]) == 0);
        g_limit = NFRAMES - 1;
        for (n = 300; n < 500; n++) {
            for (k = 0; k < 3; k++) {
                double t = (double)n + (double)k / 3.0;
                int i, y;
                interp_render(&keep, get_game, NULL, t, g_limit, &d);
                fresh.base_valid = 0;                                           /* made from nothing */
                fresh.nrect = 0;
                interp_render(&fresh, get_game, NULL, t, g_limit, &d);
                (void)d;
                wrong += diff(keep.work, fresh.work, px) != 0;
                pics++;
                (void)i;
                (void)y;
            }
        }
        CHECK(wrong == 0);
        CHECK(pics == 600);
        /* what is sent: the picture shown, brought up to date with the rectangles of d, is the picture */
        memcpy(shown, keep.work, px * sizeof(uint32_t));
        interp_out_free(&keep);
        interp_out_init(&keep);
        interp_out_size(&keep, sizes[si][0], sizes[si][1]);
        interp_render(&keep, get_game, NULL, 300.0, g_limit, &d);
        memcpy(shown, keep.work, px * sizeof(uint32_t));
        for (n = 300; n < 420; n++) {
            for (k = 0; k < 3; k++) {
                double t = (double)n + (double)k / 3.0;
                int i, y;
                interp_render(&keep, get_game, NULL, t, g_limit, &d);
                if (d.full) {
                    memcpy(shown, keep.work, px * sizeof(uint32_t));
                } else {
                    partial += d.n > 0;
                    for (i = 0; i < d.n; i++) {
                        for (y = d.r[i][1]; y < d.r[i][3]; y++) {
                            memcpy(shown + (size_t)y * (size_t)sizes[si][0] + d.r[i][0], keep.work + (size_t)y * (size_t)sizes[si][0] + d.r[i][0], (size_t)(d.r[i][2] - d.r[i][0]) * sizeof(uint32_t));
                        }
                    }
                }
                short_d += diff(shown, keep.work, px) != 0;
            }
        }
        CHECK(short_d == 0);
        CHECK(partial > 50);                                                    /* and the places are used (not the whole picture each time) */
        interp_out_free(&keep);
        interp_out_free(&fresh);
        free(shown);
    }
}

/* the mixture of two game frames (o.blend): with the objects not moved (still) the picture at the moment n + a is, pixel for pixel and channel for channel, the picture of frame n and the picture of frame n + 1 mixed
 * with the weight a / 256 for the second; at a whole frame it is that frame's picture; and the places given in d bring the last picture shown to this one, with the objects gliding too */
static uint32_t mix_px(uint32_t pa, uint32_t pb, int a8)
{
    uint32_t wa = (uint32_t)(256 - a8), wb = (uint32_t)a8;

    if (pa == pb) {
        return pa;
    }
    return 0xFF000000u | (((((pa >> 16) & 255u) * wa + ((pb >> 16) & 255u) * wb + 128u) >> 8) << 16) | (((((pa >> 8) & 255u) * wa + ((pb >> 8) & 255u) * wb + 128u) >> 8) << 8) | ((((pa & 255u) * wa + (pb & 255u) * wb + 128u) >> 8));
}

static void test_blend(void)
{
    InterpOut o;
    InterpDirty d;
    uint32_t *ra = (uint32_t *)malloc((size_t)OW * OH * sizeof(uint32_t)), *rb = (uint32_t *)malloc((size_t)OW * OH * sizeof(uint32_t)), *shown = (uint32_t *)malloc((size_t)OW * OH * sizeof(uint32_t));
    unsigned long n;
    int k, wrong = 0, whole_wrong = 0, short_d = 0, mixed = 0, glide_short = 0;
    size_t px = (size_t)OW * OH, i;

    CHECK(ra != NULL && rb != NULL && shown != NULL && interp_out_init(&o) == 0 && interp_out_size(&o, OW, OH) == 0);
    g_limit = NFRAMES - 1;
    o.still = 1;
    o.blend = 1;
    for (n = 400; n < 440; n++) {
        for (k = 0; k < 4; k++) {
            int a8 = k * 64;
            double t = (double)n + (double)a8 / 256.0;
            interp_render(&o, get_game, NULL, t, g_limit, &d);
            reference(&frames[n], ra);
            reference(&frames[n + 1], rb);
            if (a8 == 0) {
                whole_wrong += diff(o.work, ra, px) != 0;
            } else {
                int bad = 0;
                for (i = 0; i < px; i++) {
                    bad += o.work[i] != mix_px(ra[i], rb[i], a8);
                    mixed += ra[i] != rb[i];
                }
                wrong += bad != 0;
            }
        }
    }
    CHECK(whole_wrong == 0);
    CHECK(wrong == 0);
    CHECK(mixed > 0);                                                         /* and the frames do differ: the test means something */
    o.still = 0;                                                              /* with the objects gliding: the places in d are enough */
    interp_out_free(&o);
    interp_out_init(&o);
    interp_out_size(&o, OW, OH);
    o.blend = 1;
    interp_render(&o, get_game, NULL, 400.0, g_limit, &d);
    memcpy(shown, o.work, px * sizeof(uint32_t));
    for (n = 400; n < 520; n++) {
        for (k = 0; k < 3; k++) {
            int j, y;
            interp_render(&o, get_game, NULL, (double)n + (double)k / 3.0, g_limit, &d);
            if (d.full) {
                memcpy(shown, o.work, px * sizeof(uint32_t));
            } else {
                for (j = 0; j < d.n; j++) {
                    for (y = d.r[j][1]; y < d.r[j][3]; y++) {
                        memcpy(shown + (size_t)y * OW + d.r[j][0], o.work + (size_t)y * OW + d.r[j][0], (size_t)(d.r[j][2] - d.r[j][0]) * sizeof(uint32_t));
                    }
                }
            }
            short_d += diff(shown, o.work, px) != 0;
            glide_short += 0;
        }
    }
    CHECK(short_d == 0);
    CHECK(glide_short == 0);
    interp_out_free(&o);
    free(ra);
    free(rb);
    free(shown);
}

int main(void)
{
    if (assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) != ASSETS_OK || assets_install_tables(&assets) != ASSETS_OK) {
        printf("interp_check: the asset blob is not there (run install_assets)\n");
        return 2;
    }
    assets_ram_image(&assets, ram_image);
    frames = (InterpFrame *)malloc((size_t)NFRAMES * sizeof(InterpFrame));
    if (frames == NULL) {
        return 2;
    }
    play();
    test_still();
    test_glide();
    test_smoothness();
    test_no_mixing();
    test_box();
    test_every_frame_shown();
    test_still_mode();
    test_partial_equals_full();
    test_blend();
    test_crt_source();
    test_jumps();
    test_score_replaces_pacman();
    test_cost();
    free(frames);
    if (failures == 0) {
        printf("interp_check: OK\n");
        return 0;
    }
    printf("interp_check: %d failures\n", failures);
    return 1;
}
