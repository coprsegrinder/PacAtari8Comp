/* core/frame.c - the ghost logic that runs every frame (stage 76d).  Twin of tools/core_frame.py: read the two side by side. */
#include "frame.h"

#include "draw.h"
#include "ghost.h"
#include "ref.h"
#include "score.h"
#include "sound.h"
#include "tables.h"
#include "constants.h"

/* the frightened ghosts alternate blue ($84) and white ($0C) with the phase */
static void flash_colours(World *w)
{
    uint8_t y = (w->FrightenPhase & 1) ? 0x84 : 0x0C;
    int x;
    for (x = 3; x >= 0; x--) {
        if (w->GhostState[x] & GS_FRIGHTENED_BIT) {
            w->shadow[FRAME_PCOLR0 + x] = y;
        }
    }
}

void frightened_tick(World *w)
{
    int x;
    uint8_t ended[4];

    if (w->FrightenPhase == 0) {
        if (w->EyesReturning == 0) {
            siren(w);
        }
        return;
    }
    if (w->EyesReturning == 0) {
        frightened_sound(w);
    }
    if (w->FrightenCountdown) {
        w->FrightenCountdown = (uint8_t)(w->FrightenCountdown - 1u);
        flash_colours(w);
        return;
    }
    if (ref_fright_end_phase(w->Level[w->CurrentPlayer]) == w->FrightenPhase) {
        for (x = 3; x >= 0; x--) {
            if (w->GhostState[x] & GS_FRIGHTENED_BIT) {
                w->shadow[FRAME_PCOLR0 + x] = table_rom((uint16_t)(0xBBE2 + x));
            }
        }
        ref_frightened_end(w->GhostState, ended);
        for (x = 0; x < 4; x++) {
            w->GhostState[x] = ended[x];
        }
        w->FrightenPhase = 0;
        w->FrightenFlashTimer = 0;
        w->FrightSound[3] = 0;
        w->ChaseTimer = 0xA0;
        return;
    }
    if (w->FrightenFlashTimer == 0) {
        w->FrightenPhase = (uint8_t)(w->FrightenPhase + 1u);
        w->FrightenFlashTimer = FRIGHT_FLASH_FRAMES;
    }
    w->FrightenFlashTimer = (uint8_t)(w->FrightenFlashTimer - 1u);
    flash_colours(w);
}

void ghost_eaten(World *w, int x)
{
    int py, ey, a, g;

    w->GhostState[x] = GS_EYES;
    w->EatenGhost = (uint8_t)x;
    w->GhostsEaten = (uint8_t)(w->GhostsEaten + 1u);
    w->shadow[0xC7] = 0xDC;                          /* COLOR3 */
    w->shadow[FRAME_PCOLR0 + x] = 0xDC;
    draw_popup(w, x);
    py = w->EntityY[4];
    ey = w->EntityY[x];
    if (py == ey) {
        a = py;
    } else if (py < ey) {
        a = (py + 2) & 0xFF;
    } else {
        a = (py - 2) & 0xFF;
    }
    w->PopupMissilePtr[0] = (uint8_t)a;
    w->PopupPlayerPtr[0] = (uint8_t)a;
    w->PopupMissilePtr[1] = 0x23;
    w->PopupPlayerPtr[1] = (uint8_t)((x + 0x23 + 1) & 0xFF);
    sound_wr(w, POKEY_AUDC2, 0);
    w->EatPause = (uint8_t)(w->EatPause + 1u);
    w->EatPausePitch = 0x84;
    w->EatPauseTick = 2;
    w->shadow[0x6F] = PRIORITY_POPUP;                          /* GPRIOR: the pop-up in front */
    g = w->GhostsEaten;
    if (g == 0) {
        w->ScoreAdd[3] = 2;
    } else if (g == 1) {
        w->ScoreAdd[3] = 4;
    } else if (g == 2) {
        w->ScoreAdd[3] = 8;
    } else {
        w->ScoreAdd[2] = 1;
        w->ScoreAdd[3] = 6;
    }
    add_to_score(w);
}

void eyes_and_house_per_frame(World *w, RandomFeed *rnd)
{
    int x, on;
    uint8_t mask;

    w->EyesReturning = 0;
    for (x = 3; x >= 0; x--) {
        uint8_t s = w->GhostState[x];
        if (s == GS_EYES_AT_DOOR || !(s & 0x40) || x == w->EatenGhost) {
            continue;
        }
        w->EyesReturning = (uint8_t)(w->EyesReturning + 1u);
        if (w->EntityX[x] == GHOST_DOOR_X && w->EntityY[x] == GHOST_DOOR_Y) {
            if (w->EntityDir[x] == DIR_UP) {
                w->EntityDir[x] = DIR_LEFT;                 /* arriving from below: turn left first */
            } else {
                w->GhostState[x] = GS_EYES_AT_DOOR;
                w->StartRouteStep[x] = 0xFF;
                continue;
            }
        }
        mask = junction_lookup(w, x, &on);
        if (on) {
            w->TargetX[x] = GHOST_DOOR_X;
            w->TargetY[x] = GHOST_DOOR_Y;
            steer_to_target(w, x, mask, rnd);
        }
        step_entity(w, x, w->EntityDir[x]);
    }
    if (w->EyesReturning == 0) {
        w->EyesSoundStep = 0;
    } else if (w->EatPause == 0) {
        eyes_returning_sound(w);
    }
    for (x = 3; x >= 0; x--) {
        uint8_t s = w->GhostState[x];
        if (!((s >> 2) & 1)) {
            continue;
        }
        if (s & 0x40) {
            house_enter_step(w, x);
        } else if ((w->RTCLOK2 & 3) == 0) {
            house_leave(w, x);
        }
    }
}
