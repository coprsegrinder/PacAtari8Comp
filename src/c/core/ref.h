/* core/ref.h - the pure functions of the game in C (stage 76a, docs/44 section 2): levels, scoring, ghost AI, the dot count.
 * Twin of tools/core_ref.py, function by function, same names with the prefix ref_; checked against the 16 vector sets core_ref.*.vec (docs/51 section 4).
 * Plain values in, plain values out: no World.  Directions: 1 up, 2 down, 4 left, 8 right. */
#ifndef PM_CORE_REF_H
#define PM_CORE_REF_H

#include "constants.h"
#include <stdint.h>

#include "random_feed.h"

#define REF_UP DIR_UP
#define REF_DOWN DIR_DOWN
#define REF_LEFT DIR_LEFT
#define REF_RIGHT DIR_RIGHT
#define REF_GS_FRIGHT GS_FRIGHTENED_BIT
#define REF_GS_EYES GS_EYES
#define REF_GS_CHASE GS_CHASE
#define REF_DOTS_PER_BOARD 260
#define REF_DOT_POINTS 10
#define REF_PELLET_POINTS 50

/* levels */
uint8_t ref_pacing_delay(int32_t entity, uint8_t level, int32_t cycle);
/* one frame of an entity's pacing: returns 1 when it moves this frame; *cycle and *count are updated */
int ref_move_delay_tick(int32_t entity, uint8_t level, int32_t *cycle, uint8_t *count);
void ref_release_timers(uint8_t level, uint8_t out[3]);   /* the release timers of ghosts 1, 2, 3 by level (units of 4 frames; a window of the table clamped at level 3) */
uint8_t ref_fright_frames(uint8_t level);   /* frames of solid frightened colour; the level is not clamped (past 15 the table runs on into the ROM bytes that follow) */
uint8_t ref_fright_end_phase(uint8_t level);   /* the phase at which the frightened period ends (0 = practically endless); not clamped */
/* frames of the whole frightened period; returns 0 (and leaves *out alone) when the end phase is 0 = "practically endless" (Python None) */
int ref_fright_total_frames(uint8_t level, int32_t *out);
uint8_t ref_bonus_glyph(uint8_t level);   /* the bonus item's picture code (level clamped at 12) */
int32_t ref_bonus_points(uint8_t level);   /* the bonus score as a number (thousands and hundreds digits) */
void ref_bonus_popup_glyphs(uint8_t level, uint8_t out[5]);   /* the five screen codes of the bonus score pop-up */

/* scoring: a six-digit decimal score that wraps at 1,000,000 (points are not negative) */
void ref_score_add(int64_t score, int64_t points, int32_t extra_given, int32_t lives, int64_t *new_score, int32_t *new_extra, int32_t *new_lives);
int32_t ref_ghost_points(int32_t n);   /* 200, 400, 800, 1600 for the running count 0-3, 1600 beyond */

/* ghost AI */
uint8_t ref_junction_exits(int32_t is_pacman, int32_t x, int32_t y, int32_t direction, int32_t state, int *on_lattice_point);
void ref_wants(int32_t ey, int32_t ex, int32_t ty, int32_t tx, int32_t state, int *wv, int *wh);   /* the wanted vertical and horizontal direction (0 = none): towards the target, away from it when frightened */
int ref_steer(int32_t ey, int32_t ex, int32_t ty, int32_t tx, int32_t state, int32_t mask, RandomFeed *rnd);   /* the direction a ghost takes at a junction; takes 0 or 1 RANDOM value */
void ref_force_chase(const uint8_t states[4], int32_t x, uint8_t out[4]);   /* ghosts x .. 0 in the patrol-start, patrol and corner states go to chase */
void ref_power_pellet_ghosts(const uint8_t states[4], const uint8_t dirs[4], uint8_t out_states[4], uint8_t out_dirs[4]);   /* a power pellet: every ghost not eaten becomes frightened; most reverse */
void ref_frightened_end(const uint8_t states[4], uint8_t out[4]);   /* the end of the frightened period: states and corners */

/* the dot count: 16 bits, returns 1 when the board is complete */
int ref_count_dot(uint8_t lo, uint8_t hi, uint8_t *new_lo, uint8_t *new_hi);

#endif
