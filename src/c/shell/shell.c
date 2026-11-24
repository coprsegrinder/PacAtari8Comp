/* shell/shell.c - see shell.h. */
#include "shell.h"

#include <string.h>

#include "../platform/fs.h"

#define HIGHSCORE_FIRST 0x39              /* status[0x39..0x3E] = $2039-$203E */
#define HIGHSCORE_CELLS 6
#define HIGHSCORE_PATH "save/highscore.pmo"
#define OPTIONS_PATH "save/options.pmo"
#define LOG_PATH "logs/shell.log"

/* ---- the platform of a replay or a front end ---- */

static uint8_t sh_stick(void *ctx, int port)
{
    Shell *s = (Shell *)ctx;

    return port == 0 ? s->in.stick0 : s->in.stick1;
}

static uint8_t sh_trigger(void *ctx, int port)
{
    Shell *s = (Shell *)ctx;

    return port == 0 ? s->in.trig0 : s->in.trig1;
}

static uint8_t sh_console(void *ctx)
{
    return ((Shell *)ctx)->in.console;
}

static uint8_t sh_key(void *ctx)
{
    return ((Shell *)ctx)->in.key;
}

static uint8_t sh_key_delay(void *ctx)
{
    return ((Shell *)ctx)->in.keydelay;
}

static uint8_t sh_clock(void *ctx)
{
    return ((Shell *)ctx)->in.clock;
}

static void sh_attract(void *ctx, uint8_t *drkmsk, uint8_t *colrsh)
{
    *drkmsk = ((Shell *)ctx)->in.drkmsk;
    *colrsh = ((Shell *)ctx)->in.colrsh;
}

static uint8_t sh_random(void *ctx)
{
    Shell *s = (Shell *)ctx;

    if (s->in.random != NULL) {                              /* the recorded bytes of the frame */
        if (s->stream_pos < s->in.nrandom) {
            return s->in.random[s->stream_pos++];
        }
        s->stream_overrun++;
        return 0;
    }
    return pokey_random_read(&s->poke);                      /* the POKEY model: a whole frame at the start of the frame (shell_frame), a fixed stride before each read */
}

static void sh_collisions(void *ctx, const World *w, uint8_t out[16])
{
    (void)w;
    memcpy(out, ((Shell *)ctx)->latch.reg, 16);
}

static void sh_frame_done(void *ctx, const World *w)
{
    Shell *s = (Shell *)ctx;

    gtia_latch_frame_done(&s->latch, w, s->charset);
}

/* ---- the run ---- */

#define FNV64_BASIS 0xCBF29CE484222325ull
#define FNV64_PRIME 0x100000001B3ull

static uint64_t fnv64(uint64_t h, const uint8_t *p, size_t n)
{
    size_t i;

    for (i = 0; i < n; i++) {
        h = (h ^ p[i]) * FNV64_PRIME;
    }
    return h;
}

void shell_init(Shell *s, const uint8_t charset[GTIA_CHARSET_SIZE], uint32_t seed, uint8_t start_clock)
{
    memset(&s->in, 0, sizeof s->in);
    memcpy(s->charset, charset, GTIA_CHARSET_SIZE);
    power_on_world(&s->world, start_clock);
    start(&s->world);
    keyloop_init(&s->kl);
    gtia_latch_init(&s->latch);
    pokey_random_init(&s->poke, seed);
    s->stream_pos = 0;
    s->stream_overrun = 0;
    s->frame = 0;
    s->chain = FNV64_BASIS;
}

uint64_t shell_state_hash(Shell *s)
{
    world_pack(&s->world, s->pack);
    return fnv64(FNV64_BASIS, s->pack, sizeof s->pack);
}

uint64_t shell_frame(Shell *s, const FrameInput *in)
{
    Platform p;
    uint64_t h;
    uint8_t le[8];
    int i;

    s->in = *in;
    s->stream_pos = 0;
    if (in->random == NULL) {
        pokey_random_step(&s->poke, PM_POKEY_FRAME_CYCLES);
    }
    p.ctx = s;
    p.stick = sh_stick;
    p.trigger = sh_trigger;
    p.console = sh_console;
    p.key = sh_key;
    p.key_delay = sh_key_delay;
    p.clock = sh_clock;
    p.attract = sh_attract;
    p.random = sh_random;
    p.collisions = sh_collisions;
    p.frame_done = sh_frame_done;
    (void)app_frame(&s->world, &s->kl, &p);
    s->frame++;
    h = shell_state_hash(s);
    for (i = 0; i < 8; i++) {
        le[i] = (uint8_t)(h >> (8 * i));
    }
    s->chain = fnv64(s->chain, le, sizeof le);
    return h;
}

uint64_t shell_digest(const Shell *s)
{
    return s->chain;
}

/* ---- what is kept between runs ---- */

static uint32_t fnv32(const uint8_t *p, size_t n)
{
    uint32_t h = 0x811C9DC5u;
    size_t i;

    for (i = 0; i < n; i++) {
        h = (h ^ p[i]) * 0x01000193u;
    }
    return h;
}

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}

