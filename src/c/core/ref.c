/* core/ref.c - the pure functions of the game (stage 76a).  Twin of tools/core_ref.py: read the two side by side. */
#include "ref.h"

#include "tables.h"
#include "constants.h"

/* ------------------------------------------------------------------------------------------------ levels */
uint8_t ref_pacing_delay(int32_t entity, uint8_t level, int32_t cycle)
{
    uint8_t lv = level < LEVEL_CLAMP_SPEED ? level : LEVEL_CLAMP_SPEED;
    uint8_t base = entity == 4 ? PAC_DELAY_BASE[lv] : GHOST_DELAY_BASE[lv];
    return MOVE_DELAY[base + cycle];
}

int ref_move_delay_tick(int32_t entity, uint8_t level, int32_t *cycle, uint8_t *count)
{
    *count = (uint8_t)(*count - 1u);
    if (*count != 0) {
        return 0;
    }
    *cycle = *cycle == 3 ? 0 : *cycle + 1;
    *count = ref_pacing_delay(entity, level, *cycle);
    return 1;
}

void ref_release_timers(uint8_t level, uint8_t out[3])
{
    uint8_t y = level < 3 ? level : 3;
    out[0] = HOUSE_RELEASE[y + 2];
    out[1] = HOUSE_RELEASE[y + 1];
    out[2] = HOUSE_RELEASE[y];
}

uint8_t ref_fright_frames(uint8_t level)
{
    return FRIGHT_FRAMES[level];
}

uint8_t ref_fright_end_phase(uint8_t level)
{
    return FRIGHT_END[level];
}

int ref_fright_total_frames(uint8_t level, int32_t *out)
{
    int32_t end = ref_fright_end_phase(level);
    int32_t frames = ref_fright_frames(level);
    if (end == 0) {
        return 0;
    }
    *out = end >= 2 ? frames + (end - 2) * FRIGHT_FLASH_FRAMES + 2 : frames + end;
    return 1;
}

uint8_t ref_bonus_glyph(uint8_t level)
{
    return BONUS_GLYPH[level < LEVEL_CLAMP_BONUS ? level : LEVEL_CLAMP_BONUS];
}

int32_t ref_bonus_points(uint8_t level)
{
    int i = 2 * (level < LEVEL_CLAMP_BONUS ? level : LEVEL_CLAMP_BONUS);
    return BONUS_SCORE[i] * 1000 + BONUS_SCORE[i + 1] * 100;
}

void ref_bonus_popup_glyphs(uint8_t level, uint8_t out[5])
{
    uint8_t o = BONUS_SCORE_GLYPH_OFFSETS[level < LEVEL_CLAMP_BONUS ? level : LEVEL_CLAMP_BONUS];
    int k;
    for (k = 0; k < 5; k++) {
        out[k] = BONUS_SCORE_GLYPHS[o + k];
    }
}

/* ------------------------------------------------------------------------------------------------ scoring */
void ref_score_add(int64_t score, int64_t points, int32_t extra_given, int32_t lives, int64_t *new_score, int32_t *new_extra, int32_t *new_lives)
{
    int64_t n = (score + points) % 1000000;
    *new_score = n;
    if (extra_given == 0 && (n >= 10000 || score >= 100000)) {
        *new_extra = 1;
        *new_lives = (lives + 1) & 0xFF;
    } else {
        *new_extra = extra_given;
        *new_lives = lives;
    }
}

int32_t ref_ghost_points(int32_t n)
{
    static const int32_t points[4] = {200, 400, 800, 1600};
    return n < 4 ? points[n] : 1600;
}

/* ------------------------------------------------------------------------------------------------ ghost AI */
uint8_t ref_junction_exits(int32_t is_pacman, int32_t x, int32_t y, int32_t direction, int32_t state, int *on_lattice_point)
{
    int r = -1, c = -1, i;
    uint8_t mask;
    int on = 0;

    for (i = 0; i < 10; i++) {
        if (JUNCTION_Y[i] == y) {
            r = i;
        }
        if (JUNCTION_X[i] == x) {
            c = i;
        }
    }
    if (r >= 0) {
        if (c >= 0) {
            mask = JUNCTION_EXITS[10 * r + c];
            on = 1;
        } else {
            mask = DIR_LEFT | DIR_RIGHT;
        }
    } else {
        mask = c >= 0 ? DIR_UP | DIR_DOWN : DIR_LEFT | DIR_RIGHT;
    }
    if (!is_pacman) {
        mask = (uint8_t)(mask & NO_REVERSE[direction]);
        if (y == DOOR_Y && (x == DOOR_SIDE_X_LEFT || x == DOOR_SIDE_X_RIGHT)) {
            if (state & REF_GS_FRIGHT) {
                mask = 1;
            } else {
                mask = (uint8_t)(mask & 0x0E);
                if (mask == 0) {
                    mask = 1;
                }
            }
        }
    }
    *on_lattice_point = on;
    return mask;
}

