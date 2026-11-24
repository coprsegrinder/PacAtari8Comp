/* core/ghost.c - the ghost state machine (stage 76b).  Twin of tools/core_ghost.py: read the two side by side. */
#include "ghost.h"

#include "draw.h"
#include "ref.h"
#include "tables.h"
#include "constants.h"

/* ------------------------------------------------------------------------------------------------ the lattice and the steering */
uint8_t junction_lookup(const World *w, int i, int *on_lattice_point)
{
    return ref_junction_exits(i == 4, w->EntityX[i], w->EntityY[i], w->EntityDir[i], i < 4 ? w->GhostState[i] : 0, on_lattice_point);
}

void steer_to_target(World *w, int i, uint8_t mask, RandomFeed *rnd)
{
    uint8_t state = w->GhostState[i];
    int wv, wh;
    ref_wants(w->EntityY[i], w->EntityX[i], w->TargetY[i], w->TargetX[i], state, &wv, &wh);
    w->WantVert[i] = (uint8_t)wv;
    w->WantHoriz[i] = (uint8_t)wh;
    w->EntityDir[i] = (uint8_t)ref_steer(w->EntityY[i], w->EntityX[i], w->TargetY[i], w->TargetX[i], state, mask, rnd);
}

void step_entity(World *w, int i, int32_t d)
{
    step_and_draw_entity(w, i, d);
}

/* ------------------------------------------------------------------------------------------------ the sight test */
/* the loop `lda base,y / cmp #$FF / beq found / cmp limit / bcs stop / iny / bne`: returns 1 when $FF was met; *value is the last value read */
static int scan_up(int base, int y, int limit, int *value)
{
    for (;;) {
        int v = table_rom((uint16_t)(base + y));
        if (v == 0xFF) {
            *value = v;
            return 1;
        }
        if (v >= limit) {
            *value = v;
            return 0;
        }
        y = (y + 1) & 0xFF;
        if (y == 0) {
            *value = v;
            return 0;
        }
    }
}

static int find_last(const uint8_t *table, int value)
{
    int k;
    for (k = 9; k >= 0; k--) {
        if (table[k] == value) {
            return k;
        }
    }
    return -1;
}

int ghost_sees(const World *w, int i)
{
    int gx = w->EntityX[i], gy = w->EntityY[i], d = w->EntityDir[i];
    int px = w->EntityX[4], py = w->EntityY[4];
    int y, v, ff;

    if (gy == py) {
        y = find_last(JUNCTION_Y, py);
        if (y < 0) {
            return 0;
        }
        if (gx < px) {
            if (d != 8) {
                return 0;
            }
            ff = scan_up(0xBBB8, y, gx, &v);
            return ff ? 1 : v >= px;
        }
        if (d != 4) {
            return 0;
        }
        ff = scan_up(0xBBB8, y, px, &v);
        return ff ? 1 : v >= gx;
    }
    if (gx == px) {
        y = find_last(JUNCTION_X, px);
        if (y < 0) {
            return 0;
        }
        if (gy >= py) {
            if (d != 1) {
                return 0;
            }
            ff = scan_up(0xBBD8, y, py, &v);
            return ff ? 1 : v >= gy;
        }
        if (d != 2) {
            return 0;
        }
        ff = scan_up(0xBBD8, y, gy, &v);
        return ff ? 1 : v >= py;
    }
    return 0;
}

void ghost_sees_pacman(World *w, int i)
{
    if (ghost_sees(w, i) && !(i == 2 && (w->RTCLOK2 & 0x80))) {
        w->GhostState[i] = GHOST_CHASE;
        w->ChaseTimer = CHASE_ON_SIGHT;
    }
}

/* ------------------------------------------------------------------------------------------------ timers, siren, forced chase */
void force_chase(World *w, int x)
{
    int k;
    for (k = x; k >= 0; k--) {
        uint8_t s = w->GhostState[k];
        if (s == GS_PATROL_TRAVEL || s == GS_PATROL || s == GS_CORNER) {
            w->GhostState[k] = GHOST_CHASE;
        }
    }
    w->ChaseTimer = 0xFF;
}

void chase_timer_siren_sight(World *w)
{
    int p, g, step;
    uint8_t lo, hi;

    if ((w->RTCLOK2 & 7) == 0 && w->ChaseTimer != 0) {
        w->ChaseTimer = (uint8_t)(w->ChaseTimer - 1u);
    }
    p = w->CurrentPlayer;
    lo = w->DotsEatenLo[p];
    hi = w->DotsEatenHi[p];
    if (hi != 0 || lo >= LATE_BOARD_DOTS_2) {
        force_chase(w, 3);
        step = 5;
    } else if (lo >= LATE_BOARD_DOTS_1) {
        force_chase(w, 2);
        step = 4;
    } else if (lo >= 0xB0) {
        step = 3;
    } else {
        step = 2;
    }
    w->SirenStep = (uint8_t)step;
    for (g = 3; g >= 0; g--) {
        if (w->GhostState[g] == GS_PATROL_TRAVEL || w->GhostState[g] == GS_PATROL) {
            ghost_sees_pacman(w, g);
        }
    }
}