static uint32_t get32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

int shell_make_folders(void)
{
    return (pm_fs_mkdir("save") == 0 && pm_fs_mkdir("logs") == 0) ? 0 : 1;
}

static int write_file(const char *path, const uint8_t *buf, size_t n)
{
    PmFile *f;

    if (shell_make_folders() != 0) {
        return 1;
    }
    f = pm_fs_open(path, "wb");
    if (f == NULL) {
        return 1;
    }
    if (pm_fs_write(f, buf, n) != n) {
        pm_fs_close(f);
        return 1;
    }
    return pm_fs_close(f) == 0 ? 0 : 1;
}

static int read_file(const char *path, uint8_t *buf, size_t n)
{
    PmFile *f = pm_fs_open(path, "rb");
    size_t got;
    uint8_t extra;

    if (f == NULL) {
        return 1;
    }
    got = pm_fs_read(f, buf, n);
    if (got == n && pm_fs_read(f, &extra, 1) != 0) {
        got = n + 1;                                         /* longer than it should be */
    }
    pm_fs_close(f);
    return got == n ? 0 : 1;
}

long shell_highscore_value(const Shell *s)
{
    long v = 0;
    int i;

    for (i = 0; i < HIGHSCORE_CELLS; i++) {
        uint8_t c = s->world.status[HIGHSCORE_FIRST + i];
        if (c == 0u) {
            v = v * 10;                                      /* a blank: the leading zeros of a score are not drawn */
        } else if (c >= 0x10u && c <= 0x19u) {
            v = v * 10 + (long)(c - 0x10u);
        } else {
            return -1;
        }
    }
    return v;
}

/* save/highscore.pmo: "PMHS", u16 version 1, u16 0, the six cells, 2 bytes 0, u32 FNV-1a of the first 16 bytes = 20 bytes */
int shell_highscore_save(const Shell *s)
{
    uint8_t buf[20];
    int i;

    if (shell_highscore_value(s) <= 0) {
        return 1;                                            /* nothing to keep: no score yet, or cells that are not a score */
    }
    memset(buf, 0, sizeof buf);
    buf[0] = 0x50u; buf[1] = 0x4Du; buf[2] = 0x48u; buf[3] = 0x53u;      /* "PMHS" */
    buf[4] = 1;
    for (i = 0; i < HIGHSCORE_CELLS; i++) {
        buf[8 + i] = s->world.status[HIGHSCORE_FIRST + i];
    }
    put32(buf + 16, fnv32(buf, 16));
    return write_file(HIGHSCORE_PATH, buf, sizeof buf);
}

int shell_highscore_load(Shell *s)
{
    uint8_t buf[20];
    int i;

    if (read_file(HIGHSCORE_PATH, buf, sizeof buf) != 0) {
        return 1;
    }
    if (memcmp(buf, "PMHS", 4) != 0 || buf[4] != 1 || get32(buf + 16) != fnv32(buf, 16)) {
        return 1;
    }
    for (i = 0; i < HIGHSCORE_CELLS; i++) {
        if (buf[8 + i] != 0u && (buf[8 + i] < 0x10u || buf[8 + i] > 0x19u)) {
            return 1;
        }
    }
    for (i = 0; i < HIGHSCORE_CELLS; i++) {
        s->world.status[HIGHSCORE_FIRST + i] = buf[8 + i];
    }
    return 0;
}

/* save/options.pmo: "PMOP", u16 version 1, u16 0, u32 seed, u8 start clock, 3 bytes 0, u32 FNV-1a of the first 16 bytes = 20 bytes */
int shell_options_save(const ShellOptions *o)
{
    uint8_t buf[20];

    memset(buf, 0, sizeof buf);
    buf[0] = 0x50u; buf[1] = 0x4Du; buf[2] = 0x4Fu; buf[3] = 0x50u;      /* "PMOP" */
    buf[4] = 1;
    put32(buf + 8, o->seed);
    buf[12] = o->start_clock;
    put32(buf + 16, fnv32(buf, 16));
    return write_file(OPTIONS_PATH, buf, sizeof buf);
}

int shell_options_load(ShellOptions *o)
{
    uint8_t buf[20];

    if (read_file(OPTIONS_PATH, buf, sizeof buf) != 0) {
        return 1;
    }
    if (memcmp(buf, "PMOP", 4) != 0 || buf[4] != 1 || get32(buf + 16) != fnv32(buf, 16)) {
        return 1;
    }
    o->seed = get32(buf + 8);
    o->start_clock = buf[12];
    return 0;
}

int shell_log(const char *line)
{
    PmFile *f;

    if (shell_make_folders() != 0) {
        return 1;
    }
    f = pm_fs_open(LOG_PATH, "ab");
    if (f == NULL) {
        return 1;
    }
    pm_fs_printf(f, "%s\n", line);
    return pm_fs_close(f) == 0 ? 0 : 1;
}
