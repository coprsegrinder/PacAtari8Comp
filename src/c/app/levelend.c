/* app/levelend.c - the end of a level (stage 79b).  Twin of tools/core_app_board.py. */
#include "board.h"

#include "../core/draw.h"
#include "../core/sound.h"
#include "init.h"

void advance_level(World *w)
{
    int p;

    new_board_init(w);
    p = w->CurrentPlayer;
    w->Lives[p] = (uint8_t)(w->Lives[p] + 1u);
    w->Level[p] = (uint8_t)(w->Level[p] + 1u);
    draw_level_indicator(w);
    draw_ready_screen(w);
    w->LevelComplete = 0;
    w->LevelEndStep = 0;
    w->WaitState = 2;
    w->WaitTimer = 0x40;
}

void level_end_step(World *w)
{
    int s = w->LevelEndStep, x;

    if (s == 0) {
        clear_pokey(w);
        draw_all_in_place(w);
        w->LevelEndDelay = 0x40;
        w->LevelEndStep = (uint8_t)(w->LevelEndStep + 1u);
        return;
    }
    if (s == 1) {
        if (w->LevelEndDelay) {
            w->LevelEndDelay = (uint8_t)(w->LevelEndDelay - 1u);
            return;
        }
        for (x = 3; x >= 0; x--) {
            w->hpos[x] = 0;                                  /* the ghosts leave the screen */
        }
        w->shadow[0xC4] = 0x0C;                              /* COLOR0 */
        w->LevelEndFlashes = 7;
        w->LevelEndDelay = 0x10;
        w->LevelEndStep = (uint8_t)(w->LevelEndStep + 1u);
        return;
    }
    if (s == 2) {
        if (w->LevelEndDelay) {
            w->LevelEndDelay = (uint8_t)(w->LevelEndDelay - 1u);
            return;
        }
        w->LevelEndFlashes = (uint8_t)(w->LevelEndFlashes - 1u);
        if (w->LevelEndFlashes == 0) {
            w->LevelEndStep = (uint8_t)(w->LevelEndStep + 1u);
            return;
        }
        w->shadow[0xC4] = (w->LevelEndFlashes & 1) ? 0x0C : 0x86;
        w->LevelEndDelay = 0x10;
        return;
    }
    if (s == 3) {
        init_board(w);
        w->LevelEndStep = (uint8_t)(w->LevelEndStep + 1u);
        return;
    }
    advance_level(w);
}
