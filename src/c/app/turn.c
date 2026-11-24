/* app/turn.c - TurnControl (stage 79b).  Twin of tools/core_app_board.py turn_control: read the two side by side. */
#include "board.h"

#include <string.h>

#include "../core/play.h"
#include "../core/sound.h"
#include "init.h"
#include "../core/constants.h"

/* $AAEF: the GAME OVER text (the 14 cells from $AC), its colour; when no hand-over is in progress the high score is updated and the countdown starts */
static void game_over_text(World *w)
{
    int x;
    for (x = 0; x < 0x0E; x++) {
        w->maze[0x1ED + x] = (uint8_t)(0xAC + x);
    }
    w->shadow[0xC7] = 0x44;                                  /* COLOR3 */
    sound_wr(w, BOARD_COLPF3, 0x44);
    if (w->TurnSwitchState != 0) {
        return;
    }
    compare_high_score(w, 0x2A);
    compare_high_score(w, 0x47);
    w->WaitState = 0;
    w->CountdownActive = 1;
    w->CountdownTimer = COUNTDOWN_STEPS;
    draw_label_1up(w);
    show_power_pellets(w);
}

void turn_control(World *w)
{
    int p;

    show_power_pellets(w);
    if (w->TurnSwitchState != 0) {
        int st;
        if (w->WaitTimer != 0) {
            w->WaitTimer = (uint8_t)(w->WaitTimer - 1u);
            return;
        }
        st = w->TurnSwitchState;
        if (st == 1) {
            memcpy(w->maze, w->saved1, sizeof w->maze);
            draw_label_2up(w);
            w->CurrentPlayer = 0;
            w->TurnSwitchState = 3;
            return;
        }
        if (st == 2) {
            memcpy(w->maze, w->saved2, sizeof w->maze);
            draw_label_1up(w);
            w->CurrentPlayer = 1;
            w->TurnSwitchState = 3;
            return;
        }
        show_power_pellets(w);
        w->TurnSwitchState = 0;
    } else {
        if (w->TwoPlayers) {
            if (w->CurrentPlayer == 0) {
                if (w->Lives[1] != 0) {
                    if (w->Lives[0] == 0) {
                        w->TurnSwitchState = 2;
                        w->WaitTimer = WAIT_AFTER_DEATH;
                        game_over_text(w);
                        return;
                    }
                    copy_0c00_to_1000(w);
                    w->WaitTimer = WAIT_AFTER_DEATH;
                    w->TurnSwitchState = 2;
                    return;
                }
            } else {
                if (w->Lives[0] != 0) {
                    if (w->Lives[1] == 0) {
                        w->TurnSwitchState = 1;
                        w->WaitTimer = WAIT_AFTER_DEATH;
                        game_over_text(w);
                        return;
                    }
                    copy_0c00_to_1400(w);
                    w->WaitTimer = WAIT_AFTER_DEATH;
                    w->TurnSwitchState = 1;
                    return;
                }
            }
        }
    }
    p = w->CurrentPlayer;
    if (w->Lives[p] != 0) {
        init_board(w);
        draw_level_indicator(w);
        draw_ready_screen(w);
        return;
    }
    game_over_text(w);
}
