/* app/dispatch.c - the frame dispatcher (stage 79c).  Twin of tools/core_app_frame.py: read the two side by side. */
#include "dispatch.h"

#include "../core/draw.h"
#include "../core/play.h"
#include "../core/sound.h"
#include "../core/tables.h"
#include "board.h"
#include "../core/constants.h"

#define COLORS_TITLE 0xBBEA          /* ColorsTitle: 4 bytes, COLOR0-3 of the title */
#define TEXT_COPYRIGHT 0xBDF7        /* 14 bytes */
#define TEXT_PLAYER_GAME 0xBFC6      /* 11 bytes */
#define TEXT_PRESS_SELECT_FOR 0xBFD1 /* 16 bytes */
#define TEXT_PRESS_OPTION_TO 0xBFE1  /* 16 bytes */
#define TEXT_PRESS_START_TO 0xBDE7   /* 16 bytes */
#define TEXT_CHANGE_DIFFICULTY 0xBDD6 /* 17 bytes */
#define TEXT_PLAY_GAME 0xBFF1        /* 9 bytes */
#define LEVEL_ICON_CODES 0xBE05

/* ------------------------------------------------------------------------------------------------ the display and the title scores */
void init_display2(World *w)
{
    int x, y;
    for (x = 7; x >= 0; x--) {
        w->hpos[x] = 0;
        sound_wr(w, (uint16_t)(0xD200 + x), 0);
    }
    w->shadow[0x30] = 0x81;                          /* SDLSTL */
    w->shadow[0x31] = 0xBF;                          /* SDLSTH */
    w->shadow[0x00] = 0xCE;                          /* VDSLST */
    w->shadow[0x01] = 0xA5;
    for (y = 3; y >= 0; y--) {
        w->shadow[0xC4 + y] = table_rom((uint16_t)(COLORS_TITLE + y));
    }
    w->DstPtr[1] = 0xA5;                             /* the tail copies 16 bytes INTO THE ROM (nothing happens): only the pointer's high byte is left */
}

static void clear_scores_tail(World *w)
{
    draw_label_1up(w);
    w->status[SCORE_CELLS_P1 - 1] = SCORE_DIGIT_BASE;
    w->status[SCORE_CELLS_P1] = SCORE_DIGIT_BASE;
}

void title_clear_scores_1p(World *w)
{
    int x;
    for (x = 6; x >= 0; x--) {
        w->status[0x20 + x] = 0;
        w->status[0x47 + x] = 0;
        w->status[0x2A + x] = 0;
    }
    clear_scores_tail(w);
}

void title_clear_scores_2p(World *w)
{
    int x;
    for (x = 6; x >= 0; x--) {
        w->status[0x2A + x] = 0;
        w->status[0x47 + x] = 0;
    }
    draw_label_2up(w);
    w->status[SCORE_CELLS_P2 - 1] = SCORE_DIGIT_BASE;
    w->status[SCORE_CELLS_P2] = SCORE_DIGIT_BASE;
    clear_scores_tail(w);
}

/* ------------------------------------------------------------------------------------------------ the copyright screens and the title menu */
void copyright_setup(World *w)
{
    int x;
    init_display2(w);
    for (x = 0; x < 256; x++) {
        w->title[x] = 0;
        w->title[0x100 + x] = 0;
        w->maze[0x300 + x] = 0;
    }
    w->shadow[0xC5] = 0;
    for (x = 13; x >= 0; x--) {
        w->title[0x157 + x] = table_rom((uint16_t)(TEXT_COPYRIGHT + x));
    }
    for (x = 0; x < 12; x++) {
        w->title[0x18 + x] = (uint8_t)(x + 0xC1);
        w->title[0x2C + x] = (uint8_t)(x + 0xCD);
    }
    w->GameState = (uint8_t)(w->GameState + 1u);
}

void copyright_wait(World *w)
{
    if (w->CopyrightEnd == w->RTCLOK2) {
        w->GameState = (uint8_t)(w->GameState + 1u);
    }
}

