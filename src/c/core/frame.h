/* core/frame.h - the ghost logic that runs every frame, in C (stage 76d, docs/44).  Twin of tools/core_frame.py: the frightened period, a ghost eaten, the eyes' way home and the house. */
#ifndef PM_CORE_FRAME_H
#define PM_CORE_FRAME_H

#include "random_feed.h"
#include "world.h"

#define FRAME_PCOLR0 0xC0   /* index of PCOLR0 in w->shadow */

void frightened_tick(World *w);                                  /* FrightenedTick $AF54 */
void ghost_eaten(World *w, int x);                               /* GhostEaten $A886 */
void eyes_and_house_per_frame(World *w, RandomFeed *rnd);        /* EyesAndHousePerFrame $B69E */

#endif
