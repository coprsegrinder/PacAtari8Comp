/* app/keyloop.h - the main program (the key loop `$A4BA-$A572`), the new game and the start-up in C (stage 79d, docs/51).  Twin of tools/core_app.py, function by function.
 * keyloop.c: the main program as a machine with five places (a pass, the console read, the debounce, the release, the clock wait), run after the frame's handler to the point where it can only wait for the next frame.
 * newgame.c: the restart `$A477` and what follows it (the new game).  start.c: the OS's power-on RAM and `Start` `$A386`.  app.c: one frame on a platform. */
#ifndef PM_APP_KEYLOOP_H
#define PM_APP_KEYLOOP_H

#include <stdint.h>

#include "../core/random_feed.h"
#include "../core/world.h"
#include "../platform/hal.h"

/* the five places of the main program (the key loop) where it can wait between frames */
enum KeyLoopPc { KL_TOP = 0, KL_READ = 1, KL_DEBOUNCE = 2, KL_RELEASE = 3, KL_CLOCK_WAIT = 4 };

#define KL_CONSOL_NONE 7
#define KL_CONSOL_START 6
#define KL_CONSOL_SELECT 5
#define KL_CONSOL_OPTION 3

/* the key loop's machine: where it is, the console accumulator, the clock it waits for */
typedef struct KeyLoop {
    int pc;               /* an enum KeyLoopPc */
    uint8_t acc;          /* the accumulator of the debounce and the release: the OR of the console reads */
    uint8_t clock;        /* the clock the restart waits to change */
} KeyLoop;

void keyloop_init(KeyLoop *kl);   /* the main program at the top of a pass, nothing accumulated */
uint32_t keyloop_state(const KeyLoop *kl);        /* pc | acc << 8 (debounce, release) | clock << 16 (clock wait): the place the program is in, as one number */

/* the main program for the rest of the frame: `console` is the value of CONSOL for the frame (the caller reads it from the platform); returns 0, or 1 when the program did not settle */
int key_loop(World *w, KeyLoop *kl, uint8_t console);

/* newgame.c */
void restart_clear(World *w);                     /* $A477-$A48A: `$20-$3F`, the chip, the stored maze to the screen and both saved mazes */
void restart_tail(World *w);                      /* $A49B-$A4B6: the display list, the priority, the first board, the title scores, the board start */
void new_game(World *w, KeyLoop *kl);             /* $A537: START or a trigger: the restart, then the wait for the OS clock */

/* start.c */
void power_on_world(World *w, uint8_t clock);     /* the RAM after the OS's power-on clear, with the OS-owned values the game reads (docs/37) */
void start(World *w);                             /* Start $A386 to the first pass of the main program */

/* app.c: one frame of the whole program on a platform: the inputs, the OS clock, the handler, the main program, the platform's frame_done; returns the number of RANDOM values the frame took */
void app_read_inputs(World *w, const Platform *p);
uint32_t app_frame(World *w, KeyLoop *kl, Platform *p);   /* returns the number of RANDOM values the frame took */

#endif
