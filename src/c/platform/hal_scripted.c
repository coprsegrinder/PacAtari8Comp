/* platform/hal_scripted.c - the scripted platform, see hal_scripted.h. */
#include "hal_scripted.h"

#include <string.h>

static uint8_t sp_stick(void *ctx, int port)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    s->calls_stick++;
    if (s->nsticks > 0) {
        return s->sticks[(s->t + (uint32_t)port) % s->nsticks];
    }
    return 0x0F;
}

static uint8_t sp_trigger(void *ctx, int port)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    (void)port;
    s->calls_trigger++;
    return 1;
}

static uint8_t sp_console(void *ctx)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    s->calls_console++;
    return 7;
}

static uint8_t sp_key(void *ctx)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    s->calls_key++;
    return 0xFF;
}

static uint8_t sp_key_delay(void *ctx)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    s->calls_key_delay++;
    return 0;
}

static uint8_t sp_clock(void *ctx)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    s->calls_clock++;
    return (uint8_t)(s->t & 0xFFu);
}

static void sp_attract(void *ctx, uint8_t *drkmsk, uint8_t *colrsh)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    s->calls_attract++;
    *drkmsk = 0xFF;
    *colrsh = 0x00;
}

static uint8_t sp_random(void *ctx)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    s->calls_random++;
    if (s->stream != NULL) {
        if (s->stream_pos < s->stream_len) {
            return s->stream[s->stream_pos++];
        }
        s->stream_overrun++;
        return 0;
    }
    return pokey_random_read(&s->poke);
}

static void sp_collisions(void *ctx, const World *w, uint8_t out[16])
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    (void)w;
    s->calls_collisions++;
    switch (s->collisions_mode) {
    case SCRIPTED_COLLISIONS_FIXED:
        memcpy(out, s->fixed_collide, 16);
        break;
    case SCRIPTED_COLLISIONS_GTIA:
        memcpy(out, s->latch.reg, 16);
        break;
    default:
        memset(out, 0, 16);
        break;
    }
}

static void sp_frame_done(void *ctx, const World *w)
{
    ScriptedPlatform *s = (ScriptedPlatform *)ctx;
    s->calls_frame_done++;
    if (s->collisions_mode == SCRIPTED_COLLISIONS_GTIA) {
        gtia_latch_frame_done(&s->latch, w, s->charset);
    }
    s->t++;
    if (s->stream == NULL) {
        pokey_random_step(&s->poke, PM_POKEY_FRAME_CYCLES);     /* the counter runs on through the rest of the frame */
    }
}

void scripted_init(ScriptedPlatform *s, uint32_t seed, uint32_t start_clock)
{
    memset(s, 0, sizeof *s);
    s->t = start_clock;
    pokey_random_init(&s->poke, seed);
    gtia_latch_init(&s->latch);
    s->platform.ctx = s;
    s->platform.stick = sp_stick;
    s->platform.trigger = sp_trigger;
    s->platform.console = sp_console;
    s->platform.key = sp_key;
    s->platform.key_delay = sp_key_delay;
    s->platform.clock = sp_clock;
    s->platform.attract = sp_attract;
    s->platform.random = sp_random;
    s->platform.collisions = sp_collisions;
    s->platform.frame_done = sp_frame_done;
}

void scripted_set_sticks(ScriptedPlatform *s, const uint8_t *sticks, uint32_t n)
{
    if (n > SCRIPTED_MAX_STICKS) {
        n = SCRIPTED_MAX_STICKS;
    }
    memcpy(s->sticks, sticks, n);
    s->nsticks = n;
}

void scripted_inject_random(ScriptedPlatform *s, const uint8_t *values, uint32_t n)
{
    s->stream = values;
    s->stream_len = n;
    s->stream_pos = 0;
    s->stream_overrun = 0;
}

void scripted_set_fixed_collisions(ScriptedPlatform *s, const uint8_t regs[16])
{
    memcpy(s->fixed_collide, regs, 16);
    s->collisions_mode = SCRIPTED_COLLISIONS_FIXED;
}

void scripted_use_gtia(ScriptedPlatform *s, const uint8_t charset[GTIA_CHARSET_SIZE])
{
    s->charset = charset;
    gtia_latch_init(&s->latch);
    s->collisions_mode = SCRIPTED_COLLISIONS_GTIA;
}
