/* Stage 77b: checks of the platform layer.
 *   platform_check                       the POKEY RANDOM model: full period, distinct states, the shape of the byte, the all-ones seed; the scripted platform's calls
 *   platform_check --bits N              prints the bit 8 of the counter after each of N steps from seed 0 (tests/test_c_platform.py compares it with tools/pokey_noise.py)
 *   platform_check --gtia STATEFILE CHARSET   runs frames on the scripted platform with the GTIA collisions and checks the latch frame by frame against an independent computation
 *   platform_check --frames STATEFILE    packed World states (PM_STATE_SIZE bytes each, relative to the main folder): runs frames on the scripted platform and checks determinism, the
 *                                        different seed, "inputs only through the platform" (poisoned input fields change nothing) and the count of every input call */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../app/run_frame.h"
#include "../core/gtia.h"
#include "../core/world.h"
#include "../platform/fs.h"
#include "../platform/hal_scripted.h"
#include "../platform/pokey_random.h"
#include "boot_tables.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static uint8_t seen[(PM_POKEY_POLY17_PERIOD + 7) / 8 + 1];

static void pokey_tests(void)
{
    PokeyRandom r;
    uint32_t start, i, ones7 = 0;
    static uint32_t hist[16];

    pokey_random_init(&r, 0x1FFFF);
    CHECK(r.poly == 0);                                       /* the all-ones state is replaced */
    pokey_random_init(&r, 0x12345);
    start = r.poly;
    memset(seen, 0, sizeof seen);
    for (i = 0; i < PM_POKEY_POLY17_PERIOD; i++) {
        CHECK(r.poly != 0x1FFFF);                             /* the all-ones state never occurs */
        if (seen[r.poly >> 3] & (1u << (r.poly & 7u))) {
            printf("state repeated after %u steps\n", (unsigned)i);
            failures++;
            break;
        }
        seen[r.poly >> 3] = (uint8_t)(seen[r.poly >> 3] | (1u << (r.poly & 7u)));
        pokey_random_step(&r, 1);
    }
    CHECK(i == PM_POKEY_POLY17_PERIOD);
    CHECK(r.poly == start);                                   /* the period is 131,071 */

    pokey_random_init(&r, 1);
    for (i = 0; i < PM_POKEY_POLY17_PERIOD; i++) {
        uint8_t v = pokey_random_read(&r);
        ones7 += v >> 7;
        hist[v & 15]++;
    }
    CHECK(ones7 > PM_POKEY_POLY17_PERIOD * 49u / 100u && ones7 < PM_POKEY_POLY17_PERIOD * 51u / 100u);   /* bit 7 is a fair coin */
    {
        uint8_t a = 0;
        PokeyRandom x, y;
        pokey_random_init(&x, 77);
        pokey_random_init(&y, 77);
        for (i = 0; i < 1000; i++) {
            a = (uint8_t)(a | (pokey_random_read(&x) ^ pokey_random_read(&y)));   /* the same seed, the same stream (x and y read in step) */
        }
        CHECK(a == 0);
    }
    for (i = 0; i < 16; i++) {
        CHECK(hist[i] > 7000u);                               /* the low nibble is spread over all sixteen values */
    }
}

static void scripted_call_tests(void)
{
    ScriptedPlatform s;
    uint8_t out[16];
    static const uint8_t sticks[3] = {0x0F, 0x07, 0x0B};
    static const uint8_t stream[3] = {10, 20, 30};
    uint8_t d, c;

    scripted_init(&s, 5, 250);
    scripted_set_sticks(&s, sticks, 3);
    CHECK(s.platform.stick(s.platform.ctx, 0) == 0x07);              /* sticks[(t + port) % n] with t = 250: index 1 */
    CHECK(s.platform.stick(s.platform.ctx, 1) == 0x0B);              /* index 2 */
    CHECK(s.platform.clock(s.platform.ctx) == 250);
    s.platform.attract(s.platform.ctx, &d, &c);
    CHECK(d == 0xFF && c == 0x00);
    s.platform.collisions(s.platform.ctx, NULL, out);
    CHECK(out[2] == 0 && out[9] == 0 && out[10] == 0);
    CHECK(s.platform.trigger(s.platform.ctx, 0) == 1 && s.platform.console(s.platform.ctx) == 7 && s.platform.key(s.platform.ctx) == 0xFF && s.platform.key_delay(s.platform.ctx) == 0);
    CHECK(s.calls_stick == 2 && s.calls_clock == 1 && s.calls_attract == 1 && s.calls_collisions == 1 && s.calls_trigger == 1);
    scripted_inject_random(&s, stream, 3);
    CHECK(s.platform.random(s.platform.ctx) == 10 && s.platform.random(s.platform.ctx) == 20 && s.platform.random(s.platform.ctx) == 30);
    CHECK(s.platform.random(s.platform.ctx) == 0 && s.stream_overrun == 1);
    {
        uint8_t fixed[16] = {0};
        fixed[9] = 0x0F;
        scripted_set_fixed_collisions(&s, fixed);
        s.platform.collisions(s.platform.ctx, NULL, out);
        CHECK(out[9] == 0x0F);
    }
}

