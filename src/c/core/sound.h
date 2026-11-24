/* core/sound.h - the sound and the death in C (stage 76d, docs/44).  Twin of tools/core_sound.py.
 * Every sound is a small state machine that runs once per frame (or per 4th jiffy), updates its state variables and appends the POKEY writes (address, value) to the World's log in order.
 * POKEY: AUDF1 $D200, AUDC1 $D201, AUDF2 $D202, AUDC2 $D203, AUDF3 $D204, AUDC3 $D205, AUDF4 $D206, AUDC4 $D207, AUDCTL $D208; HITCLR $D01E. */
#ifndef PM_CORE_SOUND_H
#define PM_CORE_SOUND_H

#include "world.h"

#define POKEY_AUDF1 0xD200
#define POKEY_AUDC1 0xD201
#define POKEY_AUDF2 0xD202
#define POKEY_AUDC2 0xD203
#define POKEY_AUDF3 0xD204
#define POKEY_AUDC3 0xD205
#define POKEY_AUDF4 0xD206
#define POKEY_AUDC4 0xD207
#define POKEY_AUDCTL 0xD208
#define GTIA_HITCLR 0xD01E

void sound_wr(World *w, uint16_t addr, int value);   /* one chip write, value masked to a byte */
void clear_pokey(World *w);                          /* ClearPokeyRegisters $B0E6 */
void dot_sound_sweep(World *w);                      /* DotSoundSweep $B0BC */
void bonus_sound(World *w);                          /* BonusSound $ABC9 */
void frightened_sound(World *w);                     /* FrightenedSound $AFD7 */
void eyes_returning_sound(World *w);                 /* EyesReturningSound $B02C */
void siren(World *w);                                /* the siren $B508 */
void ghost_eaten_pause(World *w);                    /* GhostEatenPause $B049 */

/* the start tune block of FrameDispatch $A6CC (from $A7D3); returns 0 wait, 1 tune, 2 ready, 3 play (the strings of the Python) */
int start_tune_step(World *w);

void toggle_leg_phase(World *w);                     /* ToggleLegPhase $AC05 */
void death_sequence(World *w);                       /* DeathSequence $AE3D */
void death_animation(World *w);                      /* DeathAnimation $AEF7 */

#endif
