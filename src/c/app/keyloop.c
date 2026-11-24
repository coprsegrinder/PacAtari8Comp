/* app/keyloop.c - the main program (stage 79d).  Twin of tools/core_app.py (_pass, _read, _released, key_loop): read the two side by side. */
#include "keyloop.h"

#include <string.h>

#include "../core/tables.h"
#include "dispatch.h"

#define COLORS_DLI 0xBBEE          /* ColorsDli: 4 bytes */

void keyloop_init(KeyLoop *kl)
{
    kl->pc = KL_TOP;
    kl->acc = 0;
    kl->clock = 0;
}

uint32_t keyloop_state(const KeyLoop *kl)
{
    uint32_t s = (uint32_t)kl->pc;
    if (kl->pc == KL_DEBOUNCE || kl->pc == KL_RELEASE) {
        s |= (uint32_t)kl->acc << 8;
    }
    if (kl->pc == KL_CLOCK_WAIT) {
        s |= (uint32_t)kl->clock << 16;
    }
    return s;
}

static void colours(World *w)
{
    int x;
    for (x = 3; x >= 0; x--) {
        w->DliColors[x] = (uint8_t)((table_rom((uint16_t)(COLORS_DLI + x)) ^ w->COLRSH) & w->DRKMSK);
    }
}

/* $A550: GameState 3 (the title menu), ATRACT 3 */
static void set_title(World *w, KeyLoop *kl)
{
    w->GameState = 3;
    w->ATRACT = 3;
    kl->pc = KL_TOP;
}

/* one pass from `$A4BA` to the next branch point; sets kl->pc */
static void pass_once(World *w, KeyLoop *kl)
{
    colours(w);
    if (w->GameState == 0) {
        if (w->shadow[0xF1] == 0 && w->shadow[0xFC] == 0x21) {          /* KEYDEL clear and the space bar: pause or resume */
            w->Paused = w->Paused ? 0 : 1;
            w->shadow[0xFC] = 0xFF;
        }
        if (w->CountdownActive == 0) {
            kl->pc = KL_READ;
            return;
        }
        if (w->CountdownTimer == 0) {                                   /* the game-over countdown is over: back to the title */
            w->GameState = 4;
            w->ATRACT = 4;
            kl->pc = KL_TOP;
            return;
        }
    }
    w->shadow[0xFC] = 0xFF;                                             /* $A4F5: CH cleared, the triggers start a game */
    if (w->shadow[0x84] == 0 || w->shadow[0x85] == 0) {
        new_game(w, kl);
        return;
    }
    kl->pc = KL_READ;
}

/* $A504: the console; a key starts the debounce */
static void read_console(World *w, KeyLoop *kl, uint8_t console)
{
    if (console == KL_CONSOL_NONE) {
        kl->pc = KL_TOP;
        return;
    }
    w->KeyValue = console;
    w->KeyDebounce = 1;
    kl->acc = console;                                                  /* `ora CONSOL` once before the first look at the counter */
    kl->pc = KL_DEBOUNCE;
}

/* $A521: the key has been released: what it meant */
static void released(World *w, KeyLoop *kl)
{
    uint8_t k = w->KeyValue;
    if (k == KL_CONSOL_START) {
        new_game(w, kl);
        return;
    }
    if (w->GameState < 3) {                                             /* the copyright screen, and a game in progress: any key leaves it for the title */
        set_title(w, kl);
        return;
    }
    if (k == KL_CONSOL_OPTION) {                                        /* the start level: 0 -> 1 -> 2 -> 4 -> 6 -> 8 -> 10 -> 12 -> 0 */
        if (w->StartLevel < 2) {
            w->StartLevel = (uint8_t)(w->StartLevel + 1u);
        } else if (w->StartLevel == 0x0C) {
            w->StartLevel = 0;
        } else {
            w->StartLevel = (uint8_t)(w->StartLevel + 2u);
        }
        set_title(w, kl);
        return;
    }
    if (k == KL_CONSOL_SELECT) {                                        /* one or two players */
        w->TwoPlayers = w->TwoPlayers ? 0 : 1;
        set_title(w, kl);
        return;
    }
    kl->pc = KL_TOP;
}

/* what a pass of the main program can change: the colours, the flags and the shadow byte it writes, and where the program is */
typedef struct Signature {
    uint8_t dli[4], paused, game_state, atract, start_level, two_players, countdown_active, intro_request, key_value, key_debounce, ch;
    uint32_t place;
} Signature;

static void signature(const World *w, const KeyLoop *kl, Signature *s)
{
    memset(s, 0, sizeof *s);
    memcpy(s->dli, w->DliColors, 4);
    s->paused = w->Paused;
    s->game_state = w->GameState;
    s->atract = w->ATRACT;
    s->start_level = w->StartLevel;
    s->two_players = w->TwoPlayers;
    s->countdown_active = w->CountdownActive;
    s->intro_request = w->IntroRequest;
    s->key_value = w->KeyValue;
    s->key_debounce = w->KeyDebounce;
    s->ch = w->shadow[0xFC];
    s->place = keyloop_state(kl);
}

int key_loop(World *w, KeyLoop *kl, uint8_t console)
{
    Signature last, cur;
    int have_last = 0, n;

    memset(&last, 0, sizeof last);
    for (n = 0; n < 400; n++) {
        if (kl->pc == KL_CLOCK_WAIT) {
            if (w->RTCLOK2 == kl->clock) {
                return 0;
            }
            restart_tail(w);
            kl->pc = KL_TOP;
        } else if (kl->pc == KL_DEBOUNCE) {
            kl->acc = (uint8_t)(kl->acc | console);
            if (w->KeyDebounce != 0) {
                return 0;
            }
            kl->pc = kl->acc != w->KeyValue ? KL_READ : KL_RELEASE;
        } else if (kl->pc == KL_RELEASE) {
            if (console == kl->acc) {
                return 0;
            }
            released(w, kl);
        } else if (kl->pc == KL_READ) {
            read_console(w, kl, console);
        } else {
            signature(w, kl, &cur);
            if (have_last && memcmp(&cur, &last, sizeof cur) == 0) {
                return 0;                                               /* a pass that changed nothing: every further pass is the same */
            }
            last = cur;
            have_last = 1;
            pass_once(w, kl);
        }
    }
    return 1;
}
