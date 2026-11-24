/* app/board.h - the board, the turn, the end of a level, the READY! intro and the labels in C (stage 79b, docs/51).  Twin of tools/core_app_board.py, function by function (the ROM routine in each comment).
 * Files: intro.c (labels, READY!), board.c (the level indicator, the high score), levelend.c (the level-end sequence, AdvanceLevel), turn.c (TurnControl and the game over).
 * The game-over countdown is started by turn_control (CountdownActive, CountdownTimer); its decrement and its labels are in the frame dispatcher (79c). */
#ifndef PM_APP_BOARD_H
#define PM_APP_BOARD_H

#include "../core/world.h"

#define BOARD_COLPF3 0xD019

/* intro.c */
void draw_label_1up(World *w);          /* DrawLabel1UP $AD9F */
void draw_label_2up(World *w);          /* DrawLabel2UP $AD87 */
void blink_player_label(World *w);      /* BlinkPlayerLabel $AD69 */
void clear_ready_text(World *w);        /* ClearReadyText $AD5E */
void draw_ready_screen(World *w);       /* DrawReadyScreen $AD0E */

/* board.c */
void draw_level_indicator(World *w);    /* DrawLevelIndicator $AC93 */
void compare_high_score(World *w, int x);   /* CompareHighScore $AB26: x = $2A or $47, the score cells in the status rows */

/* levelend.c */
void advance_level(World *w);           /* AdvanceLevel $AC75 */
void level_end_step(World *w);          /* the level-end sequence $AC18 */

/* turn.c */
void turn_control(World *w);            /* TurnControl $AA2D */

#endif
