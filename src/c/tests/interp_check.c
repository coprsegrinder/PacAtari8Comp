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
static uint8_t blob_buf[ASSET_BLOB_MAX], ram_image[65536];
static Assets assets;
static Shell sh;
static Renderer rend;
static InterpFrame *frames;          /* every frame of the game */

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
        if (n >= 300 && n < 420) {
            k.pad[0].left = 1;
        } else {
            k.pad[0].left = 0;
        }
        if (n >= 420 && n < 520) {
            k.pad[0].up = 1;
        } else {
            k.pad[0].up = 0;
        }
        front_frame(&f, &k, &in);
        shell_frame(&sh, &in);
        render_frame_layers(&rend, &sh.world, frames[n].colour, &frames[n].layers);
        interp_prepare(&frames[n]);
    }
}

/* the nearest-pixel picture of a frame at ow x oh, written here independently of interp.c */
static void reference(const InterpFrame *f, int ow, int oh, uint32_t *out)
{
    int x, y;

    for (y = 0; y < oh; y++) {
        for (x = 0; x < ow; x++) {
            int sx = (int)(((2LL * x + 1) * RENDER_W) / (2LL * ow)), sy = (int)(((2LL * y + 1) * RENDER_H) / (2LL * oh));
            uint8_t c = f->colour[sy * RENDER_W + sx];
            out[(size_t)y * (size_t)ow + (size_t)x] = 0xFF000000u | ((uint32_t)NTSC_PALETTE[c][0] << 16) | ((uint32_t)NTSC_PALETTE[c][1] << 8) | NTSC_PALETTE[c][2];
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
static int centroid(const uint32_t *p, int ow, int oh, uint32_t colour, double *cx, double *cy, long *n)
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
    *n = c;
    if (c == 0) {
        return 0;
    }
    *cx = sx / (double)c;
    *cy = sy / (double)c;
    return 1;
}

static void test_ends_and_motion(void)
{
    InterpOut o;
    InterpPair pr;
    uint32_t *ref;
    const int OW = 768, OH = 480;
    int n, k, found = 0;
    InterpDirty dirty;
    size_t px = (size_t)OW * (size_t)OH;

    ref = (uint32_t *)malloc(px * sizeof(uint32_t));
    CHECK(ref != NULL && interp_out_init(&o) == 0 && interp_out_size(&o, OW, OH) == 0);
    /* a pair of frames in which an object moved, and kept its shape */
    for (n = 400; n < NFRAMES - 1 && !found; n++) {      /* a ghost that moved and kept its shape */
        interp_pair(&frames[n], &frames[n + 1], &pr);
        for (k = 0; k < 4; k++) {
            if (pr.ok[k] && (pr.dx[k] != 0 || pr.dy[k] != 0) && frames[n].obj[k].count == frames[n + 1].obj[k].count) {
                found = 1;
                break;
            }
        }
        if (found) {
            break;
        }
    }
    CHECK(found);
    if (!found) {
        free(ref);
        return;
    }
    interp_pair(&frames[n], &frames[n + 1], &pr);
    printf("  frames %d -> %d: object %d moved by (%d, %d) picture pixels\n", n, n + 1, k, pr.dx[k], pr.dy[k]);

    /* phi = 0 is frame A, phi = 1 is frame B, to the pixel */
    interp_render(&o, &frames[n], &frames[n + 1], &pr, 0.0, (unsigned long)n, &dirty);
    reference(&frames[n], OW, OH, ref);
    CHECK(diff(o.work, ref, px) == 0 && dirty.full);
    interp_render(&o, &frames[n], &frames[n + 1], &pr, 1.0, (unsigned long)n, &dirty);
    reference(&frames[n + 1], OW, OH, ref);
    CHECK(diff(o.work, ref, px) == 0);
    interp_render(&o, &frames[n], &frames[n + 1], &pr, 0.0, (unsigned long)n, &dirty);
    interp_render(&o, &frames[n], &frames[n + 1], &pr, 0.0, (unsigned long)n, &dirty);
    CHECK(!dirty.full && dirty.n == 0);                  /* the same picture again: nothing changed */

    /* in between: the picture is not A's and not B's, the object is a fraction of its move on the way, nothing is mixed */
    {
        double phis[5] = {0.0, 0.25, 0.49, 0.5, 0.75};
        double cx[5], cy[5];
        long cnt[5];
        int i, have = 1;
        uint32_t colour;
        uint32_t *seen = (uint32_t *)calloc(256, sizeof(uint32_t));
        size_t j;
        long mixed = 0;
        uint32_t lut[256];

        /* the colour of the object: the colour of one of its pixels */
        {
            int x, y;
            uint8_t c = 0;
            int found_c = 0;
            for (y = frames[n].obj[k].y0; y < frames[n].obj[k].y1 && !found_c; y++) {
                for (x = frames[n].obj[k].x0; x < frames[n].obj[k].x1 && !found_c; x++) {
                    if (frames[n].layers.cov[y * RENDER_W + x] & (1u << k)) {
                        c = frames[n].colour[y * RENDER_W + x];
                        found_c = 1;
                    }
                }
            }
            colour = 0xFF000000u | ((uint32_t)NTSC_PALETTE[c][0] << 16) | ((uint32_t)NTSC_PALETTE[c][1] << 8) | NTSC_PALETTE[c][2];
        }
        for (i = 0; i < 256; i++) {
            lut[i] = 0xFF000000u | ((uint32_t)NTSC_PALETTE[i][0] << 16) | ((uint32_t)NTSC_PALETTE[i][1] << 8) | NTSC_PALETTE[i][2];
        }
        for (i = 0; i < 5; i++) {
            interp_render(&o, &frames[n], &frames[n + 1], &pr, phis[i], (unsigned long)n, &dirty);
            have &= centroid(o.work, OW, OH, colour, &cx[i], &cy[i], &cnt[i]);
        }
        CHECK(have);
        if (have) {
            double s = (double)OW / RENDER_W;
            double ax = cx[0], ay = cy[0];
            /* the frame-B end of the move, measured on the B picture itself */
            double bx = 0.0, by = 0.0;
            long bn;
            reference(&frames[n + 1], OW, OH, ref);
            CHECK(centroid(ref, OW, OH, colour, &bx, &by, &bn));
            printf("  centroid of the object's colour (output pixels, 2 x): A (%.2f, %.2f)  B (%.2f, %.2f)  expected move (%.2f, %.2f)\n", ax, ay, bx, by, pr.dx[k] * s, pr.dy[k] * s);
            for (i = 0; i < 5; i++) {
                double ex = ax + phis[i] * (bx - ax), ey = ay + phis[i] * (by - ay);
                printf("    phi %.2f: (%.2f, %.2f), %ld pixels; straight line from A to B: (%.2f, %.2f)\n", phis[i], cx[i], cy[i], cnt[i], ex, ey);
                CHECK(fabs(cx[i] - ex) <= 1.0 * s && fabs(cy[i] - ey) <= 1.0 * s);        /* on the line from A to B to within a picture pixel */
            }
            CHECK(fabs((cx[3] - ax) - (bx - ax) * 0.5) <= 1.0 * s);
            CHECK(fabs(cx[1] - ax) > 0.0 || fabs(cy[1] - ay) > 0.0 || (pr.dx[k] == 0 && pr.dy[k] == 0));
        }
        /* a picture in between is neither A's nor B's, but every pixel of it is a colour of the game: no mixing */
        interp_render(&o, &frames[n], &frames[n + 1], &pr, 0.25, (unsigned long)n, &dirty);
        reference(&frames[n], OW, OH, ref);
        CHECK(diff(o.work, ref, px) > 0);
        for (j = 0; j < px; j++) {
            int c;
            for (c = 0; c < 256; c++) {
                if (lut[c] == o.work[j]) {
                    seen[c] = 1;
                    break;
                }
            }
            if (c == 256) {
                mixed++;
            }
        }
        CHECK(mixed == 0);
        {
            int colours = 0, c;
            for (c = 0; c < 256; c++) {
                colours += seen[c] != 0;
            }
            CHECK(colours >= 2 && colours <= 12);       /* the picture of a game uses few colours; a mix would add many */
        }
        free(seen);
    }
    /* sweeping phi: only rows near the objects change between two pictures of one nearest frame */
    interp_render(&o, &frames[n], &frames[n + 1], &pr, 0.10, (unsigned long)n, &dirty);
    interp_render(&o, &frames[n], &frames[n + 1], &pr, 0.20, (unsigned long)n, &dirty);
    CHECK(!dirty.full && dirty.n > 0);
    {
        uint32_t *keep = (uint32_t *)malloc(px * sizeof(uint32_t));
        int yy, xx, i2;
        long outside = 0;
        interp_render(&o, &frames[n], &frames[n + 1], &pr, 0.10, (unsigned long)n, &dirty);
        memcpy(keep, o.work, px * sizeof(uint32_t));
        interp_render(&o, &frames[n], &frames[n + 1], &pr, 0.20, (unsigned long)n, &dirty);
        for (yy = 0; yy < OH; yy++) {
            for (xx = 0; xx < OW; xx++) {
                int in = 0;
                for (i2 = 0; i2 < dirty.n; i2++) {
                    in |= xx >= dirty.r[i2][0] && xx < dirty.r[i2][2] && yy >= dirty.r[i2][1] && yy < dirty.r[i2][3];
                }
                if (!in && keep[(size_t)yy * (size_t)OW + (size_t)xx] != o.work[(size_t)yy * (size_t)OW + (size_t)xx]) {
                    outside++;
                }
            }
        }
        CHECK(outside == 0);                                /* what is reported as changed covers all that changed */
        free(keep);
    }
    interp_out_free(&o);
    free(ref);
}

/* an object that jumps, appears or vanishes is not moved */
static void test_jumps(void)
{
    InterpOut o;
    InterpPair pr;
    InterpFrame *a = &frames[400], *b = (InterpFrame *)malloc(sizeof *b);
    uint32_t *ref;
    int x, y, k;
    InterpDirty dirty;
    const int OW = 768, OH = 480;
    size_t px = (size_t)OW * (size_t)OH;

    ref = (uint32_t *)malloc(px * sizeof(uint32_t));
    CHECK(b != NULL && ref != NULL);
    for (k = 0; k < 4; k++) {
        if (a->obj[k].present) {
            break;
        }
    }
    CHECK(k < 4);
    *b = *a;                                              /* frame b: player k thrown 40 pixels to the right (a tunnel, a respawn) */
    memset(b->layers.cov, 0, sizeof b->layers.cov);
    for (y = 0; y < RENDER_H; y++) {
        for (x = 0; x < RENDER_W; x++) {
            uint8_t v = a->layers.cov[y * RENDER_W + x];
            if (v & (1u << k)) {
                if (x + 40 < RENDER_W) {
                    b->layers.cov[y * RENDER_W + x + 40] |= (uint8_t)(1u << k);
                }
                v = (uint8_t)(v & ~(1u << k));
            }
            b->layers.cov[y * RENDER_W + x] |= v;
        }
    }
    interp_prepare(b);
    interp_pair(a, b, &pr);
    CHECK(!pr.ok[k]);
    interp_out_init(&o);
    interp_out_size(&o, OW, OH);
    interp_render(&o, a, b, &pr, 0.25, 400, &dirty);
    reference(a, OW, OH, ref);
    CHECK(diff(o.work, ref, px) == 0);                    /* not moved: exactly the nearer frame's picture */
    interp_render(&o, a, b, &pr, 0.75, 400, &dirty);
    memset(b->layers.cov, 0, sizeof b->layers.cov);       /* the object vanishes */
    interp_prepare(b);
    interp_pair(a, b, &pr);
    CHECK(!pr.ok[k]);
    interp_out_free(&o);
    free(b);
    free(ref);
}

/* a 2304 x 1440 picture (a 6 x scale: the 3440 x 1440 and the 2560 x 1440 screens) takes how long, and a 1152 x 720 one */
static void test_cost(void)
{
    InterpOut o;
    InterpPair pr;
    const int sizes[3][2] = {{1152, 720}, {2304, 1440}, {3456, 2160}};
    int s, i, n0 = 500, kk;
    InterpDirty dirty;

    for (; n0 < NFRAMES - 60; n0++) {                     /* a pair in which something moves */
        interp_pair(&frames[n0], &frames[n0 + 1], &pr);
        for (kk = 0; kk < INTERP_OBJECTS && !(pr.ok[kk] && (pr.dx[kk] || pr.dy[kk])); kk++) {
        }
        if (kk < INTERP_OBJECTS) {
            break;
        }
    }
    interp_out_init(&o);
    for (s = 0; s < 3; s++) {
        clock_t t;
        double ms_move, ms_full;
        interp_out_size(&o, sizes[s][0], sizes[s][1]);
        interp_pair(&frames[n0], &frames[n0 + 1], &pr);
        interp_render(&o, &frames[n0], &frames[n0 + 1], &pr, 0.1, (unsigned long)n0, &dirty);
        t = clock();
        for (i = 0; i < 200; i++) {
            interp_render(&o, &frames[n0], &frames[n0 + 1], &pr, 0.05 + 0.002 * i, (unsigned long)n0, &dirty);
        }
        ms_move = (double)(clock() - t) * 1000.0 / CLOCKS_PER_SEC / 200.0;
        t = clock();
        for (i = 0; i < 40; i++) {
            interp_render(&o, &frames[n0 + i], &frames[n0 + 1 + i], &pr, 0.1, (unsigned long)(n0 + i), &dirty);
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
    test_ends_and_motion();
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
