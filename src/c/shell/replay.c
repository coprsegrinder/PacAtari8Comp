/* shell/replay.c - see replay.h. */
#include "replay.h"

#include <string.h>

#include "../platform/fs.h"

static uint32_t rd16(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8);
}

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint32_t fnv1a(const uint8_t *p, size_t n)
{
    uint32_t h = 0x811C9DC5u;
    size_t i;

    for (i = 0; i < n; i++) {
        h = (h ^ p[i]) * 0x01000193u;
    }
    return h;
}

const char *replay_error_text(ReplayError e)
{
    switch (e) {
    case REPLAY_OK: return "ok";
    case REPLAY_TOO_SHORT: return "the replay is too short";
    case REPLAY_BAD_MAGIC: return "not a replay (bad magic)";
    case REPLAY_BAD_VERSION: return "unknown replay version";
    case REPLAY_BAD_FLAGS: return "unknown replay flags";
    case REPLAY_BAD_COUNT: return "the number of frames is not possible";
    case REPLAY_BAD_FRAME: return "a frame is malformed or bytes are left over";
    case REPLAY_BAD_CHECKSUM: return "bad checksum";
    case REPLAY_OPEN_FAILED: return "the file cannot be opened";
    case REPLAY_TOO_BIG: return "the file does not fit the buffer";
    case REPLAY_WRITE_FAILED: return "the replay cannot be written";
    case REPLAY_FULL: return "the replay buffer is full";
    }
    return "unknown error";
}

ReplayError replay_parse(Replay *r, const uint8_t *buf, size_t size)
{
    size_t pos, end;
    uint32_t n;

    memset(r, 0, sizeof *r);
    if (size < REPLAY_HEADER + 4u) {
        return REPLAY_TOO_SHORT;
    }
    if (memcmp(buf, "PMRP", 4) != 0) {
        return REPLAY_BAD_MAGIC;
    }
    if (rd16(buf + 4) != REPLAY_VERSION) {
        return REPLAY_BAD_VERSION;
    }
    r->flags = (uint16_t)rd16(buf + 6);
    if (r->flags & ~REPLAY_FLAG_RANDOM) {
        return REPLAY_BAD_FLAGS;
    }
    r->seed = rd32(buf + 8);
    r->nframes = rd32(buf + 12);
    r->start_clock = buf[16];
    if (r->nframes > REPLAY_MAX_FRAMES) {
        return REPLAY_BAD_COUNT;
    }
    end = size - 4u;
    if (fnv1a(buf, end) != rd32(buf + end)) {
        return REPLAY_BAD_CHECKSUM;
    }
    pos = REPLAY_HEADER;
    for (n = 0; n < r->nframes; n++) {
        if (end - pos < REPLAY_FRAME_BASE) {
            return REPLAY_BAD_FRAME;
        }
        pos += REPLAY_FRAME_BASE;
        if (r->flags & REPLAY_FLAG_RANDOM) {
            size_t k;
            if (end - pos < 2u) {
                return REPLAY_BAD_FRAME;
            }
            k = rd16(buf + pos);
            pos += 2u;
            if (end - pos < k) {
                return REPLAY_BAD_FRAME;
            }
            pos += k;
        }
    }
    if (pos != end) {
        return REPLAY_BAD_FRAME;
    }
    r->data = buf + REPLAY_HEADER;
    r->size = end - REPLAY_HEADER;
    r->pos = 0;
    r->next = 0;
    return REPLAY_OK;
}

ReplayError replay_load(Replay *r, const char *path, uint8_t *buf, size_t cap)
{
    PmFile *f = pm_fs_open(path, "rb");
    size_t got = 0, n;

    memset(r, 0, sizeof *r);
    if (f == NULL) {
        return REPLAY_OPEN_FAILED;
    }
    for (;;) {
        if (got == cap) {
            uint8_t extra;
            n = pm_fs_read(f, &extra, 1);
            pm_fs_close(f);
            return n == 0 ? replay_parse(r, buf, got) : REPLAY_TOO_BIG;
        }
        n = pm_fs_read(f, buf + got, cap - got);
        if (n == 0) {
            break;
        }
        got += n;
    }
    pm_fs_close(f);
    return replay_parse(r, buf, got);
}