/* ------------------------------------------------------------------------------------------------ the behaviour of a ghost by its state */
void ghost_behaviour(World *w, int i, RandomFeed *rnd)
{
    uint8_t s = w->GhostState[i];
    if (s & GS_FRIGHTENED_BIT) {                                 /* frightened: bit 2 clear -> flee (chase steering), bit 2 set -> stands */
        if ((s >> 2) & 1) {
            return;
        }
        ghost_chase(w, i, rnd);
        return;
    }
    switch (s) {
    case 0x01:
        ghost_start_route(w, i, rnd);
        break;
    case 0x02:
        if (w->ChaseTimer != 0) {
            ghost_chase(w, i, rnd);
        } else {
            ghost_go_to_corner(w, i, rnd);
        }
        break;
    case 0x08:
        ghost_patrol_travel(w, i, rnd);
        break;
    case GS_PATROL:
        ghost_patrol(w, i, rnd);
        break;
    case GS_CORNER:
        ghost_go_to_corner(w, i, rnd);
        break;
    default:
        break;
    }
}

void ghost_start_route(World *w, int i, RandomFeed *rnd)
{
    int on;
    uint8_t d;
    int32_t ptr;

    (void)junction_lookup(w, i, &on);
    if (on) {
        w->StartRouteStep[i] = (uint8_t)(w->StartRouteStep[i] + 1u);
    }
    ptr = (int32_t)((table_rom((uint16_t)(0xBCE6 + 2 * i)) | (table_rom((uint16_t)(0xBCE6 + 2 * i + 1)) << 8)) + w->StartRouteStep[i]) & 0xFFFF;
    d = table_ram((uint16_t)ptr);
    if (d == 0x0F) {
        if (i != 0) {
            ghost_select_patrol(w, i, rnd);
            return;
        }
        w->ChaseTimer = CHASE_AFTER_START_ROUTE;
        w->GhostState[0] = GHOST_CHASE;
        ghost_chase(w, i, rnd);
        return;
    }
    w->EntityDir[i] = d;
    step_entity(w, i, w->EntityDir[i]);
}

void ghost_select_patrol(World *w, int i, RandomFeed *rnd)
{
    int route;
    w->GhostState[i] = GHOST_PATROL_TRAVEL;
    w->PatrolStep[i] = 0;
    route = random_next(rnd) & 0x0F;
    w->PatrolRoute[i] = (uint8_t)route;
    w->TargetX[i] = table_rom((uint16_t)(0xBCEE + 2 * route));
    w->TargetY[i] = table_rom((uint16_t)(0xBCEE + 2 * route + 1));
    w->GhostTimer[i] = GHOST_PATROL_TIME;
    ghost_patrol_travel(w, i, rnd);
}

static void read_patrol_route(World *w, int i)
{
    int off = table_rom((uint16_t)(0xBD16 + w->PatrolRoute[i]));
    uint8_t d = table_ram((uint16_t)(0x06AE + ((off + w->PatrolStep[i]) & 0xFF)));
    if (d == 0) {
        w->PatrolStep[i] = 0;
        d = table_ram((uint16_t)(0x06AE + off));
    }
    w->EntityDir[i] = d;
    step_entity(w, i, d);
}

void ghost_patrol_travel(World *w, int i, RandomFeed *rnd)
{
    int on;
    uint8_t mask;

    if (w->GhostTimer[i] == 0) {
        ghost_go_to_corner(w, i, rnd);
        return;
    }
    mask = junction_lookup(w, i, &on);
    if (!on) {
        step_entity(w, i, w->EntityDir[i]);
        return;
    }
    steer_to_target(w, i, mask, rnd);
    if (w->WantHoriz[i] || w->WantVert[i]) {
        step_entity(w, i, w->EntityDir[i]);
        return;
    }
    w->GhostState[i] = GHOST_PATROL;
    read_patrol_route(w, i);
}

void ghost_patrol(World *w, int i, RandomFeed *rnd)
{
    int on;

    if (w->GhostTimer[i] == 0) {
        ghost_go_to_corner(w, i, rnd);
        return;
    }
    (void)junction_lookup(w, i, &on);
    if (on) {
        w->PatrolStep[i] = (uint8_t)(w->PatrolStep[i] + 1u);
    }
    read_patrol_route(w, i);
}

void ghost_go_to_corner(World *w, int i, RandomFeed *rnd)
{
    int on;
    uint8_t mask;

    w->GhostState[i] = GHOST_CORNER;
    w->TargetX[i] = table_rom((uint16_t)(0xBD0E + 2 * i));
    w->TargetY[i] = table_rom((uint16_t)(0xBD0E + 2 * i + 1));
    mask = junction_lookup(w, i, &on);
    if (!on) {
        step_entity(w, i, w->EntityDir[i]);
        return;
    }
    steer_to_target(w, i, mask, rnd);
    if (w->WantHoriz[i] || w->WantVert[i]) {
        step_entity(w, i, w->EntityDir[i]);
        return;
    }
    ghost_select_patrol(w, i, rnd);
}

void ghost_chase(World *w, int i, RandomFeed *rnd)
{
    int on;
    uint8_t mask;

    w->TargetX[i] = w->EntityX[4];
    w->TargetY[i] = w->EntityY[4];
    mask = junction_lookup(w, i, &on);
    if (on) {
        steer_to_target(w, i, mask, rnd);
    }
    step_entity(w, i, w->EntityDir[i]);
}
