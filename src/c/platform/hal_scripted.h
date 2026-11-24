/* platform/hal_scripted.h - a scripted platform for tests and the headless build (twin of tools/platform_iface.ScriptedPlatform and GtiaCollisions).
 * Deterministic: a stick script indexed by the clock, a clock that counts frames, RANDOM from the POKEY model (a seed) or from an injected stream, collisions from nothing, a fixed set or the GTIA model with
 * its latch; every call to an input is counted (the "inputs only through the platform" tests). */
#ifndef PM_PLATFORM_HAL_SCRIPTED_H
#define PM_PLATFORM_HAL_SCRIPTED_H

#include <stddef.h>

#include "../core/gtia.h"
#include "hal.h"
#include "pokey_random.h"

#define SCRIPTED_MAX_STICKS 64

/* where the scripted platform's collision registers come from */
typedef enum ScriptedCollisions {
    SCRIPTED_COLLISIONS_NONE = 0,    /* all sixteen registers 0 */
    SCRIPTED_COLLISIONS_FIXED,       /* the fixed registers in `fixed_collide` */
    SCRIPTED_COLLISIONS_GTIA         /* the GTIA model with its latch (needs `charset`) */
} ScriptedCollisions;

/* a platform that plays a script: a stick sequence, the clock counting frames, RANDOM from the model or an injected stream, collisions none / fixed / from the GTIA model; it counts every call to an input (the tests use it) */
typedef struct ScriptedPlatform {
    Platform platform;
    /* the script */
    uint8_t sticks[SCRIPTED_MAX_STICKS];
    uint32_t nsticks;                /* 0: the stick is never moved ($0F) */
    uint32_t t;                      /* frames run: the clock is t & $FF */
    /* RANDOM: the POKEY model, or an injected stream (then 0 once it is used up, counted in `stream_overrun`) */
    PokeyRandom poke;
    const uint8_t *stream;
    uint32_t stream_len, stream_pos, stream_overrun;
    /* the collision registers */
    ScriptedCollisions collisions_mode;
    uint8_t fixed_collide[16];
    GtiaLatch latch;
    const uint8_t *charset;
    /* counters of every call to an input */
    uint32_t calls_stick, calls_trigger, calls_console, calls_key, calls_key_delay, calls_clock, calls_attract, calls_random, calls_collisions, calls_frame_done;
} ScriptedPlatform;

void scripted_init(ScriptedPlatform *s, uint32_t seed, uint32_t start_clock);   /* a scripted platform: the RANDOM model seeded with `seed`, the OS clock at `start_clock` */
void scripted_set_sticks(ScriptedPlatform *s, const uint8_t *sticks, uint32_t n);   /* a stick script: the stick of port p at frame t is sticks[(t + p) % n] */
void scripted_inject_random(ScriptedPlatform *s, const uint8_t *values, uint32_t n);   /* RANDOM from a recorded stream instead of the model */
void scripted_set_fixed_collisions(ScriptedPlatform *s, const uint8_t regs[16]);
void scripted_use_gtia(ScriptedPlatform *s, const uint8_t charset[GTIA_CHARSET_SIZE]);   /* the collision registers come from the GTIA model (docs/50) with this character set */

#endif
