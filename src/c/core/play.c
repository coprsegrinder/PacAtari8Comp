/* core/play.c - one frame of play (stage 76d).  Twin of tools/core_play.py: read the two side by side. */
#include "play.h"

#include "draw.h"
#include "frame.h"
#include "ghost.h"
#include "pacman.h"
#include "ref.h"
#include "score.h"
#include "sound.h"
#include "tables.h"
#include "constants.h"

static const int pellet_cells[3] = {0x7B, 0x9C, 0x283};   /* the first three power-pellet cells of the maze screen ($0C7B, $0C9C, $0E83 minus $0C00); the fourth is $2A4 */

void show_power_pellets(World *w)
{
    uint8_t flags = w->PelletFlags[w->CurrentPlayer];
    int k;
    w->Scratch2A = flags;
    for (k = 0; k < 3; k++) {
        if (flags & (1 << k)) {
            w->maze[pellet_cells[k]] = 2;
        }
    }
    if (flags & 8) {
        w->maze[PLAY_LAST_PELLET_CELL] = 2;
    }
}

void blink_power_pellets(World *w)
{
    int a = w->RTCLOK2 & 0x0F;
    int k;
    if (a == 0) {
        show_power_pellets(w);
    } else if (a == 8) {
        for (k = 0; k < 3; k++) {
            w->maze[pellet_cells[k]] = 0;
        }
        w->maze[PLAY_LAST_PELLET_CELL] = 0;
    }
}

void bonus_item_update(World *w)
{
    int p, k, t, fire;
    uint8_t dots, code;

    if (w->BonusScoreShown) {
        if (w->BonusScoreTimer == 0) {
            w->BonusScoreShown = 0;
            for (k = 0; k < 5; k++) {
                w->maze[PLAY_BONUS_CELLS + k] = 0;
            }
        } else {
            w->BonusScoreTimer = (uint8_t)(w->BonusScoreTimer - 1u);
        }
        return;
    }
    if (w->BonusVisible == 0) {
        p = w->CurrentPlayer;
        dots = w->DotsEatenLo[p];
        t = w->BonusCount[p];
        if (t == 0) {
            fire = dots == BONUS_FIRST_DOTS || dots == BONUS_SECOND_DOTS;
        } else if (t == 1) {
            fire = dots == BONUS_SECOND_DOTS;
        } else {
            return;
        }
        if (!fire) {
            return;
        }
        w->BonusCount[p] = (uint8_t)(t + 1);
        code = ref_bonus_glyph(w->Level[p]);
        w->maze[0x1F3] = code;
        w->maze[0x1F4] = (uint8_t)(code + 1u);
        w->BonusVisible = 1;
        w->BonusTimer[0] = BONUS_TIME_LO;
        w->BonusTimer[1] = BONUS_TIME_HI;
        return;
    }
    if (w->BonusTimer[1] == 0 && w->BonusTimer[0] == 0) {
        w->maze[0x1F3] = 0;
        w->maze[0x1F4] = 0;
        w->BonusVisible = 0;
        return;
    }
    w->BonusTimer[0] = (uint8_t)(w->BonusTimer[0] - 1u);
    if (w->BonusTimer[0] == 0) {
        w->BonusTimer[1] = (uint8_t)(w->BonusTimer[1] - 1u);
    }
}

int move_delay_tick_w(World *w, int x)
{
    int32_t cycle = w->MoveDelayCycle[x];
    uint8_t count = w->MoveDelayCount[x];
    int moves = ref_move_delay_tick(x, w->Level[w->CurrentPlayer], &cycle, &count);
    w->MoveDelayCycle[x] = (uint8_t)cycle;
    w->MoveDelayCount[x] = count;
    return moves;
}

/* $A93D: Pac-Man touched the bonus item (missile 2 on playfield 1): its score picture, 100-5000 points by level, and the bonus sound */
static void pick_up_bonus(World *w)
{
    int p = w->CurrentPlayer;
    int lv = w->Level[p] < LEVEL_CLAMP_BONUS ? w->Level[p] : LEVEL_CLAMP_BONUS;
    int off = BONUS_SCORE_GLYPH_OFFSETS[lv];
    int k;

    for (k = 0; k < 5; k++) {
        w->maze[PLAY_BONUS_CELLS + k] = BONUS_SCORE_GLYPHS[off + k];
    }
    w->BonusScoreShown = 1;
    w->BonusScoreTimer = BONUS_SCORE_TIME;
    w->BonusVisible = 0;
    w->BonusTimer[0] = 0;
    w->BonusTimer[1] = 0;
    w->BonusSoundStep = 1;
    w->BonusSoundPitch = 0x78;
    w->ScoreAdd[2] = BONUS_SCORE[2 * lv];
    w->ScoreAdd[3] = BONUS_SCORE[2 * lv + 1];
    add_to_score(w);
}

