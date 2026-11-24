/* Stage J: the front end's input logic (src/c/shell/frontend.c) - what the keys and pads become, and that a game played through it replays to the same state.
 * The pure parts need nothing; the game parts need the asset blob (install_assets). */
#include <stdio.h>
#include <string.h>

#include "../assets/assets.h"
#include "../assets/rom_install.h"
#include "../shell/frontend.h"
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

static uint8_t blob_buf[ASSET_BLOB_MAX], ram_image[65536], rbuf[1 << 20];
static Assets assets;
static Shell sh1, sh2;

static void test_stick_and_buttons(void)
{
    Frontend f;
    FrontKeys k;
    FrameInput in;

    front_init(&f, 250);
    memset(&k, 0, sizeof k);
    front_frame(&f, &k, &in);
    CHECK(in.stick0 == 0x0F && in.stick1 == 0x0F && in.trig0 == 1 && in.trig1 == 1 && in.console == 7 && in.key == 0xFF && in.keydelay == 0);
    CHECK(in.clock == 250 && in.drkmsk == 0xFF && in.colrsh == 0 && in.random == NULL && in.nrandom == 0);
    k.pad[0].up = 1;
    front_frame(&f, &k, &in);
    CHECK(in.stick0 == 0x0E && in.stick1 == 0x0F && in.clock == 251);
    k.pad[0].up = 0; k.pad[0].down = 1;
    front_frame(&f, &k, &in);
    CHECK(in.stick0 == 0x0D);
    k.pad[0].down = 0; k.pad[0].left = 1;
    front_frame(&f, &k, &in);
    CHECK(in.stick0 == 0x0B);
    k.pad[0].left = 0; k.pad[0].right = 1;
    front_frame(&f, &k, &in);
    CHECK(in.stick0 == 0x07);
    k.pad[0].right = 0; k.pad[0].up = 1; k.pad[0].left = 1;   /* a diagonal is two switches */
    front_frame(&f, &k, &in);
    CHECK(in.stick0 == 0x0A);
    memset(&k, 0, sizeof k);
    k.pad[1].up = k.pad[1].down = k.pad[1].left = k.pad[1].right = 1;   /* opposite switches cancel: nothing */
    front_frame(&f, &k, &in);
    CHECK(in.stick1 == 0x0F && in.stick0 == 0x0F);
    memset(&k, 0, sizeof k);
    k.pad[0].fire = 1;
    k.start = 1;
    front_frame(&f, &k, &in);
    CHECK(in.trig0 == 0 && in.trig1 == 1 && in.console == 6);
    k.start = 0; k.select = 1; k.pad[1].fire = 1; k.pad[0].fire = 0;
    front_frame(&f, &k, &in);
    CHECK(in.trig0 == 1 && in.trig1 == 0 && in.console == 5);
    k.select = 0; k.option = 1;
    front_frame(&f, &k, &in);
    CHECK(in.console == 3);
    k.start = k.select = 1;
    front_frame(&f, &k, &in);
    CHECK(in.console == 0);
}

static void test_clock_and_key(void)
{
    Frontend f;
    FrontKeys k;
    FrameInput in;
    int i;

    front_init(&f, 254);
    memset(&k, 0, sizeof k);
    front_frame(&f, &k, &in);
    front_frame(&f, &k, &in);
    front_frame(&f, &k, &in);
    CHECK(in.clock == 0);                                /* RTCLOK2 wraps */
    k.pause = 1;                                         /* a press: CH = $21, KEYDEL = 3 */
    front_frame(&f, &k, &in);
    CHECK(in.key == 0x21 && in.keydelay == FRONT_KEYDELAY);
    k.pause = 0;
    for (i = 2; i >= 0; i--) {                           /* the OS counts it down, CH is not given again */
        front_frame(&f, &k, &in);
        CHECK(in.key == 0xFF && in.keydelay == i);
    }
    front_frame(&f, &k, &in);
    CHECK(in.keydelay == 0);
}

/* the game through the front end: START, then pause and resume with the key; and a recorded game replays to the same state */
static void test_game(void)
{
    Frontend f;
    FrontKeys k;
    FrameInput in;
    ReplayWriter w;
    Replay r;
    size_t size;
    unsigned n;
    int started = -1, paused_at = -1, resumed_at = -1;
    uint64_t h1 = 0, h2 = 0;

    shell_init(&sh1, ram_image + 0x3000, 4242u, 0);
    front_init(&f, 0);
    replay_writer_init(&w, rbuf, sizeof rbuf, 4242u, 0, 0);
    memset(&k, 0, sizeof k);
    for (n = 0; n < 1500u; n++) {
        k.start = 0;
        k.pause = 0;
        if (started < 0 && n >= 100u && n < 106u) {      /* START at the title */
            k.start = 1;
        }
        if (started >= 0 && n == (unsigned)started + 200u) {                  /* the pause key */
            k.pause = 1;
        }
        if (paused_at >= 0 && n == (unsigned)paused_at + 100u) {              /* and again */
            k.pause = 1;
        }
        front_frame(&f, &k, &in);
        (void)replay_writer_add(&w, &in);
        h1 = shell_frame(&sh1, &in);
        if (started < 0 && sh1.world.GameState == 0) {
            started = (int)n;
        }
        if (started >= 0 && paused_at < 0 && sh1.world.Paused != 0) {
            paused_at = (int)n;
        }
        if (paused_at >= 0 && resumed_at < 0 && sh1.world.Paused == 0 && n > (unsigned)paused_at) {
            resumed_at = (int)n;
        }
    }
    CHECK(started >= 0);                                  /* START made a game */
    CHECK(paused_at >= 0 && paused_at == started + 200 + FRONT_KEYDELAY);          /* paused when KEYDEL reached 0: three frames after the press */
    CHECK(resumed_at >= 0 && resumed_at == paused_at + 100 + FRONT_KEYDELAY);
    CHECK(replay_writer_finish(&w, &size) == REPLAY_OK && replay_parse(&r, rbuf, size) == REPLAY_OK);
    shell_init(&sh2, ram_image + 0x3000, r.seed, r.start_clock);
    while (replay_next(&r, &in)) {
        h2 = shell_frame(&sh2, &in);
    }
    CHECK(h1 == h2 && shell_digest(&sh1) == shell_digest(&sh2));                  /* the recorded game replays to the same state */
}

int main(void)
{
    test_stick_and_buttons();
    test_clock_and_key();
    if (assets_load(&assets, ASSET_DEFAULT_PATH, blob_buf, sizeof blob_buf) != ASSETS_OK || assets_install_tables(&assets) != ASSETS_OK) {
        printf("frontend_check: the asset blob is not there (run install_assets)\n");
        return 2;
    }
    assets_ram_image(&assets, ram_image);
    test_game();
    if (failures == 0) {
        printf("frontend_check: OK\n");
        return 0;
    }
    printf("frontend_check: %d failures\n", failures);
    return 1;
}
