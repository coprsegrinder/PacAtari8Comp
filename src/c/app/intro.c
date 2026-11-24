/* app/intro.c - the labels and the READY! intro (stage 79b).  Twin of tools/core_app_board.py. */
#include "board.h"

#include "../core/draw.h"
#include "../core/score.h"

void draw_label_1up(World *w)
{
    w->status[4] = 0x11;
    w->status[5] = 0x35;
    w->status[6] = 0x30;
}

void draw_label_2up(World *w)
{
    w->status[0x21] = 0x12;
    w->status[0x22] = 0x35;
    w->status[0x23] = 0x30;
}

void blink_player_label(World *w)
{
    if (w->RTCLOK2 & 0x0F) {
        return;
    }
    w->LabelBlink = w->LabelBlink == 0 ? 1 : 0;
    if (w->CurrentPlayer == 0) {
        if (w->LabelBlink) {
            draw_label_1up(w);
        } else {
            w->status[4] = 0;
            w->status[5] = 0;
            w->status[6] = 0;
        }
    } else {
        if (w->LabelBlink) {
            draw_label_2up(w);
        } else {
            w->status[0x21] = 0;
            w->status[0x22] = 0;
            w->status[0x23] = 0;
        }
    }
}

void clear_ready_text(World *w)
{
    int x;
    for (x = 0x0D; x >= 0; x--) {
        w->maze[0x1ED + x] = 0;
    }
}

void draw_ready_screen(World *w)
{
    draw_all_in_place(w);
    w->Lives[w->CurrentPlayer] = (uint8_t)(w->Lives[w->CurrentPlayer] - 1u);
    draw_lives(w);
}
