/* core/score.h - scoring, dots and power pellets in C (stage 76c, docs/44).  Twin of tools/core_score.py.
 * The screen cells are w->status ($2000 + i) and w->maze ($0C00 + i). */
#ifndef PM_CORE_SCORE_H
#define PM_CORE_SCORE_H

#include "world.h"

#define SCORE_CELL_P1 0x2A
#define SCORE_CELL_P2 0x47
#define SCORE_LIFE_ICON 0x9B

void draw_lives(World *w);            /* DrawLives $AD15 */
void add_to_score(World *w);          /* AddToScore $B423 */
void count_dot(World *w);             /* the dot count of the player on turn; the board is complete at 260 */
void eat_dot(World *w);               /* EatDotAtPacMan $B33A */
void power_pellet_check(World *w);    /* PowerPelletCheck $B39F + PowerPelletEaten $B3DE */

#endif
