/* app/app.c - one frame of the whole program on a platform (stage 79d).  Twin of tools/core_app.py (read_inputs, App.frame). */
#include "keyloop.h"

#include "dispatch.h"

void app_read_inputs(World *w, const Platform *p)
{
    uint8_t k, drkmsk, colrsh;

    w->stick[0] = p->stick(p->ctx, 0);
    w->stick[1] = p->stick(p->ctx, 1);
    w->stick[2] = 0x0F;
    w->stick[3] = 0x0F;
    w->shadow[0x84] = p->trigger(p->ctx, 0);
    w->shadow[0x85] = p->trigger(p->ctx, 1);
    k = p->key(p->ctx);
    if (k != 0xFF) {
        w->shadow[0xFC] = k;                                 /* a key press is stored by the OS in CH */
    }
    w->shadow[0xF1] = p->key_delay(p->ctx);
    p->collisions(p->ctx, w, w->collide);
    w->RTCLOK2 = p->clock(p->ctx);
    p->attract(p->ctx, &drkmsk, &colrsh);
    w->DRKMSK = drkmsk;
    w->COLRSH = colrsh;
}

uint32_t app_frame(World *w, KeyLoop *kl, Platform *p)
{
    RandomFeed feed;

    app_read_inputs(w, p);
    w->pokey_n = 0;
    w->pokey_overflow = 0;
    random_feed_from(&feed, p->random, p->ctx);
    vbi_handler(w, &feed);
    (void)key_loop(w, kl, p->console(p->ctx));
    if (p->frame_done != NULL) {
        p->frame_done(p->ctx, w);
    }
    return feed.used;
}