void ref_wants(int32_t ey, int32_t ex, int32_t ty, int32_t tx, int32_t state, int *wv, int *wh)
{
    int fr = (state & REF_GS_FRIGHT) != 0;
    if (ey == ty) {
        *wv = 0;
    } else if (ey > ty) {
        *wv = fr ? REF_DOWN : REF_UP;
    } else {
        *wv = fr ? REF_UP : REF_DOWN;
    }
    if (ex == tx) {
        *wh = 0;
    } else if (ex > tx) {
        *wh = fr ? REF_RIGHT : REF_LEFT;
    } else {
        *wh = fr ? REF_LEFT : REF_RIGHT;
    }
}

int ref_steer(int32_t ey, int32_t ex, int32_t ty, int32_t tx, int32_t state, int32_t mask, RandomFeed *rnd)
{
    int wv, wh, d;
    int32_t r;

    ref_wants(ey, ex, ty, tx, state, &wv, &wh);
    if (wv && (mask & wv)) {
        if (wh && (mask & wh)) {
            return (random_next(rnd) & 0x80u) ? wh : wv;
        }
        return wv;
    }
    if (wh && (mask & wh)) {
        return wh;
    }
    r = (int32_t)random_next(rnd) & mask;
    if (r == 0) {
        r = mask;
    }
    for (d = REF_UP; d <= REF_RIGHT; d <<= 1) {
        if (r & d) {
            return d;
        }
    }
    return REF_RIGHT;
}

void ref_force_chase(const uint8_t states[4], int32_t x, uint8_t out[4])
{
    int32_t i;
    for (i = 0; i < 4; i++) {
        out[i] = states[i];
    }
    for (i = x; i >= 0; i--) {
        if (out[i] == GS_PATROL_TRAVEL || out[i] == GS_PATROL || out[i] == GS_CORNER) {
            out[i] = REF_GS_CHASE;
        }
    }
}

void ref_power_pellet_ghosts(const uint8_t states[4], const uint8_t dirs[4], uint8_t out_states[4], uint8_t out_dirs[4])
{
    int g;
    for (g = 0; g < 4; g++) {
        out_states[g] = states[g];
        out_dirs[g] = dirs[g];
    }
    for (g = 3; g >= 0; g--) {
        uint8_t s = states[g];
        if (s & 0x40) {
            continue;
        }
        s = (uint8_t)(s | REF_GS_FRIGHT);
        out_states[g] = s;
        if ((s >> 2) & 1) {
            continue;
        }
        if (((s >> 3) & 0x3B) == 0) {
            continue;
        }
        out_dirs[g] = REVERSE_DIR[dirs[g]];
    }
}

void ref_frightened_end(const uint8_t states[4], uint8_t out[4])
{
    int g;
    for (g = 0; g < 4; g++) {
        out[g] = states[g];
    }
    for (g = 3; g >= 0; g--) {
        uint8_t s = out[g];
        if (s & GS_FRIGHTENED_BIT) {
            if (s == GS_FRIGHTENED_BIT) {
                out[g] = 0;
            } else if (s & GS_END_FRIGHT_MASK) {
                out[g] = GS_CORNER;
            }
        }
    }
}

/* ------------------------------------------------------------------------------------------------ the dot count */
int ref_count_dot(uint8_t lo, uint8_t hi, uint8_t *new_lo, uint8_t *new_hi)
{
    lo = (uint8_t)(lo + 1u);
    if (lo == 0) {
        hi = (uint8_t)(hi + 1u);
    }
    *new_lo = lo;
    *new_hi = hi;
    return hi != 0 && lo == 4;
}