static World w1, w2, w3;
static uint8_t states[8 * PM_STATE_SIZE];

static int load_states(const char *path, int *n)
{
    PmFile *f = pm_fs_open(path, "rb");
    size_t got;
    if (f == NULL) {
        printf("cannot read %s (%s)\n", path, pm_fs_error_text(pm_fs_error()));
        return 0;
    }
    got = pm_fs_read(f, states, sizeof states);
    pm_fs_close(f);
    *n = (int)(got / PM_STATE_SIZE);
    return *n > 0 && got % PM_STATE_SIZE == 0;
}

static int same(const World *a, const World *b)
{
    uint8_t pa[PM_STATE_SIZE], pb[PM_STATE_SIZE];
    world_pack(a, pa);
    world_pack(b, pb);
    return memcmp(pa, pb, PM_STATE_SIZE) == 0 && a->pokey_n == b->pokey_n && memcmp(a->pokey_addr, b->pokey_addr, a->pokey_n * sizeof a->pokey_addr[0]) == 0
           && memcmp(a->pokey_val, b->pokey_val, a->pokey_n) == 0;
}

static void frame_tests(const char *path)
{
    int n, k, f, differ = 0;
    static const uint8_t sticks[5] = {0x0F, 0x07, 0x0B, 0x0E, 0x0D};
    uint32_t randoms_total;

    if (!load_states(path, &n)) {
        failures++;
        return;
    }
    for (k = 0; k < n; k++) {
        ScriptedPlatform pa, pb, pc;
        uint32_t used = 0;

        /* the same seed twice: the same frames */
        world_init(&w1);
        world_unpack(&w1, states + (size_t)k * PM_STATE_SIZE);
        w2 = w1;
        w3 = w1;
        scripted_init(&pa, 3, 40);
        scripted_set_sticks(&pa, sticks, 5);
        scripted_init(&pb, 3, 40);
        scripted_set_sticks(&pb, sticks, 5);
        scripted_init(&pc, 4, 40);
        scripted_set_sticks(&pc, sticks, 5);
        for (f = 0; f < 120; f++) {
            used += run_frame(&w1, &pa.platform);
            (void)run_frame(&w2, &pb.platform);
            (void)run_frame(&w3, &pc.platform);
            CHECK(same(&w1, &w2));
            if (!same(&w1, &w3)) {
                differ = 1;
            }
        }
        /* a poisoned copy */
        {
            static World wp, wq;
            ScriptedPlatform pq, pp;
            world_init(&wp);
            world_unpack(&wp, states + (size_t)k * PM_STATE_SIZE);
            wq = wp;
            scripted_init(&pq, 3, 40);
            scripted_set_sticks(&pq, sticks, 5);
            scripted_init(&pp, 3, 40);
            scripted_set_sticks(&pp, sticks, 5);
            for (f = 0; f < 120; f++) {
                int i;
                for (i = 0; i < 4; i++) {
                    wp.stick[i] = (uint8_t)(0xA5 + f + i);
                }
                for (i = 0; i < 16; i++) {
                    wp.collide[i] = (uint8_t)(0x5A + f * 3 + i);
                }
                wp.RTCLOK2 = (uint8_t)(0x33 + f);
                wp.DRKMSK = (uint8_t)(0x11 * f);
                wp.COLRSH = (uint8_t)(f * 7);
                (void)run_frame(&wp, &pp.platform);
                (void)run_frame(&wq, &pq.platform);
                if (!same(&wp, &wq)) {
                    printf("state %d frame %d: a poisoned input field changed the frame\n", k, f);
                    failures++;
                    break;
                }
            }
        }
        /* every input call is counted: the running game's frame reads two sticks, the collisions, the clock, the attract values and RANDOM only */
        CHECK(pa.calls_stick == 240u && pa.calls_collisions == 120u && pa.calls_clock == 120u && pa.calls_attract == 120u && pa.calls_frame_done == 120u);
        CHECK(pa.calls_trigger == 0 && pa.calls_console == 0 && pa.calls_key == 0 && pa.calls_key_delay == 0);
        randoms_total = pa.calls_random;
        CHECK(randoms_total == used);
    }
    CHECK(differ);          /* a different seed gives a different game somewhere in the states */
}

