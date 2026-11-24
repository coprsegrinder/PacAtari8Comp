/* The audit of the in-between pictures (docs/69), run over whole games by tools/check_interp.py: for every frame of every replay given, the places an object is drawn at between that frame and the next
 * (the quarters of a frame, with the game one or two frames ahead as in the program) are checked against what the game itself did, so that no in-between picture shows anything the native picture does not:
 *   C1  an object that is not the same object in the next frame (it appears, vanishes, jumps, or becomes another shape: a ghost eaten and its eyes, Pac-Man and the score that takes his place) is not moved:
 *       it stays on the place the game has it;
 *   C2  an object is never further from the place the game has it than one step of its own (the longest step it makes in the frames around), so nothing runs away from where the game puts it;
 *   C3  the way the match says an object moved agrees with the way its pixels moved (their centre of mass): a match across two different shapes does not;
 *   C4  two frames that are called the same object have shapes of a similar size.
 * Usage: interp_audit [--root DIR] [--similar PERCENT] [--quiet] [--breaks] REPLAY...      Prints one line a replay and the totals; exit 1 when a check failed. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../assets/assets.h"
#include "../assets/rom_install.h"
#include "../platform/fs.h"
#include "../render/interp.h"
#include "../shell/replay.h"
#include "../shell/shell.h"

#define RING 32

static uint8_t replay_buf[1u << 24], blob_buf[ASSET_BLOB_MAX], ram_image[65536];
static Assets assets;
static Shell shell;
static Renderer renderer;
static Replay replay;
static InterpFrame ring[RING];
static unsigned long ring_id[RING];
static int ring_ok[RING];

static const InterpFrame *get_ring(void *ctx, unsigned long id)
{
    size_t s = (size_t)(id % RING);

    (void)ctx;
    return ring_ok[s] && ring_id[s] == id ? &ring[s] : NULL;
}

static int g_breaks;                                         /* --breaks: list the pairs whose object is in both frames and is not called the same */

typedef struct Totals {
    long frames, samples, c1_fail, c2_fail, c3_fail, c4_fail, c1_checked, c2_checked, c3_checked, c4_checked, moved_samples;
    double worst_dev;
} Totals;

static void centre_of_mass(const InterpFrame *f, int k, double *cx, double *cy)
{
    int x, y;
    double sx = 0, sy = 0, n = 0;
    uint8_t m = k < 4 ? (uint8_t)(1u << k) : (uint8_t)0xF0u;

    for (y = f->obj[k].y0; y < f->obj[k].y1; y++) {
        for (x = f->obj[k].x0; x < f->obj[k].x1; x++) {
            if (f->layers.cov[y * RENDER_W + x] & m) {
                sx += x;
                sy += y;
                n += 1.0;
            }
        }
    }
    *cx = n > 0 ? sx / n : 0.0;
    *cy = n > 0 ? sy / n : 0.0;
}

