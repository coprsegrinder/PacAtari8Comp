/* app/start.c - the power-on state and Start (stage 79d).  Twin of tools/core_app.py (power_on_world, start). */
#include "keyloop.h"

#include <string.h>

#include "../core/sound.h"
#include "../core/tables.h"
#include "init.h"

#define TEXT_HIGH_SCORE 0xBDC7     /* 10 bytes */

void power_on_world(World *w, uint8_t clock)
{
    world_init(w);
    w->POKMSK = 0xC0;
    w->RTCLOK2 = clock;
    w->DliColors[0] = 0x42;
    w->DliColors[1] = 0x9C;
    memset(w->stick, 0x0F, sizeof w->stick);
    w->shadow[0x84] = 1;                                     /* STRIG0 / STRIG1: not pressed */
    w->shadow[0x85] = 1;
    w->shadow[0xFC] = 0xFF;                                  /* CH: no key */
}

void start(World *w)
{
    int x;

    for (x = 9; x >= 0; x--) {
        w->status[0x0F + x] = table_rom((uint16_t)(TEXT_HIGH_SCORE + x));
    }
    clear_zp(w, 0x18, 0x40);
    clear_zp(w, 0x80, 0x100);
    w->GameState = (uint8_t)(w->GameState + 1u);
    w->CopyrightEnd = (uint8_t)(w->RTCLOK2 - 1u);
    memcpy(w->maze_orig, MAZE_DATA, MAZE_DATA_SIZE);
    memset(w->maze_orig + MAZE_DATA_SIZE, 0, sizeof w->maze_orig - MAZE_DATA_SIZE);   /* the tail $0B98-$0BFF is what the OS left: zeros */
    w->POKMSK = (uint8_t)(w->POKMSK | 0x40u);                /* the keyboard interrupt */
    sound_wr(w, 0xD20E, w->POKMSK);                          /* IRQEN: the keyboard interrupt on */
    sound_wr(w, 0xD20F, 7);                                  /* SKCTL */
    w->shadow[0x2F] = 0x3E;                                  /* SDMCTL */
    restart_clear(w);
}
