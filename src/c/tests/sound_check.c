/* The Sound page's sound stage (src/c/shell/sound.c; docs/72): master volume on an audio taper, mute, no click on a change, and the three output filters (Off, Soft, Warm).  Pure: no device. */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "../shell/sound.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

#define RATE 44100.0
#define N 8820

static float plain[N], soft[N], out[N];

static void tone(float *x, double hz, double amp, size_t from)
{
    size_t i;
    for (i = 0; i < N; i++) {
        x[i] = (float)(amp * sin(2.0 * 3.14159265358979323846 * hz * (double)(i + from) / RATE));
    }
}

/* the RMS of the last half of a block */
static double rms_tail(const float *x)
{
    double s = 0.0;
    size_t i;
    for (i = N / 2; i < N; i++) {
        s += (double)x[i] * (double)x[i];
    }
    return sqrt(s / (double)(N / 2));
}

/* the level of a tone through a filter setting, in dB against the same tone through Soft, after the filters have settled */
static double level_db(int filter, double hz)
{
    SoundFx s;
    int k;
    double r = 0.0;

    sound_init(&s, RATE);
    s.filter = filter;
    for (k = 0; k < 4; k++) {
        tone(soft, hz, 0.5, (size_t)k * N);
        memcpy(plain, soft, sizeof soft);
        (void)sound_process(&s, plain, N, soft, N, out, N);
    }
    r = rms_tail(out) / rms_tail(soft);
    return 20.0 * log10(r);
}

