/* core/house.c - the ghost house (stage 76b).  Twin of the house part of tools/core_ghost.py. */
#include "ghost.h"

#include "tables.h"
#include "constants.h"

void house_bob_step(World *w, int i)
{
    if (w->EntityDir[i] == DIR_UP) {
        if (w->EntityY[i] == 0x70) {
            w->EntityDir[i] = DIR_DOWN;
        }
    } else if (w->EntityY[i] == 0x78) {
        w->EntityDir[i] = DIR_UP;
    }
    step_entity(w, i, w->EntityDir[i]);
}

static void set_dir_step(World *w, int i, uint8_t d)
{
    w->EntityDir[i] = d;
    step_entity(w, i, d);
}

void house_leave_step(World *w, int i)
{
    uint8_t s, a, d;

    if (w->EntityY[i] != GHOST_DOOR_Y) {
        set_dir_step(w, i, 1);
        return;
    }
    s = w->GhostState[i];
    if (s == 0) {
        a = 1;
        d = 4;
    } else {
        a = (uint8_t)((s & GS_FRIGHTENED_BIT) | 2);
        if (a & GS_FRIGHTENED_BIT) {
            w->ChaseTimer = a;                      /* a frightened ghost loads ChaseTimer with its state: a quirk of the code */
            d = 8;
        } else {
            d = 4;
        }
    }
    w->EntityDir[i] = d;
    w->GhostState[i] = a;
}

void house_leave_ghost2(World *w, int i)
{
    if (w->EntityX[i] == GHOST_DOOR_X) {
        house_leave_step(w, i);
    } else {
        set_dir_step(w, i, 8);
    }
}

void house_leave_ghost3(World *w, int i)
{
    if (w->EntityX[i] == GHOST_DOOR_X) {
        house_leave_step(w, i);
    } else {
        set_dir_step(w, i, 4);
    }
}

void house_leave(World *w, int i)
{
    if (i == 3) {
        house_leave_ghost3(w, i);
    } else if (i == 2) {
        house_leave_ghost2(w, i);
    } else {
        house_leave_step(w, i);
    }
}

void house_enter_step(World *w, int i)
{
    if (w->EntityY[i] != HOUSE_FLOOR_Y) {
        set_dir_step(w, i, 2);
        return;
    }
    if (i == 2 && w->EntityX[i] != 0x70) {
        set_dir_step(w, i, 4);
        return;
    }
    if (i == 3 && w->EntityX[i] != 0x88) {
        set_dir_step(w, i, 8);
        return;
    }
    w->GhostState[i] = (uint8_t)(w->GhostState[i] & GS_LOW_NIBBLE);
    w->shadow[0xC0 + i] = table_rom((uint16_t)(0xBBE2 + i));     /* PCOLR0 + i */
}

void house_waiting_tick(World *w)
{
    int i;
    for (i = 1; i <= 3; i++) {
        if (w->GhostState[i] & 0x7F) {
            continue;
        }
        if (w->GhostTimer[i]) {
            w->GhostTimer[i] = (uint8_t)(w->GhostTimer[i] - 1u);
            house_bob_step(w, i);
        } else {
            house_leave(w, i);
        }
    }
}
