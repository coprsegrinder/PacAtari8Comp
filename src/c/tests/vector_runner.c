/* The vector runner (docs/51 section 2, stage 75b).
 *   vector_runner [--root DIR] [--fn NAME] [--chain] [--platform] [--check-format] FILE
 * Loads a vector file through platform/fs.c, and for every call: unpacks the "before" World, hands the call its arguments and its RANDOM values, runs the function,
 * and compares the whole World (every region), the ordered chip writes, the return value and the number of RANDOM values used with what the file says.
 * Exit: 0 all equal, 1 a difference, 2 the file is bad or refused, 3 no C function for this set (the stage that writes it is not done).
 * The functions are in tests/world_functions.c (the World calls) and tests/pure_functions.c (the pure calls). */
#include <stdio.h>
#include <string.h>

#include "../core/random_feed.h"
#include "../core/world.h"
#include "../core/gtia.h"
#include "pure_functions.h"
#include "world_functions.h"
#include "vector.h"
#include "boot_tables.h"

static const char *region_of(size_t state_index, size_t *within)
{
    size_t i, k = 0;
    for (i = 0; i < PM_WORLD_REGIONS; i++) {
        if (state_index < k + world_regions[i].count) {
            *within = state_index - k;
            return world_regions[i].name;
        }
        k += world_regions[i].count;
    }
    *within = 0;
    return "?";
}

static void print_value(const VecValue *v)
{
    int32_t i, total = 0;
    if (v->tag == 0) {
        printf("%d", (int)v->n);
    } else if (v->tag == 2) {
        printf("None");
    } else {
        if (v->tag == 1) {
            total = v->n;
        } else {
            for (i = 0; i < v->n; i++) {
                total += v->sub_len[i];
            }
        }
        printf("[");
        for (i = 0; i < total; i++) {
            printf("%s%d", i ? ", " : "", (int)v->seq[i]);
        }
        printf("]");
    }
}

static void print_pure_difference(uint32_t k, const PureVec *in, const VecValue *got, int status, int rnd_ok)
{
    int i;
    printf("  call %u: args (", (unsigned)k);
    for (i = 0; i < in->nargs; i++) {
        printf("%s", i ? ", " : "");
        print_value(&in->args[i]);
    }
    if (status != 0) {
        printf("): arguments of the wrong shape\n");
        return;
    }
    printf("): got ");
    print_value(got);
    printf(", expected ");
    print_value(&in->result);
    printf("%s\n", rnd_ok ? "" : " (and a different number of RANDOM values used)");
}

/* ---- the collision scenes (stage 77a): the registers of the scene by the C model, with the latch the record asks for */
static SceneVec scene_rec;

static int run_scenes(VecFile *vf, const char *path, int check_format, int via_world, int vis_lo, int vis_hi, int line_lo, int line_hi)
{
    static World sw;
    static uint8_t latch[16];
    uint32_t k, bad = 0, compared = 0;
    const char *err[1] = {""};

    memset(latch, 0, sizeof latch);
    for (k = 0; k < vf->count; k++) {
        GtiaScene sc;
        uint8_t shown[16], got[16];
        int i, differs = 0;

        if (vec_next_scene(vf, &scene_rec, err) != 0) {
            printf("%s: call %u: %s\n", path, (unsigned)k, err[0]);
            vec_close(vf);
            return 2;
        }
        if (check_format) {
            continue;
        }
        if (scene_rec.mode == 0 || scene_rec.mode == 1) {
            memset(latch, 0, sizeof latch);
        } else if (scene_rec.mode == 3) {
            memcpy(latch, scene_rec.latch_in, 16);
        }
        if (via_world) {
            /* the World path: the scene is what the World leaves on the screen; a HITCLR in the chip-write log clears the latch (platform_iface.GtiaCollisions.frame_done) */
            GtiaLatch gl;
            world_init(&sw);
            memcpy(sw.hpos, scene_rec.hpos, 8);
            memcpy(sw.pm, scene_rec.pages[0], 256);
            for (i = 0; i < 4; i++) {
                memcpy(sw.pm + 0x100 * (i + 1), scene_rec.pages[i + 1], 256);
            }
            memcpy(sw.maze, scene_rec.cells, VEC_SCENE_CELLS);
            memcpy(gl.reg, latch, 16);
            if (scene_rec.mode == 1) {
                world_pokey(&sw, 0xD01E, 0);
            }
            gtia_latch_frame_done(&gl, &sw, vf->charset);
            memcpy(got, gl.reg, 16);
        } else {
            sc.hpos = scene_rec.hpos;
            sc.missile_page = scene_rec.pages[0];
            for (i = 0; i < 4; i++) {
                sc.player_pages[i] = scene_rec.pages[i + 1];
            }
            sc.cells = scene_rec.cells;
            sc.charset = vf->charset;
            gtia_collision_registers(&sc, vis_lo, vis_hi, line_lo, line_hi, shown);
            for (i = 0; i < 16; i++) {
                got[i] = (uint8_t)(latch[i] | shown[i]);
            }
        }
        memcpy(latch, got, 16);
        for (i = 0; i < 16; i++) {
            if ((scene_rec.mask >> i) & 1) {
                if (got[i] != scene_rec.expected[i]) {
                    if (bad < 8 && !differs) {
                        printf("  scene %u: register %d (D0%02X) = %02x, expected %02x\n", (unsigned)k, i, i, got[i], scene_rec.expected[i]);
                    }
                    differs = 1;
                }
            }
        }
        if (scene_rec.mask) {
            compared++;
        }
        if (differs) {
            bad++;
        }
    }
    if (check_format) {
        printf("%s: %u scenes of '%s': format ok\n", path, (unsigned)vf->count, vf->name);
    } else {
        printf("%s: %u scenes of '%s': %u compared, %u equal, %u different\n", path, (unsigned)vf->count, vf->name, (unsigned)compared, (unsigned)(compared - bad), (unsigned)bad);
    }
    vec_close(vf);
    return bad == 0 ? 0 : 1;
}

