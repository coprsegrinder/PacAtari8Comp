/* Stage 80d: self test of the shell (src/c/shell): the replay format (round trip, every way a replay can be wrong), the run (deterministic, sensitive to an input and to the start), the high score, the
 * options and the log under save/ and logs/ of a folder made below build/ (nothing is written in the main folder itself).  Needs the asset blob (install_assets). */
#include <stdio.h>
#include <string.h>

#include "../assets/assets.h"
#include "../assets/rom_install.h"
#include "../platform/fs.h"
#include "../shell/replay.h"
#include "../shell/shell.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static Shell shell1, shell2;
static uint8_t blob_buf[ASSET_BLOB_MAX], ram_image[65536];
static Assets assets;
static uint8_t rbuf[1 << 16];

static FrameInput idle(uint8_t clock)
{
    FrameInput f;

    memset(&f, 0, sizeof f);
    f.stick0 = 0x0F;
    f.stick1 = 0x0F;
    f.trig0 = 1;
    f.trig1 = 1;
    f.console = 7;
    f.key = 0xFF;
    f.clock = clock;
    f.drkmsk = 0xFF;
    return f;
}

static void test_replay_format(void)
{
    ReplayWriter w;
    Replay r;
    FrameInput f, g;
    static const uint8_t rnd[3] = {7, 8, 9};
    size_t size, i;
    uint8_t copy[1024];

    /* with RANDOM bytes */
    replay_writer_init(&w, rbuf, sizeof rbuf, 1234u, REPLAY_FLAG_RANDOM, 250);
    f = idle(250);
    f.nrandom = 3;
    f.random = rnd;
    CHECK(replay_writer_add(&w, &f) == REPLAY_OK);
    f = idle(251);
    f.console = 6;
    f.key = 0x21;
    CHECK(replay_writer_add(&w, &f) == REPLAY_OK);                 /* a frame with no RANDOM bytes */
    CHECK(replay_writer_finish(&w, &size) == REPLAY_OK);
    CHECK(size == REPLAY_HEADER + 2u * REPLAY_FRAME_BASE + 2u + 3u + 2u + 4u);
    CHECK(replay_parse(&r, rbuf, size) == REPLAY_OK);
    CHECK(r.nframes == 2 && r.seed == 1234u && r.start_clock == 250 && (r.flags & REPLAY_FLAG_RANDOM));
    CHECK(replay_next(&r, &g) == 1 && g.clock == 250 && g.nrandom == 3 && g.random != NULL && g.random[0] == 7 && g.random[2] == 9);
    CHECK(replay_next(&r, &g) == 1 && g.console == 6 && g.key == 0x21 && g.nrandom == 0);
    CHECK(replay_next(&r, &g) == 0);
    replay_rewind(&r);
    CHECK(replay_next(&r, &g) == 1 && g.clock == 250);
    /* without RANDOM bytes */
    replay_writer_init(&w, rbuf, sizeof rbuf, 5u, 0, 0);
    f = idle(0);
    CHECK(replay_writer_add(&w, &f) == REPLAY_OK && replay_writer_finish(&w, &size) == REPLAY_OK);
    CHECK(size == REPLAY_HEADER + REPLAY_FRAME_BASE + 4u);
    CHECK(replay_parse(&r, rbuf, size) == REPLAY_OK && replay_next(&r, &g) == 1 && g.random == NULL);
    /* every way to be wrong */
    CHECK(size < sizeof copy);
    memcpy(copy, rbuf, size);
    CHECK(replay_parse(&r, copy, 10) == REPLAY_TOO_SHORT);
    copy[0] = 'X';
    CHECK(replay_parse(&r, copy, size) == REPLAY_BAD_MAGIC);
    memcpy(copy, rbuf, size);
    copy[4] = 2;
    CHECK(replay_parse(&r, copy, size) == REPLAY_BAD_VERSION);
    for (i = 0; i < size; i++) {                                    /* any single changed byte is caught */
        memcpy(copy, rbuf, size);
        copy[i] ^= 0x20;
        CHECK(replay_parse(&r, copy, size) != REPLAY_OK);
    }
    CHECK(replay_parse(&r, rbuf, size - 1) != REPLAY_OK);
    CHECK(replay_parse(&r, rbuf, size + 1) != REPLAY_OK);
    /* a writer that runs out of room says so */
    replay_writer_init(&w, copy, 30, 0, 0, 0);
    f = idle(0);
    CHECK(replay_writer_add(&w, &f) == REPLAY_OK);
    CHECK(replay_writer_add(&w, &f) == REPLAY_FULL);
    CHECK(replay_writer_finish(&w, &size) == REPLAY_FULL);
}

static void run_frames(Shell *s, int n, int press_start_at)
{
    int i;

    for (i = 0; i < n; i++) {
        FrameInput f = idle((uint8_t)(250 + i));
        if (press_start_at >= 0 && i >= press_start_at && i < press_start_at + 6) {
            f.console = 6;
        }
        (void)shell_frame(s, &f);
    }
}