/* $A843 - $A98B: the pellet, the contact with a ghost (frightened: eaten; otherwise Pac-Man is killed), the bonus pick-up.  Returns 1 when the frame is over (a ghost was eaten) */
static int contact_and_bonus(World *w)
{
    int x, y, d;

    bonus_item_update(w);
    power_pellet_check(w);
    if (!w->LevelComplete) {
        y = 1;
        for (x = 0; x < 4; x++) {
            if (((w->GhostState[x] << 1) & 0x80) == 0 && (w->collide[PLAY_M1PL] & y) && (w->collide[PLAY_M2PL] & y)) {
                d = w->EntityY[4] - w->EntityY[x];
                if (d < 0) {
                    d = -d;
                }
                if (d < 5) {
                    if (w->GhostState[x] & GS_FRIGHTENED_BIT) {
                        ghost_eaten(w, x);
                        return 1;
                    }
                    w->PacFrozen = (uint8_t)(w->PacFrozen | 0x80);     /* the ghost kills Pac-Man: the death sequence starts */
                    clear_pokey(w);
                    w->DrawOnly = 1;
                    w->DeathState = 1;
                    w->DeathFreeze = DEATH_FREEZE;
                    break;
                }
            }
            y <<= 1;
        }
    }
    if (w->collide[PLAY_M2PF] & 2) {
        pick_up_bonus(w);
    }
    sound_wr(w, GTIA_HITCLR, 0);
    return 0;
}

void play_frame(World *w, RandomFeed *rnd)
{
    int x;
    uint8_t hold;

    blink_power_pellets(w);
    if (w->DeathState) {
        death_sequence(w);
        death_animation(w);
        return;
    }
    eyes_and_house_per_frame(w, rnd);
    if (w->EatPause) {
        ghost_eaten_pause(w);
        return;
    }
    if (contact_and_bonus(w)) {
        return;
    }
    if (w->DeathState) {
        return;
    }
    frightened_tick(w);
    if (w->EatPause) {
        return;
    }
    dot_sound_sweep(w);
    bonus_sound(w);
    toggle_leg_phase(w);
    if (w->PacCornering) {
        hold = 0;
    } else if (w->DotDelay) {
        hold = w->DotDelay;
    } else {
        hold = move_delay_tick_w(w, 4) ? 0 : 0xFF;
    }
    w->PacHold = hold;
    w->PacCornering = 0;
    move_pacman(w);
    w->DotDelay = 0;
    eat_dot(w);
    if ((w->RTCLOK2 & 3) == 0) {
        house_waiting_tick(w);
    }
    chase_timer_siren_sight(w);
    if (w->PacCornering) {
        return;                                      /* Pac-Man turned a corner this frame: the ghosts stand still */
    }
    for (x = 3; x >= 0; x--) {
        uint8_t s = w->GhostState[x];
        int in_tunnel;
        if ((s & 0x7F) == 0) {
            continue;
        }
        if ((w->RTCLOK2 & 7) == 0 && w->GhostTimer[x]) {
            w->GhostTimer[x] = (uint8_t)(w->GhostTimer[x] - 1u);
        }
        s = w->GhostState[x];
        if ((s & 0x3F) == 0 || ((s << 1) & 0x80)) {
            continue;
        }
        in_tunnel = w->EntityY[x] == TUNNEL_Y && (w->EntityX[x] >= 0xA7 || w->EntityX[x] < 0x52);
        if (in_tunnel || (s & GS_FRIGHTENED_BIT)) {               /* in the tunnel, and while frightened, a ghost moves every second tick */
            if (move_delay_tick_w(w, x)) {
                if (w->HalfSpeedToggle[x] == 1) {
                    w->HalfSpeedToggle[x] = 0;
                    ghost_behaviour(w, x, rnd);
                } else {
                    w->HalfSpeedToggle[x] = 1;
                }
            }
        } else if (move_delay_tick_w(w, x)) {
            ghost_behaviour(w, x, rnd);
        }
    }
}

void vbi_play_frame(World *w, RandomFeed *rnd)
{
    play_frame(w, rnd);
    if (w->EatPause == 0) {
        clip_entities_on_tunnel_row(w);
    }
}
