/* app/board.c - the level indicator and the high score (stage 79b).  Twin of tools/core_app_board.py. */
#include "board.h"

#include "../core/tables.h"

#define BONUS_ITEM_CODES 0xBD26      /* BonusItemCodes: 13 bytes, the first glyph of each level's bonus item */

void draw_level_indicator(World *w)
{
    int a = 0xA2, x, y, lv, src, ptr;
    uint8_t c;

    for (x = 0; x < 10; x++) {
        w->maze[0x1EF + x] = (uint8_t)a;
        a = (a + 1) & 0xFF;
    }
    lv = w->Level[w->CurrentPlayer];
    w->ItemColor = (lv >= 6 && lv < 10) ? 0xDA : 0x44;
    if (lv < 6) {
        w->Scratch2A = (uint8_t)lv;
        w->DstPtr[0] = 0x92;
        w->DstPtr[1] = 0x0F;
        x = 0;
        for (;;) {
            c = table_rom((uint16_t)(BONUS_ITEM_CODES + x));
            ptr = w->DstPtr[0] | (w->DstPtr[1] << 8);
            w->maze[ptr - 0x0C00] = c;
            w->DstPtr[0] = (uint8_t)(w->DstPtr[0] + 1u);
            ptr = w->DstPtr[0] | (w->DstPtr[1] << 8);
            w->maze[ptr - 0x0C00] = (uint8_t)(c + 1u);
            if (x == w->Scratch2A) {
                return;
            }
            x++;
            w->DstPtr[0] = (uint8_t)(w->DstPtr[0] - 3u);
        }
    }
    a = (lv < 0x12 ? lv : 0x12) - 6;
    w->Scratch2A = (uint8_t)a;
    src = 0xBD3E - a;
    w->SrcPtr[0] = (uint8_t)(src & 0xFF);
    w->SrcPtr[1] = (uint8_t)(src >> 8);
    x = 0;
    for (y = 0; y < 7; y++) {
        c = table_rom((uint16_t)(src + y));
        w->maze[0x386 + x] = c;
        w->maze[0x387 + x] = (uint8_t)(c + 1u);
        x += 2;
    }
}

void compare_high_score(World *w, int x)
{
    int y, k;
    for (y = 0; y < 6; y++) {
        uint8_t a = w->status[x + y], b = w->status[0x39 + y];
        if (a == b) {
            continue;
        }
        if (a < b) {
            return;
        }
        for (k = y; k < 6; k++) {
            w->status[0x39 + k] = w->status[x + k];
        }
        return;
    }
}
