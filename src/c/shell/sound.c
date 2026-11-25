/* shell/sound.c - master volume, mute and the output filter of the speaker's sound (docs/72); see sound.h. */
#include <math.h>
#include <string.h>

#include "sound.h"

static void biquad_lowpass(SoundBiquad *q, double rate, double fc)
{
    const double pi = 3.14159265358979323846, w = 2.0 * pi * fc / rate, c = cos(w), al = sin(w) / (2.0 * 0.70710678118654752), a0 = 1.0 + al;

    q->b0 = (1.0 - c) / 2.0 / a0;
    q->b1 = (1.0 - c) / a0;
    q->b2 = (1.0 - c) / 2.0 / a0;
    q->a1 = -2.0 * c / a0;
    q->a2 = (1.0 - al) / a0;
    q->z1 = q->z2 = 0.0;
}

static void biquad_highpass(SoundBiquad *q, double rate, double fc)
{
    const double pi = 3.14159265358979323846, w = 2.0 * pi * fc / rate, c = cos(w), al = sin(w) / (2.0 * 0.70710678118654752), a0 = 1.0 + al;

    q->b0 = (1.0 + c) / 2.0 / a0;
    q->b1 = -(1.0 + c) / a0;
    q->b2 = (1.0 + c) / 2.0 / a0;
    q->a1 = -2.0 * c / a0;
    q->a2 = (1.0 - al) / a0;
    q->z1 = q->z2 = 0.0;
}

static double biquad_run(SoundBiquad *q, double x)
{
    double y = q->b0 * x + q->z1;

    q->z1 = q->b1 * x - q->a1 * y + q->z2;
    q->z2 = q->b2 * x - q->a2 * y;
    return y;
}

void sound_init(SoundFx *s, double rate)
{
    memset(s, 0, sizeof *s);
    s->volume = SOUND_VOLUME_STEPS;
    s->filter = SF_SOFT;
    s->gain = 1.0f;
    s->rate = rate;
    s->chime_pos = -1;
    biquad_lowpass(&s->lp, rate, 5000.0);
    biquad_highpass(&s->hp, rate, 140.0);
}

float sound_gain_of(int volume, int mute)
{
    double f;

    if (mute || volume <= 0) {
        return 0.0f;
    }
    if (volume > SOUND_VOLUME_STEPS) {
        volume = SOUND_VOLUME_STEPS;
    }
    f = (double)volume / (double)SOUND_VOLUME_STEPS;
    return (float)(f * f);
}

void sound_chime(SoundFx *s)
{
    s->chime_pos = 0;
}

/* the next sample of the chime: C6, E6, G6, C7, each note 80 ms with a quick attack and a decay, the last one rings on; 0 and the end when it has finished */
static float chime_next(SoundFx *s)
{
    static const double hz[4] = {1046.50, 1318.51, 1567.98, 2093.00};
    const double pi = 3.14159265358979323846, note = 0.08 * s->rate, total = 4.0 * note + 0.12 * s->rate;
    double t = (double)s->chime_pos, local, env;
    int k;

    if (s->chime_pos < 0) {
        return 0.0f;
    }
    if (t >= total) {
        s->chime_pos = -1;
        return 0.0f;
    }
    k = (int)(t / note);
    if (k > 3) {
        k = 3;
    }
    local = t - (double)k * note;
    env = (local < 0.004 * s->rate ? local / (0.004 * s->rate) : 1.0) * exp(-local / (k == 3 ? 0.07 : 0.045) / s->rate);
    s->chime_pos++;
    return (float)(0.22 * env * sin(2.0 * pi * hz[k] * t / s->rate));
}

const char *sound_filter_name(int filter)
{
    return filter == SF_WARM ? "WARM" : filter == SF_SOFT ? "SOFT" : "OFF";
}

size_t sound_process(SoundFx *s, const float *plain, size_t nplain, const float *soft, size_t nsoft, float *out, size_t cap)
{
    const float target = sound_gain_of(s->volume, s->mute);
    size_t i, n, warm_n = nsoft;
    const float *src;
    float g = s->gain, step;

    for (i = 0; i < warm_n && s->filter == SF_WARM && i < cap; i++) {
        out[i] = (float)biquad_run(&s->hp, biquad_run(&s->lp, (double)soft[i]));
    }
    if (s->filter != SF_WARM) {                              /* the filters follow the Soft sound all the time, so that Warm starts from settled states */
        for (i = 0; i < nsoft; i++) {
            (void)biquad_run(&s->hp, biquad_run(&s->lp, (double)soft[i]));
        }
    }
    if (s->filter == SF_OFF) {
        src = plain;
        n = nplain < cap ? nplain : cap;
    } else if (s->filter == SF_SOFT) {
        src = soft;
        n = nsoft < cap ? nsoft : cap;
    } else {
        src = out;
        n = nsoft < cap ? nsoft : cap;
    }
    step = n > 0 ? (target - g) / (float)n : 0.0f;
    for (i = 0; i < n; i++) {
        g += step;
        out[i] = (src[i] + chime_next(s)) * g;
    }
    s->gain = n > 0 ? target : g;
    return n;
}