static void audit_frame(unsigned long n, Totals *t, int verbose, const char *name)
{
    int k, q, la;

    if (g_breaks && n > 0) {              /* the pairs whose object is in both frames and is not called the same: how alike they were */
        const InterpFrame *c2 = get_ring(NULL, n), *p2 = get_ring(NULL, n - 1);
        InterpPair pr;
        if (c2 != NULL && p2 != NULL) {
            interp_pair(p2, c2, &pr);
            for (k = 0; k < INTERP_OBJECTS; k++) {
                if (p2->obj[k].present && c2->obj[k].present && !pr.ok[k]) {
                    printf("BREAK %lu %d %d %d %d\n", n, k, p2->obj[k].count, c2->obj[k].count, pr.similar[k]);
                }
            }
        }
    }
    for (k = 0; k < INTERP_OBJECTS; k++) {                       /* C3 and C4 on the pair (n - 1, n) */
        const InterpFrame *cur = get_ring(NULL, n), *prev = n > 0 ? get_ring(NULL, n - 1) : NULL;
        if (cur != NULL && prev != NULL && cur->obj[k].present && prev->obj[k].present && cur->run[k] == prev->run[k]) {
            double ax, ay, bx, by;
            int dx = cur->px[k] - prev->px[k], dy = cur->py[k] - prev->py[k];
            int lo = prev->obj[k].count < cur->obj[k].count ? prev->obj[k].count : cur->obj[k].count;
            int hi = prev->obj[k].count < cur->obj[k].count ? cur->obj[k].count : prev->obj[k].count;
            centre_of_mass(prev, k, &ax, &ay);
            centre_of_mass(cur, k, &bx, &by);
            t->c3_checked++;
            if (fabs((bx - ax) - dx) > 3.0 || fabs((by - ay) - dy) > 3.0) {
                t->c3_fail++;
                if (verbose && t->c3_fail <= 5) {
                    printf("    %s: C3 frame %lu object %d: matched as a move of (%d, %d), its pixels' centre of mass moved by (%.1f, %.1f)\n", name, n, k, dx, dy, bx - ax, by - ay);
                }
            }
            t->c4_checked++;
            if (hi > 0 && lo * 100 < hi * 50) {
                t->c4_fail++;
                if (verbose && t->c4_fail <= 5) {
                    printf("    %s: C4 frame %lu object %d: %d pixels and %d pixels called one object\n", name, n, k, prev->obj[k].count, cur->obj[k].count);
                }
            }
        }
    }
    for (la = 1; la <= 2; la++) {                                /* the game one frame ahead of the picture (the least) and two */
        unsigned long f;
        if (n < (unsigned long)la + 1u) {
            continue;
        }
        f = n - (unsigned long)la;
        {
            int steps[INTERP_OBJECTS];                               /* C2's bound: the longest step each object makes in the frames around f */
            const InterpFrame *ff = get_ring(NULL, f), *f1 = get_ring(NULL, f + 1);
            unsigned long e;
            if (ff == NULL || f1 == NULL) {
                continue;
            }
            for (k = 0; k < INTERP_OBJECTS; k++) {
                steps[k] = 0;
            }
            for (e = (f > 10 ? f - 10 : 1); e <= f + 10 && e <= n; e++) {
                const InterpFrame *fe = get_ring(NULL, e), *fp = get_ring(NULL, e - 1);
                for (k = 0; fe != NULL && fp != NULL && k < INTERP_OBJECTS; k++) {
                    if (fe->run[k] == ff->run[k] && fp->run[k] == ff->run[k] && fe->mv[k]) {
                        int sx = abs(fe->px[k] - fp->px[k]), sy = abs(fe->py[k] - fp->py[k]);
                        steps[k] = sx > steps[k] ? sx : steps[k];
                        steps[k] = sy > steps[k] ? sy : steps[k];
                    }
                }
            }
            for (q = 0; q < 4; q++) {
                double tm = (double)f + (double)q / 4.0;
                for (k = 0; k < INTERP_OBJECTS; k++) {
                    double x, y, dev;
                    if (!ff->obj[k].present) {
                        continue;
                    }
                    t->samples++;
                    if (!interp_place(get_ring, NULL, tm, n, k, &x, &y)) {
                        continue;
                    }
                    dev = hypot(x - ff->px[k], y - ff->py[k]);
                    if (dev > 0.0) {
                        t->moved_samples++;
                    }
                    if (dev > t->worst_dev) {
                        t->worst_dev = dev;
                    }
                    if (!f1->obj[k].present || f1->run[k] != ff->run[k]) {          /* C1: not the same object in the next frame: stays where the game has it */
                        t->c1_checked++;
                        if (dev > 1e-6) {
                            t->c1_fail++;
                            if (verbose && t->c1_fail <= 5) {
                                printf("    %s: C1 frame %lu object %d at t = %.2f: the object is not the same in the next frame but is %.2f pixels from the game's place\n", name, f, k, tm, dev);
                            }
                        }
                    } else {
                        t->c2_checked++;                                              /* C2: no further than the longest step it makes in the frames around */
                        if (dev > (double)steps[k] + 1e-6) {
                            t->c2_fail++;
                            if (verbose && t->c2_fail <= 5) {
                                printf("    %s: C2 frame %lu object %d at t = %.2f: %.2f pixels from the game's place, its steps are %d\n", name, f, k, tm, dev, steps[k]);
                            }
                        }
                    }
                }
            }
        }
    }
}

