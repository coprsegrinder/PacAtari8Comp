/* app/newgame.c - the restart and the new game (stage 79d).  Twin of tools/core_app.py (_restart_clear, _restart_tail, _new_game). */
#include "keyloop.h"

#include "../core/sound.h"
#include "dispatch.h"
#include "init.h"
#include "../core/constants.h"

void restart_clear(World *w)
{
    clear_zp(w, 0x20, 0x40);
    clear_pokey(w);
    copy_0800_to_0c00(w);
    copy_0c00_to_1000(w);
    copy_0c00_to_1400(w);
}

void restart_tail(World *w)
{
    w->shadow[0x30] = 0xA3;                                  /* SetDisplayList(x = $A3, y = $73) */
    w->shadow[0x31] = 0xBF;
    w->shadow[0x00] = 0x73;
    w->shadow[0x01] = 0xA5;
    w->shadow[0x6F] = PRIORITY_NORMAL;                                  /* GPRIOR */
    init_board(w);
    new_game_init(w);
    if (w->TwoPlayers) {
        title_clear_scores_2p(w);
    } else {
        title_clear_scores_1p(w);
    }
    w->IntroRequest = 2;
}

void new_game(World *w, KeyLoop *kl)
{
    w->CountdownActive = 0;
    w->GameState = 0;
    w->IntroRequest = 1;
    restart_clear(w);
    kl->clock = w->RTCLOK2;                                  /* the wait for the next tick of the OS clock (`$A491-$A495`) */
    kl->pc = KL_CLOCK_WAIT;
}
