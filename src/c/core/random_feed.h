/* core/random_feed.h - the RANDOM values handed to a core function (docs/45: RANDOM is one of the 14 inputs).
 * Two kinds of feed, one interface: a recorded list of values (the vector runner: the values the original read), or a pull function (the platform's RANDOM source).
 * `used` counts the values asked for (the ROM's read count is compared with it); asking for more than a list holds returns 0 and counts an overrun, which is a difference in the vector runner. */
#ifndef PM_CORE_RANDOM_FEED_H
#define PM_CORE_RANDOM_FEED_H

#include <stdint.h>

/* the RANDOM values a core function reads: a recorded list or a pull function, with the number used and the overrun */
typedef struct RandomFeed {
    const uint8_t *values;
    uint32_t count;     /* values supplied (list feed) */
    uint32_t used;      /* values asked for */
    uint32_t overrun;   /* values asked for beyond `count` (list feed) */
    uint8_t (*pull)(void *ctx);   /* a pull feed: every request calls this (NULL for a list feed) */
    void *ctx;
} RandomFeed;

static inline void random_feed_init(RandomFeed *r, const uint8_t *values, uint32_t count)
{
    r->values = values;
    r->count = count;
    r->used = 0;
    r->overrun = 0;
    r->pull = 0;
    r->ctx = 0;
}

static inline void random_feed_from(RandomFeed *r, uint8_t (*pull)(void *ctx), void *ctx)
{
    r->values = 0;
    r->count = 0;
    r->used = 0;
    r->overrun = 0;
    r->pull = pull;
    r->ctx = ctx;
}

static inline uint8_t random_next(RandomFeed *r)
{
    uint32_t i = r->used++;
    if (r->pull) {
        return r->pull(r->ctx);
    }
    if (i < r->count) {
        return r->values[i];
    }
    r->overrun++;
    return 0;
}

#endif