static World world;
static WorldVec rec;
static uint8_t got[PM_STATE_SIZE];

/* returns the number of differences found in this call and prints the first few */
static int compare(uint32_t index, const RandomFeed *rf, int32_t ret, int shown_so_far)
{
    int n = 0;
    size_t i;
    uint32_t k;

    world_pack(&world, got);
    for (i = 0; i < PM_STATE_SIZE; i++) {
        if (got[i] != rec.after[i]) {
            size_t within;
            const char *name = region_of(i, &within);
            if (n + shown_so_far < 8) {
                printf("  call %u: %s[%u] = %02x, expected %02x\n", (unsigned)index, name, (unsigned)within, got[i], rec.after[i]);
            }
            n++;
        }
    }
    if (world.pokey_n != rec.npokey || world.pokey_overflow != 0) {
        if (n + shown_so_far < 8) {
            printf("  call %u: %u chip writes (%u lost), expected %u\n", (unsigned)index, (unsigned)world.pokey_n, (unsigned)world.pokey_overflow, (unsigned)rec.npokey);
        }
        n++;
    } else {
        for (k = 0; k < rec.npokey; k++) {
            if (world.pokey_addr[k] != rec.pokey_addr[k] || world.pokey_val[k] != rec.pokey_val[k]) {
                if (n + shown_so_far < 8) {
                    printf("  call %u: chip write %u = (%04x, %02x), expected (%04x, %02x)\n", (unsigned)index, (unsigned)k, world.pokey_addr[k], world.pokey_val[k], rec.pokey_addr[k], rec.pokey_val[k]);
                }
                n++;
                break;
            }
        }
    }
    if (rf->used != rec.nrnd || rf->overrun != 0) {
        if (n + shown_so_far < 8) {
            printf("  call %u: RANDOM used %u (%u beyond the supplied), expected %u\n", (unsigned)index, (unsigned)rf->used, (unsigned)rf->overrun, (unsigned)rec.nrnd);
        }
        n++;
    }
    if (rec.has_ret && ret != rec.ret) {
        if (n + shown_so_far < 8) {
            printf("  call %u: returned %d, expected %d\n", (unsigned)index, (int)ret, (int)rec.ret);
        }
        n++;
    }
    return n;
}