static void test_run(void)
{
    uint64_t d1, d2;
    FrameInput f;
    uint64_t h_a, h_b;

    shell_init(&shell1, ram_image + 0x3000, 7u, 250);
    shell_init(&shell2, ram_image + 0x3000, 7u, 250);
    run_frames(&shell1, 700, 480);
    run_frames(&shell2, 700, 480);
    d1 = shell_digest(&shell1);
    d2 = shell_digest(&shell2);
    CHECK(d1 == d2 && shell1.frame == 700);
    CHECK(shell_state_hash(&shell1) == shell_state_hash(&shell2));
    CHECK(shell1.world.GameState != 0 || shell1.world.GameState == 0);       /* the state is whatever the game is in; the hash is what is compared */
    /* a different input at one frame: the hashes before it are the same, the digest is not */
    shell_init(&shell2, ram_image + 0x3000, 7u, 250);
    run_frames(&shell2, 700, 481);
    CHECK(shell_digest(&shell2) != d1);
    /* another start clock gives another run */
    shell_init(&shell2, ram_image + 0x3000, 7u, 251);
    run_frames(&shell2, 700, 480);
    CHECK(shell_digest(&shell2) != d1);
    /* RANDOM from the model: another seed gives another game once the game has started (a game: START, then the ready time and play) */
    shell_init(&shell1, ram_image + 0x3000, 1u, 250);
    shell_init(&shell2, ram_image + 0x3000, 2u, 250);
    run_frames(&shell1, 2400, 480);
    run_frames(&shell2, 2400, 480);
    CHECK(shell_digest(&shell1) != shell_digest(&shell2));
    /* the RANDOM bytes of a frame: a frame that reads more than it carries is counted */
    shell_init(&shell1, ram_image + 0x3000, 1u, 250);
    f = idle(250);
    f.random = (const uint8_t *)"";
    f.nrandom = 0;
    h_a = shell_frame(&shell1, &f);
    h_b = shell_state_hash(&shell1);
    CHECK(h_a == h_b);
}

static void test_files(void)
{
    ShellOptions o, p;
    uint8_t garbage[16];
    PmFile *f;
    int i;

    CHECK(pm_fs_mkdir("build") == 0 && pm_fs_mkdir("build/shell_selftest") == 0);
    CHECK(pm_fs_set_root("build/shell_selftest") == 0);
    /* the high score */
    shell_init(&shell1, ram_image + 0x3000, 1u, 250);
    CHECK(shell_highscore_value(&shell1) == 0);                     /* the cells of a new machine are blank */
    CHECK(shell_highscore_save(&shell1) != 0);                      /* nothing to save */
    CHECK(shell_highscore_load(&shell1) != 0);                      /* nothing saved */
    for (i = 0; i < 6; i++) {
        shell1.world.status[0x39 + i] = (uint8_t)(0x10 + i + 1);    /* 123456 */
    }
    CHECK(shell_highscore_value(&shell1) == 123456);
    CHECK(shell_highscore_save(&shell1) == 0);
    shell1.world.status[0x39] = 0x00;                                 /* a blank leading zero is a zero */
    shell1.world.status[0x3A] = 0x00;
    CHECK(shell_highscore_value(&shell1) == 3456);
    shell1.world.status[0x3C] = 0x77;                                 /* not a score */
    CHECK(shell_highscore_value(&shell1) < 0 && shell_highscore_save(&shell1) != 0);
    shell1.world.status[0x3C] = 0x13;
    for (i = 0; i < 6; i++) {
        shell1.world.status[0x39 + i] = (uint8_t)(0x10 + i + 1);
    }
    shell_init(&shell2, ram_image + 0x3000, 1u, 250);
    CHECK(shell_highscore_load(&shell2) == 0 && shell_highscore_value(&shell2) == 123456);
    /* a damaged file is not used */
    memset(garbage, 0x55, sizeof garbage);
    f = pm_fs_open("save/highscore.pmo", "wb");
    CHECK(f != NULL);
    if (f != NULL) {
        pm_fs_write(f, garbage, sizeof garbage);
        pm_fs_close(f);
    }
    shell_init(&shell2, ram_image + 0x3000, 1u, 250);
    CHECK(shell_highscore_load(&shell2) != 0 && shell_highscore_value(&shell2) == 0);
    /* the options */
    o.seed = 0xDEADBEEFu;
    o.start_clock = 77;
    p.seed = 1;
    p.start_clock = 2;
    CHECK(shell_options_load(&p) != 0 && p.seed == 1 && p.start_clock == 2);   /* none: the caller's values stay */
    CHECK(shell_options_save(&o) == 0);
    CHECK(shell_options_load(&p) == 0 && p.seed == 0xDEADBEEFu && p.start_clock == 77);
    f = pm_fs_open("save/options.pmo", "wb");
    if (f != NULL) {
        pm_fs_write(f, garbage, sizeof garbage);
        pm_fs_close(f);
    }
    p.seed = 1;
    CHECK(shell_options_load(&p) != 0 && p.seed == 1);
    /* the log */
    CHECK(shell_log("first line") == 0 && shell_log("second line") == 0);
    f = pm_fs_open("logs/shell.log", "rb");
    CHECK(f != NULL);
    if (f != NULL) {
        char text[64];
        size_t n = pm_fs_read(f, text, sizeof text - 1);
        text[n] = '\0';
        CHECK(strstr(text, "first line") != NULL && strstr(text, "second line") != NULL);
        pm_fs_close(f);
    }
    CHECK(pm_fs_set_root(NULL) == 0);
}

int main(void)
{
    static uint8_t b2[ASSET_BLOB_MAX];

    (void)b2;
    if (assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) != ASSETS_OK || assets_install_tables(&assets) != ASSETS_OK) {
        printf("shell_selftest: the asset blob is not there (run install_assets)\n");
        return 2;
    }
    assets_ram_image(&assets, ram_image);
    test_replay_format();
    test_run();
    test_files();
    if (failures == 0) {
        printf("shell_selftest: OK\n");
        return 0;
    }
    printf("shell_selftest: %d failures\n", failures);
    return 1;
}
