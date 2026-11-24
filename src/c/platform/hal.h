/* platform/hal.h - what the game takes from the outside: the fourteen inputs of docs/45 (the only things that reach it, tools/iface_map.py) as a table of functions.
 * Twin of the abstract class tools/platform_iface.Platform.  Everything system-dependent (keyboard, pad, clock, a real random source) lives behind it; the core and the app layer only see this interface.
 *   stick(port)      STICK0 / STICK1: bit 0 up, 1 down, 2 left, 3 right, 0 = pressed ($0F = nothing)
 *   trigger(port)    STRIG0 / STRIG1: 0 = pressed
 *   console()        CONSOL: bit 0 START, 1 SELECT, 2 OPTION, 0 = pressed ($07 = nothing)
 *   key()            CH: the last key code ($FF = none, $21 = the space bar)
 *   key_delay()      KEYDEL: the key debounce delay of the OS (0 = a key is accepted)
 *   clock()          RTCLOK2: the low byte of the jiffy clock, one more at every frame
 *   attract()        DRKMSK, COLRSH: the OS attract-mode mask and shift ($FF, $00 outside attract mode)
 *   random()         POKEY RANDOM: one byte at every read
 *   collisions(w)    the GTIA collision registers $D000-$D00F (M2PF = [2], M1PL = [9], M2PL = [10] are the three the game reads): the port computes them from the sprite pictures (core/gtia.h)
 *   frame_done(w)    optional: called after every frame with the World the frame left (a platform that computes the collisions, or counts, uses it) */
#ifndef PM_PLATFORM_HAL_H
#define PM_PLATFORM_HAL_H

#include <stdint.h>

#include "../core/world.h"

/* the 14 inputs of the game and the frame hook as a table of functions over a context (docs/45); the comment at the top of this file says what each returns */
typedef struct Platform {
    void *ctx;
    uint8_t (*stick)(void *ctx, int port);
    uint8_t (*trigger)(void *ctx, int port);
    uint8_t (*console)(void *ctx);
    uint8_t (*key)(void *ctx);
    uint8_t (*key_delay)(void *ctx);
    uint8_t (*clock)(void *ctx);
    void (*attract)(void *ctx, uint8_t *drkmsk, uint8_t *colrsh);
    uint8_t (*random)(void *ctx);
    void (*collisions)(void *ctx, const World *w, uint8_t out[16]);
    void (*frame_done)(void *ctx, const World *w);    /* may be NULL */
} Platform;

#endif
