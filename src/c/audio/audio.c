/* audio/audio.c - see audio.h. */
#include "audio.h"

void audio_init(Audio *a, double sample_rate)
{
    pokey_init(&a->pokey, 0, POKEY_NOISE_T0, POKEY_PHASE, sample_rate);
    pokey_set_origin(&a->pokey, 0.0);
    a->frame = 0;
}

void audio_set_origin(Audio *a, double cycle)
{
    pokey_set_origin(&a->pokey, cycle);
}

size_t audio_frame_writes(Audio *a, const uint8_t *reg, const uint8_t *val, unsigned n, float *out, size_t cap)
{
    int32_t cycle[WRITE_CLOCK_MAX];
    int64_t base = a->frame * AUDIO_FRAME_CYCLES;
    unsigned i;

    if (n > WRITE_CLOCK_MAX) {
        n = WRITE_CLOCK_MAX;                                /* a frame of the game has at most 16 writes (the longest measured one has 16) */
    }
    write_clock_stamp(n, cycle);
    for (i = 0; i < n; i++) {
        pokey_write(&a->pokey, base + cycle[i], reg[i], val[i]);
    }
    pokey_run(&a->pokey, base + AUDIO_FRAME_CYCLES - AUDIO_LAG_CYCLES);
    a->frame++;
    return pokey_take(&a->pokey, out, cap);
}

size_t audio_frame(Audio *a, World *w, float *out, size_t cap)
{
    uint8_t reg[WRITE_CLOCK_MAX], val[WRITE_CLOCK_MAX];
    unsigned n = 0;
    uint32_t i;

    for (i = 0; i < w->pokey_n; i++) {
        uint16_t addr = w->pokey_addr[i];
        if (addr >= 0xD200u && addr <= 0xD208u && n < WRITE_CLOCK_MAX) {
            reg[n] = (uint8_t)(addr - 0xD200u);
            val[n] = w->pokey_val[i];
            n++;
        }
    }
    w->pokey_n = 0;
    w->pokey_overflow = 0;
    return audio_frame_writes(a, reg, val, n, out, cap);
}
