/* app/run_frame.c - one frame of the running game on a platform (stage 77b). */
#include "run_frame.h"

#include "../core/play.h"
#include "../core/random_feed.h"

void read_inputs(World *w, const Platform *p)
{
    uint8_t drkmsk, colrsh;

    w->stick[0] = (uint8_t)(p->stick(p->ctx, 0) & 0xFFu);
    w->stick[1] = (uint8_t)(p->stick(p->ctx, 1) & 0xFFu);
    w->stick[2] = 0x0F;
    w->stick[3] = 0x0F;
    p->collisions(p->ctx, w, w->collide);
    w->RTCLOK2 = p->clock(p->ctx);
    p->attract(p->ctx, &drkmsk, &colrsh);
    w->DRKMSK = drkmsk;
    w->COLRSH = colrsh;
}

uint32_t run_frame(World *w, Platform *p)
{
    RandomFeed feed;

    read_inputs(w, p);
    w->pokey_n = 0;
    w->pokey_overflow = 0;
    random_feed_from(&feed, p->random, p->ctx);
    vbi_play_frame(w, &feed);
    if (p->frame_done != NULL) {
        p->frame_done(p->ctx, w);
    }
    return feed.used;
}
