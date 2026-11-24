/* audio/audio.c - see audio.h. */
#include "audio.h"

#include <math.h>
#include <string.h>

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

unsigned audio_world_writes(const World *w, uint8_t reg[WRITE_CLOCK_MAX], uint8_t val[WRITE_CLOCK_MAX])
{
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
    return n;
}

size_t audio_frame(Audio *a, World *w, float *out, size_t cap)
{
    uint8_t reg[WRITE_CLOCK_MAX], val[WRITE_CLOCK_MAX];
    unsigned n = audio_world_writes(w, reg, val);

    w->pokey_n = 0;
    w->pokey_overflow = 0;
    return audio_frame_writes(a, reg, val, n, out, cap);
}

static double bessel_i0(double x)
{
    double sum = 1.0, term = 1.0;
    int k;

    for (k = 1; k < 60; k++) {
        term *= (x / (2.0 * (double)k)) * (x / (2.0 * (double)k));
        sum += term;
    }
    return sum;
}

void audio_hq_init(AudioHq *h, double out_rate)
{
    const double pi = 3.14159265358979323846, beta = 7.0;
    const int m = AUDIO_HQ_TAPS - 1;
    double fc = 20000.0 / (out_rate * (double)AUDIO_HQ_OVER), sum = 0.0;
    int i;

    memset(h, 0, sizeof *h);
    audio_init(&h->audio, out_rate * (double)AUDIO_HQ_OVER);
    for (i = 0; i < AUDIO_HQ_TAPS; i++) {
        double t = (double)(i - m / 2), r = 2.0 * (double)i / (double)m - 1.0;
        double s = t == 0.0 ? 2.0 * fc : sin(2.0 * pi * fc * t) / (pi * t);
        double w = bessel_i0(beta * sqrt(1.0 - r * r)) / bessel_i0(beta);
        h->coef[i] = (float)(s * w);
        sum += s * w;
    }
    for (i = 0; i < AUDIO_HQ_TAPS; i++) {
        h->coef[i] = (float)((double)h->coef[i] / sum);
    }
}

size_t audio_hq_frame(AudioHq *h, const uint8_t *reg, const uint8_t *val, unsigned n, float *out, size_t cap)
{
    size_t got = audio_frame_writes(&h->audio, reg, val, n, h->hist + h->n, AUDIO_HQ_MAX), pos = 0, made = 0;
    size_t total = h->n + got;

    while (total - pos >= AUDIO_HQ_TAPS && made < cap) {
        const float *x = h->hist + pos;
        double acc = 0.0;
        int i;
        for (i = 0; i < AUDIO_HQ_TAPS; i++) {
            acc += (double)h->coef[i] * (double)x[i];
        }
        out[made++] = (float)acc;
        pos += AUDIO_HQ_OVER;
    }
    memmove(h->hist, h->hist + pos, (total - pos) * sizeof h->hist[0]);
    h->n = total - pos;
    return made;
}