int replay_next(Replay *r, FrameInput *f)
{
    const uint8_t *p;

    if (r->next >= r->nframes) {
        return 0;
    }
    p = r->data + r->pos;
    f->stick0 = p[0];
    f->stick1 = p[1];
    f->trig0 = p[2];
    f->trig1 = p[3];
    f->console = p[4];
    f->key = p[5];
    f->keydelay = p[6];
    f->clock = p[7];
    f->drkmsk = p[8];
    f->colrsh = p[9];
    r->pos += REPLAY_FRAME_BASE;
    if (r->flags & REPLAY_FLAG_RANDOM) {
        f->nrandom = (uint16_t)rd16(r->data + r->pos);
        f->random = r->data + r->pos + 2u;
        r->pos += 2u + f->nrandom;
    } else {
        f->nrandom = 0;
        f->random = NULL;
    }
    r->next++;
    return 1;
}

void replay_rewind(Replay *r)
{
    r->pos = 0;
    r->next = 0;
}

/* ---- writing ---- */

static void put(ReplayWriter *w, unsigned v)
{
    if (w->len >= w->cap) {
        w->over = 1;
        return;
    }
    w->buf[w->len++] = (uint8_t)v;
}

static void put16(ReplayWriter *w, unsigned v)
{
    put(w, v & 0xFFu);
    put(w, (v >> 8) & 0xFFu);
}

static void put32(ReplayWriter *w, uint32_t v)
{
    put16(w, (unsigned)(v & 0xFFFFu));
    put16(w, (unsigned)(v >> 16));
}

void replay_writer_init(ReplayWriter *w, uint8_t *buf, size_t cap, uint32_t seed, uint16_t flags, uint8_t start_clock)
{
    w->buf = buf;
    w->cap = cap;
    w->len = 0;
    w->flags = flags;
    w->seed = seed;
    w->nframes = 0;
    w->start_clock = start_clock;
    w->over = 0;
    put(w, 0x50u);                                         /* "PMRP" */
    put(w, 0x4Du);
    put(w, 0x52u);
    put(w, 0x50u);
    put16(w, REPLAY_VERSION);
    put16(w, flags);
    put32(w, seed);
    put32(w, 0);                                           /* the number of frames: filled in by replay_writer_finish */
    put(w, start_clock);
    put(w, 0);
    put(w, 0);
    put(w, 0);
}

ReplayError replay_writer_add(ReplayWriter *w, const FrameInput *f)
{
    put(w, f->stick0);
    put(w, f->stick1);
    put(w, f->trig0);
    put(w, f->trig1);
    put(w, f->console);
    put(w, f->key);
    put(w, f->keydelay);
    put(w, f->clock);
    put(w, f->drkmsk);
    put(w, f->colrsh);
    if (w->flags & REPLAY_FLAG_RANDOM) {
        unsigned i;
        put16(w, f->nrandom);
        for (i = 0; i < f->nrandom; i++) {
            put(w, f->random != NULL ? f->random[i] : 0u);
        }
    }
    w->nframes++;
    return w->over ? REPLAY_FULL : REPLAY_OK;
}

ReplayError replay_writer_finish(ReplayWriter *w, size_t *size)
{
    uint32_t sum;

    if (w->over || w->len + 4u > w->cap) {
        return REPLAY_FULL;
    }
    w->buf[12] = (uint8_t)(w->nframes & 0xFFu);
    w->buf[13] = (uint8_t)((w->nframes >> 8) & 0xFFu);
    w->buf[14] = (uint8_t)((w->nframes >> 16) & 0xFFu);
    w->buf[15] = (uint8_t)((w->nframes >> 24) & 0xFFu);
    sum = fnv1a(w->buf, w->len);
    put32(w, sum);
    *size = w->len;
    return REPLAY_OK;
}

ReplayError replay_save(const char *path, const uint8_t *buf, size_t size)
{
    PmFile *f = pm_fs_open(path, "wb");

    if (f == NULL) {
        return REPLAY_WRITE_FAILED;
    }
    if (pm_fs_write(f, buf, size) != size) {
        pm_fs_close(f);
        return REPLAY_WRITE_FAILED;
    }
    return pm_fs_close(f) == 0 ? REPLAY_OK : REPLAY_WRITE_FAILED;
}
