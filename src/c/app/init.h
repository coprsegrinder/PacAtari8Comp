/* app/init.h - the state initialisation in C (stage 79a, docs/51).  Twin of tools/core_app_init.py, function by function (the ROM routines named in each comment).
 * The state the original keeps in screen memory is in the World: `maze_orig` ($0800), `saved1` ($1000), `saved2` ($1400). */
#ifndef PM_APP_INIT_H
#define PM_APP_INIT_H

#include <stdint.h>

#include "../core/world.h"

/* a zero-page byte by its address (a field, or one element of an array field); an address outside the zero page is ignored */
void world_zp_set(World *w, int addr, uint8_t value);
/* the zero-page bytes lo .. hi-1 to 0 */
void clear_zp(World *w, int lo, int hi);

void copy_0800_to_0c00(World *w);   /* Copy0800To0C00 $B11F: the stored maze to the maze screen */
void copy_0c00_to_1000(World *w);   /* Copy0C00To1000 $B13D: the screen to player 1's saved maze */
void copy_0c00_to_1400(World *w);   /* Copy0C00To1400 $B15B: the screen to player 2's saved maze */
void load_shadow_colors(World *w);  /* LoadShadowColors $B113: PCOLR0-3 and COLOR0-3 from ColorsGame */

void clear_player_counters(World *w, int x);   /* ClearPlayerCounters $AE1E: player x (0 or 1) */
void set_release_timers(World *w, int y);      /* SetReleaseTimers $AE2B: the release timers of ghosts 1-3 from the table, Y clamped at 3 */

void init_board(World *w);          /* InitBoard $ADAF: the start of every turn and every board */
void new_board_init(World *w);      /* NewBoardInit $AE02 */
void new_game_init(World *w);       /* NewGameInit $ADF1 */

#endif
