/* core/score.c - scoring, dots and power pellets (stage 76c).  Twin of tools/core_score.py: read the two side by side. */
#include "score.h"

#include "ref.h"
#include "constants.h"

static const int life_icon_cells[3] = {0x374, 0x376, 0x378};   /* $0F74, $0F76, $0F78 minus $0C00 */

void draw_lives(World *w)
{
    int n = w->Lives[w->CurrentPlayer];
    int k;
    for (k = 0; k < 3; k++) {
        w->maze[life_icon_cells[k]] = (n <= 3 && n >= k + 1) ? SCORE_LIFE_ICON : 0;
    }
}

void add_to_score(World *w)
{
    int p = w->CurrentPlayer;
    int base = p == 0 ? SCORE_CELL_P1 : SCORE_CELL_P2;
    uint8_t cells[6], created[6];
    int carry = 0, y, k;

    for (k = 0; k < 6; k++) {
        cells[k] = w->status[base + k];
        created[k] = cells[k];
    }
    for (y = 5; y >= 0; y--) {
        int s = (cells[y] & SCORE_DIGIT_MASK) + carry + w->ScoreAdd[y];
        int d, code;
        carry = s >= 10 ? 1 : 0;
        d = s % 10;
        code = SCORE_DIGIT_BASE | d;
        if (d == 0) {
            if (y == 0) {
                code = 0;
            } else {
                code = (cells[y - 1] != 0 || carry) ? SCORE_DIGIT_BASE : 0;
            }
        }
        created[y] = (uint8_t)code;
    }
    for (k = 0; k < 6; k++) {
        w->status[base + k] = created[k];
        w->ScoreAdd[k] = 0;
    }
    w->BcdCarry = (uint8_t)carry;
    if (w->ExtraLifeFlag[p] == 0 && created[1] != 0) {
        w->ExtraLifeFlag[p] = (uint8_t)(w->ExtraLifeFlag[p] + 1u);
        w->Lives[p] = (uint8_t)(w->Lives[p] + 1u);
        draw_lives(w);
    }
}

void count_dot(World *w)
{
    int p = w->CurrentPlayer;
    uint8_t lo, hi;
    (void)ref_count_dot(w->DotsEatenLo[p], w->DotsEatenHi[p], &lo, &hi);
    w->DotsEatenLo[p] = lo;
    w->DotsEatenHi[p] = hi;
    if (hi != 0 && lo == 4) {
        w->LevelComplete = LEVEL_COMPLETE_SET;
    }
}

void eat_dot(World *w)
{
    int32_t ptr, i;
    uint8_t v;

    if (w->PacSubX || w->PacSubY) {
        return;
    }
    if (w->EntityX[4] == w->LastCellX && w->EntityY[4] == w->LastCellY) {
        return;
    }
    w->LastCellY = w->EntityY[4];
    w->LastCellX = w->EntityX[4];
    ptr = w->MazePtr[0] | (w->MazePtr[1] << 8);
    i = ptr - 0x0C00;
    if (i < 0) {
        i += 0x400;                                  /* Python indexes a list from its end: the check's ROM states put the pointer below the maze */
    }
    if (i < 0 || i >= 0x400) {
        return;                                      /* Python raises IndexError: not a state of the game */
    }
    v = w->maze[i];
    if (v == 2) {
        w->maze[i] = 0;
        return;
    }
    if (v != 1) {
        return;
    }
    w->ScoreAdd[4] = 1;
    add_to_score(w);
    w->DotSoundActive = 1;
    w->DotDelay = 1;
    w->DotSoundStep = 0;
    w->DotSoundAlt = w->DotSoundAlt == 0 ? 1 : 0;
    w->maze[i] = 0;
    count_dot(w);
}

void power_pellet_check(World *w)
{
    static const uint8_t pellet_y[4] = {0x3C, 0x3C, 0xA4, 0xA4};
    static const uint8_t pellet_x[4] = {0x3A, 0xBE, 0x3A, 0xBE};
    int p = w->CurrentPlayer;
    uint8_t flags = w->PelletFlags[p];
    int bit = 0, i;
    uint8_t states[4], dirs[4];

    for (i = 0; i < 4; i++) {
        if ((flags & (1 << i)) && w->EntityY[4] == pellet_y[i] && w->EntityX[4] == pellet_x[i]) {
            bit = 1 << i;
            break;
        }
    }
    if (bit == 0) {
        return;
    }
    w->Scratch2A = flags;
    w->PelletFlags[p] = (uint8_t)((bit ^ 0x0F) & flags);
    w->ScoreAdd[4] = 5;
    add_to_score(w);
    w->FrightenPhase = 1;
    w->GhostsEaten = 0xFF;
    w->FrightenCountdown = ref_fright_frames(w->Level[p]);
    ref_power_pellet_ghosts(w->GhostState, w->EntityDir, states, dirs);
    for (i = 0; i < 4; i++) {
        w->GhostState[i] = states[i];
        w->EntityDir[i] = dirs[i];
    }
    count_dot(w);
}