void title_menu(World *w)
{
    int gs = w->GameState, x;
    uint8_t a, c;

    w->title[0x54] = (uint8_t)(((w->TwoPlayers + 1u) & 0xFFu) | 0x50u);
    if (w->TwoPlayers == 0) {
        if (gs == 3) {
            title_clear_scores_1p(w);
        }
        a = 0x12;
    } else {
        if (gs == 3) {
            title_clear_scores_2p(w);
        }
        a = 0x11;
    }
    w->title[0x90] = a;
    for (x = 0x0A; x >= 0; x--) {
        c = table_rom((uint16_t)(TEXT_PLAYER_GAME + x));
        w->title[0x92 + x] = c;
        w->title[0x56 + x] = (uint8_t)(c | 0x40u);
    }
    init_display2(w);
    for (x = 0x0F; x >= 0; x--) {
        w->title[0x7A + x] = table_rom((uint16_t)(TEXT_PRESS_SELECT_FOR + x));
        w->title[0xF2 + x] = table_rom((uint16_t)(TEXT_PRESS_OPTION_TO + x));
        w->title[0x156 + x] = table_rom((uint16_t)(TEXT_PRESS_START_TO + x));
    }
    a = table_rom((uint16_t)(LEVEL_ICON_CODES + w->StartLevel));
    w->title[0xC6] = a;
    w->title[0xC7] = (uint8_t)(a + 1u);
    for (x = 0x10; x >= 0; x--) {
        w->title[0x105 + x] = table_rom((uint16_t)(TEXT_CHANGE_DIFFICULTY + x));
    }
    for (x = 8; x >= 0; x--) {
        w->title[0x16D + x] = table_rom((uint16_t)(TEXT_PLAY_GAME + x));
    }
}

/* ------------------------------------------------------------------------------------------------ the game */
/* $A805: the WaitState dispatch (the READY! wait ends into the frame of play in the same frame) */
static void wait_state(World *w, RandomFeed *rnd)
{
    for (;;) {
        if (w->WaitState == 0) {
            play_frame(w, rnd);
            return;
        }
        if (w->WaitState == 1) {
            turn_control(w);
            if (w->TurnSwitchState != 0) {
                return;
            }
            if (w->CountdownActive != 0) {
                return;
            }
            w->WaitState = (uint8_t)(w->WaitState + 1u);
            w->WaitTimer = 0x40;
            return;
        }
        if (w->WaitTimer != 0) {
            w->WaitTimer = (uint8_t)(w->WaitTimer - 1u);
            return;
        }
        w->WaitState = 0;
        w->GhostState[0] = (uint8_t)(w->GhostState[0] + 1u);              /* LA800: ghost 0 leaves its start state */
        clear_ready_text(w);
    }
}

void game_frame(World *w, RandomFeed *rnd)
{
    if (w->CountdownTimer != 0 && (w->RTCLOK2 & 7) == 0) {
        w->CountdownTimer = (uint8_t)(w->CountdownTimer - 1u);
    }
    if (w->Paused) {
        clear_pokey(w);
        return;
    }
    blink_player_label(w);
    if (w->IntroRequest == 2) {                                           /* board start */
        w->StartTuneActive = (uint8_t)(w->StartTuneActive + 1u);
        w->ATRACT = 0;
        w->IntroRequest = 0;
        draw_level_indicator(w);
        return;
    }
    if (w->CountdownActive) {                                             /* the game-over countdown: the labels */
        if (w->TwoPlayers) {
            draw_label_2up(w);
        }
        draw_label_1up(w);
        return;
    }
    if (w->LevelComplete) {
        level_end_step(w);
        return;
    }
    if (w->PlayStarted == 0) {
        if (w->StartTuneActive == 0) {
            return;
        }
        if (start_tune_step(w) != 3) {                                    /* 3 = play */
            return;
        }
        clear_ready_text(w);
    }
    wait_state(w, rnd);
}

void frame_dispatch(World *w, RandomFeed *rnd)
{
    switch (w->GameState) {
    case 0:
        game_frame(w, rnd);
        break;
    case 1:
        copyright_setup(w);
        break;
    case 2:
        copyright_wait(w);
        break;
    default:
        title_menu(w);
        break;
    }
}

void vbi_handler(World *w, RandomFeed *rnd)
{
    w->BandCounter = 0;
    w->KeyDebounce = (uint8_t)(w->KeyDebounce - 1u);
    frame_dispatch(w, rnd);
    if (w->EatPause == 0) {
        clip_entities_on_tunnel_row(w);
    }
}
