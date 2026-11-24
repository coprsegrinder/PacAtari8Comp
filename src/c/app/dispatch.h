/* app/dispatch.h - the frame dispatcher in C (stage 79c, docs/51).  Twin of tools/core_app_frame.py, function by function (the ROM routine in each comment).
 * FrameDispatch ($A6CC) decides, by GameState and the flags of the game in the order of the code, which of the 15 frame classes of docs/38 this frame is, and runs it:
 *   GameState 1  copyright setup    GameState 2  copyright wait    GameState 3, 4  the title menu
 *   GameState 0  the game: the countdown byte, paused, the player label, board start, the countdown's labels, the level end, the start idle / start tune, then WaitState (turn control, the READY! wait,
 *                or the frame of play, which has the death and the eaten-ghost pause first) */
#ifndef PM_APP_DISPATCH_H
#define PM_APP_DISPATCH_H

#include "../core/random_feed.h"
#include "../core/world.h"

void init_display2(World *w);                     /* InitDisplay2 $A610 */
void title_clear_scores_1p(World *w);             /* TitleClearScores1P $A632 */
void title_clear_scores_2p(World *w);             /* TitleClearScores2P $A64E */
void copyright_setup(World *w);                   /* GameState 1: $A6D7-$A70A */
void copyright_wait(World *w);                    /* GameState 2: $A70D */
void title_menu(World *w);                        /* GameState 3 and 4: $A719-$A78B */
void game_frame(World *w, RandomFeed *rnd);       /* GameState 0: $A78C */
void frame_dispatch(World *w, RandomFeed *rnd);   /* FrameDispatch $A6CC */
void vbi_handler(World *w, RandomFeed *rnd);      /* the deferred vertical-blank handler $A5FD (to its jump to the OS exit) */

#endif