int main(int argc, char **argv)
{
    const char *path = NULL, *fname = NULL, *err[1] = {""};
    int check_format = 0, chain = 0, via_world = 0, i;
    int vis_lo = GTIA_VISIBLE_LO, vis_hi = GTIA_VISIBLE_HI, line_lo = GTIA_LINE_LO, line_hi = GTIA_LINE_HI;
    VecFile vf;
    static PureVec pure;
    WorldFn fn = NULL;
    PureFn pfn = NULL;
    uint32_t bad_calls = 0;
    int shown = 0;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--root") == 0 && i + 1 < argc) {
            if (pm_fs_set_root(argv[++i]) != 0) {
                printf("bad main folder\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--fn") == 0 && i + 1 < argc) {
            fname = argv[++i];
        } else if (strcmp(argv[i], "--visible") == 0 && i + 1 < argc) {
            if (sscanf(argv[++i], "%d,%d", &vis_lo, &vis_hi) != 2) {
                printf("bad --visible\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--lines") == 0 && i + 1 < argc) {
            if (sscanf(argv[++i], "%d,%d", &line_lo, &line_hi) != 2) {
                printf("bad --lines\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--via-world") == 0) {
            via_world = 1;
        } else if (strcmp(argv[i], "--platform") == 0) {
            fname = "platform.run_frame";
        } else if (strcmp(argv[i], "--chain") == 0) {
            chain = 1;
        } else if (strcmp(argv[i], "--check-format") == 0) {
            check_format = 1;
        } else {
            path = argv[i];
        }
    }
    if (path == NULL) {
        printf("usage: vector_runner [--root DIR] [--fn NAME] [--chain] [--platform] [--check-format] FILE\n");
        return 2;
    }
    if (boot_tables() != 0) {
        return 2;
    }
    if (vec_open(&vf, path, err) != 0) {
        printf("%s: %s\n", path, err[0]);
        return 2;
    }
    if (fname == NULL) {
        fname = vf.name;
    }
    if (!check_format) {
        if (vf.kind == 1) {
            fn = world_lookup(fname);
        }
        if (vf.kind == 2) {
            pfn = pure_lookup(fname);
        }
        if ((vf.kind == 3 && strncmp(fname, "gtia.", 5) != 0) || (vf.kind != 3 && fn == NULL && pfn == NULL)) {
            printf("%s: %u calls of '%s': no C function yet\n", path, (unsigned)vf.count, fname);
            vec_close(&vf);
            return 3;
        }
    }
    if (vf.kind == 3) {
        return run_scenes(&vf, path, check_format, via_world, vis_lo, vis_hi, line_lo, line_hi);
    }
    if (vf.kind == 2) {
        uint32_t k, bad = 0;
        static VecValue got;
        for (k = 0; k < vf.count; k++) {
            int rnd_ok = 1, st;
            if (vec_next_pure(&vf, &pure, err) != 0) {
                printf("%s: call %u: %s\n", path, (unsigned)k, err[0]);
                vec_close(&vf);
                return 2;
            }
            if (check_format) {
                continue;
            }
            st = pfn(&pure, &got, &rnd_ok);
            if (st != 0 || !rnd_ok || !value_equal(&got, &pure.result)) {
                if (bad < 8) {
                    print_pure_difference(k, &pure, &got, st, rnd_ok);
                }
                bad++;
            }
        }
        if (check_format) {
            printf("%s: %u pure calls of '%s': format ok\n", path, (unsigned)vf.count, vf.name);
        } else {
            printf("%s: %u calls of '%s': %u equal, %u different\n", path, (unsigned)vf.count, vf.name, (unsigned)(vf.count - bad), (unsigned)bad);
        }
        vec_close(&vf);
        return bad == 0 ? 0 : 1;
    }
    {
        uint32_t k;
        /* --chain: a call whose "before" is the previous call's "after" with the clock (RTCLOK2) advanced by one is the next frame of the same run;
         * the C then goes on from the state it made itself, not from the file's, so a difference that only shows after several frames is not hidden */
        static uint8_t prev_after[PM_STATE_SIZE], expect_before[PM_STATE_SIZE];
        int prev_ok = 0, in_chain = 0;
        uint32_t chain_len = 0, longest = 0, chained = 0, chains = 0;

        for (k = 0; k < vf.count; k++) {
            RandomFeed rf;
            int32_t ret = 0;
            int d;
            if (vec_next_world(&vf, &rec, err) != 0) {
                printf("%s: call %u: %s\n", path, (unsigned)k, err[0]);
                vec_close(&vf);
                return 2;
            }
            if (check_format) {
                continue;
            }
            in_chain = 0;
            if (chain && prev_ok) {
                memcpy(expect_before, prev_after, PM_STATE_SIZE);
                expect_before[0x14] = (uint8_t)(expect_before[0x14] + 1u);       /* RTCLOK2 */
                in_chain = memcmp(expect_before, rec.before, PM_STATE_SIZE) == 0;
            }
            if (in_chain) {
                world.pokey_n = 0;
                world.pokey_overflow = 0;
                world.RTCLOK2 = (uint8_t)(world.RTCLOK2 + 1u);
                chained++;
                chain_len++;
            } else {
                if (chain_len > longest) {
                    longest = chain_len;
                }
                chain_len = 1;
                chains++;
                world_init(&world);
                world_unpack(&world, rec.before);
            }
            memcpy(prev_after, rec.after, PM_STATE_SIZE);
            prev_ok = 1;
            random_feed_init(&rf, rec.rnd, rec.nrnd);
            if (fn(&world, rec.args, rec.nargs, &rf, &ret) != 0) {
                printf("  call %u: arguments of the wrong shape\n", (unsigned)k);
                bad_calls++;
                shown++;
                continue;
            }
            d = compare(k, &rf, ret, shown);
            if (d > 0) {
                bad_calls++;
                shown += d;
                prev_ok = 0;                                  /* the next call starts again from the file's state */
            }
        }
        if (chain_len > longest) {
            longest = chain_len;
        }
        if (chain && !check_format) {
            printf("%s: chain mode: %u frames run from the state the C had made itself, in %u runs (longest %u frames)\n", path, (unsigned)chained, (unsigned)chains, (unsigned)longest);
        }
    }
    if (check_format) {
        printf("%s: %u calls of '%s': format ok\n", path, (unsigned)vf.count, vf.name);
        vec_close(&vf);
        return 0;
    }
    printf("%s: %u calls of '%s': %u equal, %u different\n", path, (unsigned)vf.count, vf.name, (unsigned)(vf.count - bad_calls), (unsigned)bad_calls);
    vec_close(&vf);
    return bad_calls == 0 ? 0 : 1;
}