int main(int argc, char **argv)
{
    Totals total;
    int i, failed = 0, verbose = 1;

    memset(&total, 0, sizeof total);
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--root") == 0 && i + 1 < argc) {
            pm_fs_set_root(argv[++i]);
        } else if (strcmp(argv[i], "--similar") == 0 && i + 1 < argc) {
            interp_similar_percent = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--quiet") == 0) {
            verbose = 0;
        } else if (strcmp(argv[i], "--breaks") == 0) {
            g_breaks = 1;
        }
    }
    if (assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) != ASSETS_OK || assets_install_tables(&assets) != ASSETS_OK) {
        printf("interp_audit: the asset blob is not there\n");
        return 2;
    }
    assets_ram_image(&assets, ram_image);
    for (i = 1; i < argc; i++) {
        FrameInput in;
        Totals t;
        unsigned long n = 0;

        if (argv[i][0] == '-' && argv[i][1] == '-') {
            if (strcmp(argv[i], "--root") == 0 || strcmp(argv[i], "--similar") == 0) {
                i++;
            }
            continue;
        }
        if (replay_load(&replay, argv[i], replay_buf, sizeof replay_buf) != REPLAY_OK) {
            printf("interp_audit: cannot read %s\n", argv[i]);
            return 2;
        }
        memset(&t, 0, sizeof t);
        memset(ring_ok, 0, sizeof ring_ok);
        shell_init(&shell, ram_image + 0x3000, replay.seed, replay.start_clock);
        render_init(&renderer, ram_image);
        while (replay_next(&replay, &in)) {
            size_t slot = (size_t)(n % RING), prev = (size_t)((n + RING - 1) % RING);
            shell_frame(&shell, &in);
            render_frame_layers(&renderer, &shell.world, ring[slot].colour, &ring[slot].layers);
            interp_prepare(&ring[slot]);
            interp_follow(&ring[slot], (n > 0 && ring_ok[prev] && ring_id[prev] == n - 1) ? &ring[prev] : NULL);
            ring_ok[slot] = 1;
            ring_id[slot] = n;
            audit_frame(n, &t, verbose, argv[i]);
            n++;
        }
        t.frames = (long)n;
        printf("%s: %ld frames, %ld places checked (%ld not on the game's own place, the furthest %.2f pixels); C1 %ld/%ld, C2 %ld/%ld, C3 %ld/%ld, C4 %ld/%ld failed\n", argv[i], t.frames, t.samples, t.moved_samples, t.worst_dev,
               t.c1_fail, t.c1_checked, t.c2_fail, t.c2_checked, t.c3_fail, t.c3_checked, t.c4_fail, t.c4_checked);
        total.frames += t.frames;
        total.samples += t.samples;
        total.moved_samples += t.moved_samples;
        total.c1_fail += t.c1_fail;
        total.c2_fail += t.c2_fail;
        total.c3_fail += t.c3_fail;
        total.c4_fail += t.c4_fail;
        total.c1_checked += t.c1_checked;
        total.c2_checked += t.c2_checked;
        total.c3_checked += t.c3_checked;
        total.c4_checked += t.c4_checked;
        if (t.worst_dev > total.worst_dev) {
            total.worst_dev = t.worst_dev;
        }
    }
    failed = total.c1_fail + total.c2_fail + total.c3_fail + total.c4_fail > 0;
    printf("TOTAL: %ld frames, %ld places checked (%ld away from the game's place by the in-between pictures, the furthest %.2f pixels); C1 %ld of %ld failed, C2 %ld of %ld, C3 %ld of %ld, C4 %ld of %ld\n", total.frames, total.samples, total.moved_samples,
           total.worst_dev, total.c1_fail, total.c1_checked, total.c2_fail, total.c2_checked, total.c3_fail, total.c3_checked, total.c4_fail, total.c4_checked);
    printf("interp_audit: %s\n", failed ? "FAILED" : "OK");
    return failed ? 1 : 0;
}
