/* app/init.c - the state initialisation (stage 79a).  Twin of tools/core_app_init.py: read the two side by side. */
#include "init.h"

#include <string.h>

#include "../core/draw.h"
#include "../core/score.h"
#include "../core/sound.h"
#include "../core/tables.h"

#define COLORS_GAME 0xBBE2          /* ColorsGame: 8 bytes (PCOLR0-3, COLOR0-3) */
#define ZERO_PAGE_INIT_80 0xBB6F    /* ZeroPageInit80: 20 bytes copied to $80-$93 */
#define HOUSE_RELEASE_TIMERS 0xBBF2
#define HITCLR_ADDR 0xD01E

void world_zp_set(World *w, int addr, uint8_t value)
{
    int i;
    if (addr < 0 || addr > 0xFF) {
        return;
    }
    for (i = 0; i < PM_WORLD_ZP_FIELDS; i++) {
        const WorldRegion *r = &world_regions[i];
        if (addr >= r->addr && addr < r->addr + r->count) {
            ((uint8_t *)w)[r->offset + (size_t)(addr - r->addr)] = value;
            return;
        }
    }
}

void clear_zp(World *w, int lo, int hi)
{
    int a;
    for (a = lo; a < hi; a++) {
        world_zp_set(w, a, 0);
    }
}

/* ------------------------------------------------------------------------------------------------ the maze copies and the colours */
void copy_0800_to_0c00(World *w)
{
    memcpy(w->maze, w->maze_orig, sizeof w->maze);
}

void copy_0c00_to_1000(World *w)
{
    memcpy(w->saved1, w->maze, sizeof w->saved1);
}

void copy_0c00_to_1400(World *w)
{
    memcpy(w->saved2, w->maze, sizeof w->saved2);
}

void load_shadow_colors(World *w)
{
    int x;
    for (x = 7; x >= 0; x--) {
        w->shadow[0xC0 + x] = table_rom((uint16_t)(COLORS_GAME + x));
    }
}

/* ------------------------------------------------------------------------------------------------ the counters and the timers */
void clear_player_counters(World *w, int x)
{
    w->PelletFlags[x] = 0x0F;
    w->BonusCount[x] = 0;
    w->DotsEatenLo[x] = 0;
    w->DotsEatenHi[x] = 0;
}

void set_release_timers(World *w, int y)
{
    int x;
    y &= 0xFF;
    if (y > 3) {
        y = 3;
    }
    for (x = 2; x >= 0; x--) {
        w->GhostTimer[1 + x] = table_rom((uint16_t)(HOUSE_RELEASE_TIMERS + y));
        y++;
    }
}

/* ------------------------------------------------------------------------------------------------ the start of a board */
void init_board(World *w)
{
    int lv, x;

    clear_player_memory(w);
    clear_zp(w, 0x80, 0x100);
    load_shadow_colors(w);
    lv = w->Level[w->CurrentPlayer];
    if (lv > 6) {
        lv = 6;
    }
    w->MoveDelayCount[4] = MOVE_DELAY[PAC_DELAY_BASE[lv]];              /* Pac-Man's pacing */
    for (x = 3; x >= 0; x--) {
        w->MoveDelayCount[x] = MOVE_DELAY[GHOST_DELAY_BASE[lv]];        /* the four ghosts: the same entry (Y does not move in the loop) */
    }
    for (x = 19; x >= 0; x--) {
        world_zp_set(w, 0x80 + x, table_rom((uint16_t)(ZERO_PAGE_INIT_80 + x)));    /* MazePtr, PacSubX, LastCell, the start positions and directions */
    }
    set_release_timers(w, 0);
    sound_wr(w, HITCLR_ADDR, 0);
}

void new_board_init(World *w)
{
    int p, y;

    copy_0800_to_0c00(w);
    draw_lives(w);
    p = w->CurrentPlayer;
    y = w->Level[p];
    if (y == 0 && (w->RTCLOK2 & 0x80)) {
        set_release_timers(w, 0);                                        /* LAE13 with Y = 0 */
    } else {
        y = (y + 1) & 0xFF;                                              /* LAE19: iny; bne LAE13 (a level of 255 skips the timers) */
        if (y != 0) {
            set_release_timers(w, y);
        }
    }
    clear_player_counters(w, p);
}

void new_game_init(World *w)
{
    w->Lives[0] = 3;
    w->Lives[1] = 3;
    w->Level[0] = w->StartLevel;
    w->Level[1] = w->StartLevel;
    clear_player_counters(w, 1);
    new_board_init(w);
}