static uint8_t charset[GTIA_CHARSET_SIZE];

/* the platform that computes the collisions: the game reads the latch at the start of a frame; after the frame the latch is cleared when the frame wrote HITCLR, and the frame's scene is ORed in */
static void gtia_platform_tests(const char *states_path, const char *charset_path)
{
    int n, k, f, i;
    PmFile *cf = pm_fs_open(charset_path, "rb");
    size_t got = 0;

    if (cf != NULL) {
        got = pm_fs_read(cf, charset, sizeof charset);
        pm_fs_close(cf);
    }
    CHECK(got == GTIA_CHARSET_SIZE);
    if (!load_states(states_path, &n)) {
        failures++;
        return;
    }
    for (k = 0; k < n; k++) {
        ScriptedPlatform sp;
        uint8_t expect[16], shown[16];
        int hit_frames = 0;

        world_init(&w1);
        world_unpack(&w1, states + (size_t)k * PM_STATE_SIZE);
        scripted_init(&sp, 9, 0);
        scripted_use_gtia(&sp, charset);
        memset(expect, 0, 16);
        for (f = 0; f < 80; f++) {
            GtiaScene sc;
            uint32_t j;
            int hitclr = 0;
            (void)run_frame(&w1, &sp.platform);
            for (i = 0; i < 16; i++) {
                if (w1.collide[i] != expect[i]) {
                    printf("state %d frame %d: the game read register %d = %02x, the latch was %02x\n", k, f, i, w1.collide[i], expect[i]);
                    failures++;
                    return;
                }
            }
            for (j = 0; j < w1.pokey_n; j++) {
                hitclr |= w1.pokey_addr[j] == 0xD01E;
            }
            hit_frames += hitclr;
            gtia_scene_of_world(&w1, charset, &sc);
            gtia_collision_registers(&sc, GTIA_VISIBLE_LO, GTIA_VISIBLE_HI, GTIA_LINE_LO, GTIA_LINE_HI, shown);
            for (i = 0; i < 16; i++) {
                expect[i] = (uint8_t)((hitclr ? 0 : expect[i]) | shown[i]);
            }
            CHECK(memcmp(expect, sp.latch.reg, 16) == 0);
        }
        CHECK(hit_frames > 0);                       /* the game clears the collisions in the frames it runs */
    }
}

int main(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "--bits") == 0) {
        PokeyRandom r;
        int n = atoi(argv[2]), i;
        pokey_random_init(&r, 0);
        for (i = 0; i < n; i++) {
            pokey_random_step(&r, 1);
            printf("%u", (unsigned)pokey_poly17_bit8(&r));
        }
        printf("\n");
        return 0;
    }
    if (boot_tables() != 0) {
        return 2;
    }
    if (argc == 4 && strcmp(argv[1], "--gtia") == 0) {
        gtia_platform_tests(argv[2], argv[3]);
    } else if (argc == 3 && strcmp(argv[1], "--frames") == 0) {
        frame_tests(argv[2]);
    } else {
        pokey_tests();
        scripted_call_tests();
    }
    if (failures == 0) {
        printf("platform_check: OK\n");
        return 0;
    }
    printf("platform_check: %d failures\n", failures);
    return 1;
}
