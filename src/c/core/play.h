/* core/play.h - one frame of play in C (stage 76d, docs/44).  Twin of tools/core_play.py: the frame body of FrameDispatch from $A82C (the game running) and the whole deferred
 * vertical-blank handler $A5FD for such a frame.  `w->collide` holds the GTIA collision registers (an input); `rnd` supplies the POKEY RANDOM values. */
#ifndef PM_CORE_PLAY_H
#define PM_CORE_PLAY_H

#include "random_feed.h"
#include "world.h"

#define PLAY_M2PF 2     /* index into w->collide */
#define PLAY_M1PL 9
#define PLAY_M2PL 10
#define PLAY_LAST_PELLET_CELL 0x2A4
#define PLAY_BONUS_CELLS 0x1F1   /* $0DF1: five cells of the bonus score picture; the bonus item is at $0DF3-$0DF4 */

void show_power_pellets(World *w);                 /* ShowPowerPellets $B55A */
void blink_power_pellets(World *w);                /* BlinkPowerPellets $B54F */
void bonus_item_update(World *w);                  /* BonusItemUpdate $B62E */
int move_delay_tick_w(World *w, int x);            /* MoveDelayTick $B590 on the World: 1 when entity x moves this frame */
void play_frame(World *w, RandomFeed *rnd);        /* the frame body from $A82C */
void vbi_play_frame(World *w, RandomFeed *rnd);    /* the deferred handler $A5FD for a frame of the running game */

#endif
