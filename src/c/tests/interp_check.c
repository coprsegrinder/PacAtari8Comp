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
    CHECK(d.full);                                         /* the nearer frame is the other one now */
    memset(two[1].layers.cov, 0, sizeof two[1].layers.cov);        /* the object vanishes */
    interp_prepare(&two[1]);
    interp_follow(&two[1], &two[0]);
    CHECK(!two[1].obj[k].present && two[1].run[k] != two[0].run[k]);
    interp_out_free(&o);
    free(ref);
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
    test_jumps();
    test_cost();
    free(frames);
    if (failures == 0) {
        printf("interp_check: OK\n");
        return 0;
    }
    printf("interp_check: %d failures\n", failures);
    return 1;
}