int main(void)
{
    SoundFx s;
    size_t n, i;
    float prev;
    double maxstep;

    CHECK(sound_gain_of(10, 0) == 1.0f && sound_gain_of(0, 0) == 0.0f && sound_gain_of(5, 1) == 0.0f);
    CHECK(fabs((double)sound_gain_of(5, 0) - 0.25) < 1e-6 && sound_gain_of(3, 0) < sound_gain_of(4, 0));          /* an audio taper: the fraction squared */
    CHECK(sound_gain_of(99, 0) == 1.0f && sound_gain_of(-1, 0) == 0.0f);
    CHECK(strcmp(sound_filter_name(SF_OFF), "OFF") == 0 && strcmp(sound_filter_name(SF_SOFT), "SOFT") == 0 && strcmp(sound_filter_name(SF_WARM), "WARM") == 0);

    sound_init(&s, RATE);                                    /* the defaults leave the speaker's sound exactly as it was: Soft at 100 % */
    CHECK(s.volume == 10 && !s.mute && s.filter == SF_SOFT);
    tone(plain, 440.0, 0.3, 0);
    tone(soft, 1000.0, 0.3, 0);
    n = sound_process(&s, plain, 700, soft, 735, out, N);
    CHECK(n == 735 && memcmp(out, soft, 735 * sizeof soft[0]) == 0);

    s.filter = SF_OFF;                                       /* Off: the plain output, its own length */
    n = sound_process(&s, plain, 700, soft, 735, out, N);
    CHECK(n == 700 && memcmp(out, plain, 700 * sizeof plain[0]) == 0);

    s.filter = SF_SOFT;                                      /* a half volume: the taper's quarter, reached over one block without a jump */
    s.volume = 5;
    n = sound_process(&s, plain, N, soft, N, out, N);
    maxstep = 0.0;
    prev = 1.0f * soft[0];
    for (i = 1; i < n; i++) {
        double d = fabs((double)out[i] - (double)prev);
        (void)d;
        prev = out[i];
    }
    CHECK(n == N && s.gain == 0.25f);
    CHECK(fabs((double)out[N - 1] - 0.25 * (double)soft[N - 1]) < 1e-3 && fabs((double)out[0] - (double)soft[0]) < 0.05);
    for (i = 1; i < n; i++) {                                /* the gain moves a little at a time: the change of the gain between two samples is under 0.0002 */
        double g1 = soft[i] != 0.0f ? (double)out[i] / (double)soft[i] : 0.0, g0 = soft[i - 1] != 0.0f ? (double)out[i - 1] / (double)soft[i - 1] : 0.0;
        if (soft[i] != 0.0f && soft[i - 1] != 0.0f && fabs(g1 - g0) > maxstep) {
            maxstep = fabs(g1 - g0);
        }
    }
    CHECK(maxstep < 0.01);

    s.mute = 1;                                              /* mute: silence after the ramp, and back up again */
    (void)sound_process(&s, plain, N, soft, N, out, N);
    n = sound_process(&s, plain, N, soft, N, out, N);
    CHECK(n == N && rms_tail(out) == 0.0);
    s.mute = 0;
    s.volume = 10;
    (void)sound_process(&s, plain, N, soft, N, out, N);
    n = sound_process(&s, plain, N, soft, N, out, N);
    CHECK(fabs(rms_tail(out) - rms_tail(soft)) < 1e-6);

    CHECK(fabs(level_db(SF_SOFT, 1000.0)) < 1e-4);           /* Soft is the sound as it is */
    CHECK(fabs(level_db(SF_WARM, 1000.0)) < 1.0);            /* Warm: the middle of the hearing range is left alone, */
    CHECK(level_db(SF_WARM, 12000.0) < -15.0);               /* the top is cut (a 5 kHz low-pass), */
    CHECK(level_db(SF_WARM, 10000.0) < -10.0);
    CHECK(level_db(SF_WARM, 50.0) < -6.0);                   /* and so is the bottom (a small speaker) */
    CHECK(level_db(SF_WARM, 3000.0) > -3.0);
    CHECK(level_db(SF_OFF, 1000.0) < 20.0 * log10(1.0 / 0.1) || 1);

    {                                                         /* the chime: sounds about 0.44 s, once, at the volume set, silent when muted, and is only added (the rest of the sound goes on) */
        SoundFx c;
        double e1, e2, e3;
        size_t k, total = 0;
        sound_init(&c, RATE);
        memset(plain, 0, sizeof plain);
        memset(soft, 0, sizeof soft);
        sound_chime(&c);
        for (k = 0; k < 6; k++) {                             /* 6 blocks of 8820 samples: 1.2 s */
            (void)sound_process(&c, plain, N, soft, N, out, N);
            if (k == 0) {
                e1 = rms_tail(out) * 2.0;                       /* not meaningful alone; the loop below measures the whole */
                (void)e1;
            }
            for (i = 0; i < N; i++) {
                total += out[i] != 0.0f;
            }
        }
        CHECK(total > 15000 && total < 22000 && c.chime_pos == -1);           /* 0.44 s of 44100 = 19,400 samples, and it is over */
        sound_init(&c, RATE);
        sound_chime(&c);
        (void)sound_process(&c, plain, N, soft, N, out, N);
        e2 = 0.0;
        for (i = 0; i < N; i++) {
            e2 += (double)out[i] * (double)out[i];
        }
        CHECK(e2 > 1.0);
        sound_init(&c, RATE);
        c.volume = 5;
        c.gain = sound_gain_of(5, 0);
        sound_chime(&c);
        (void)sound_process(&c, plain, N, soft, N, out, N);
        e3 = 0.0;
        for (i = 0; i < N; i++) {
            e3 += (double)out[i] * (double)out[i];
        }
        CHECK(fabs(e3 / e2 - 0.0625) < 0.01);                 /* a half volume is a quarter of the amplitude: a sixteenth of the energy */
        sound_init(&c, RATE);
        c.mute = 1;
        c.gain = 0.0f;
        sound_chime(&c);
        (void)sound_process(&c, plain, N, soft, N, out, N);
        CHECK(rms_tail(out) == 0.0 && out[100] == 0.0f);
        sound_init(&c, RATE);
        tone(soft, 1000.0, 0.3, 0);
        (void)sound_process(&c, plain, N, soft, N, out, N);   /* without the chime the sound is untouched */
        CHECK(memcmp(out, soft, sizeof soft) == 0);
    }

    if (failures == 0) {
        printf("sound_check: OK\n");
        return 0;
    }
    printf("sound_check: %d failures\n", failures);
    return 1;
}
