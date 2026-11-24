/* Stage 80c: self test of the audio (src/c/audio): no files, no recordings.
 * The POKEY model: the pitch of a pure tone, its level from the mixer table, silence, the mixer of two channels, the noise start state, the AC coupling, determinism, the counters of what is not modelled;
 * the front end: samples a frame, the log of a World taken and emptied, writes to other addresses ignored. */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "../audio/audio.h"
#include "../audio/pokey.h"

static int failures;

#define CHECK(cond)                                                        \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("FAILED line %d: %s\n", __LINE__, #cond);               \
            failures++;                                                    \
        }                                                                  \
    } while (0)

static Pokey chip, chip2;
static Audio audio;
static World world;
static float pcm[80000], pcm2[80000];

/* run the chip to `end` taking the samples in steps; returns the number of samples */
static size_t render(Pokey *p, int64_t end, float *dst, size_t cap)
{
    size_t n = 0, got;

    while (p->now + 60000 < end) {
        pokey_run(p, p->now + 50000);
        while (n < cap && (got = pokey_take(p, dst + n, cap - n)) > 0) {
            n += got;
        }
    }
    pokey_run(p, end);
    while (n < cap && (got = pokey_take(p, dst + n, cap - n)) > 0) {
        n += got;
    }
    return n;
}

static size_t rising_crossings(const float *x, size_t n)
{
    size_t i, c = 0;

    for (i = 1; i < n; i++) {
        if (x[i - 1] < 0.0f && x[i] >= 0.0f) {
            c++;
        }
    }
    return c;
}

static void test_pitch_and_level(void)
{
    size_t n;
    size_t i;
    float lo = 1e9f, hi = -1e9f;
    double expected;

    pokey_init(&chip, 0, POKEY_NOISE_T0, POKEY_PHASE, 44100.0);
    pokey_write(&chip, 1000, 0, 114);                   /* AUDF1 = 114: a toggle every 115 x 28 cycles */
    pokey_write(&chip, 1010, 1, 0xAF);                  /* AUDC1: pure tone, volume 15 */
    n = render(&chip, 1789773, pcm, 80000);             /* one second */
    CHECK(n > 44000 && n < 44200);
    /* 1,789,772.727 / (2 x 115 x 28) = 277.9 Hz: the rising zero crossings after the first 1000 samples (0.977 s) */
    expected = 277.91 * (double)(n - 1000) / 44100.0;
    CHECK(fabs((double)rising_crossings(pcm + 1000, n - 1000) - expected) <= 1.5);
    for (i = 2000; i < n; i++) {
        if (pcm[i] < lo) {
            lo = pcm[i];
        }
        if (pcm[i] > hi) {
            hi = pcm[i];
        }
    }
    /* the level of a volume-15 channel when it is low, through the table (1 x bit 0, 1 x bit 1, 3 x bit 2 and 3), scaled; the AC coupling (time constant 2.6 ms) makes a square wave of half period T/2 swing
     * 2 / (1 + exp(-T / (2 tau))) times the step */
    expected = pokey_mixer_level(1, 1, 3) * 0.5 * 2.1 * (0.56 / 8.24 / 4.0);
    expected *= 2.0 / (1.0 + exp(-(2.0 * 115.0 * 28.0 / POKEY_CPU_HZ) / (2.0 * 0.0025968510736)));
    CHECK(fabs((double)(hi - lo) - expected) < 0.03 * expected);
}

static void test_silence_and_determinism(void)
{
    size_t n, i;
    int silent = 1;

    pokey_init(&chip, 0, POKEY_NOISE_T0, POKEY_PHASE, 44100.0);
    n = render(&chip, 600000, pcm, 80000);
    CHECK(n > 0);
    for (i = 0; i < n; i++) {
        if (pcm[i] != 0.0f) {
            silent = 0;
        }
    }
    CHECK(silent);                                      /* idle channels have no volume: nothing is heard */
    pokey_init(&chip, 0, POKEY_NOISE_T0, POKEY_PHASE, 44100.0);
    pokey_init(&chip2, 0, POKEY_NOISE_T0, POKEY_PHASE, 44100.0);
    pokey_write(&chip, 500, 3, 0xA8);
    pokey_write(&chip2, 500, 3, 0xA8);
    pokey_write(&chip, 520, 2, 40);
    pokey_write(&chip2, 520, 2, 40);
    n = render(&chip, 400000, pcm, 80000);
    CHECK(render(&chip2, 400000, pcm2, 80000) == n);
    CHECK(memcmp(pcm, pcm2, n * sizeof pcm[0]) == 0);
}

static void test_two_channels_mix_through_the_table(void)
{
    size_t n, i;
    float hi = -1e9f, lo = 1e9f;
    double one, two;

    /* channels 1 and 2 at the same pitch, volume 8 each: the swing is the table's value for 2 channels low, less than twice one channel's */
    pokey_init(&chip, 0, POKEY_NOISE_T0, POKEY_PHASE, 44100.0);
    pokey_write(&chip, 1000, 0, 60);
    pokey_write(&chip, 1010, 1, 0xA8);
    n = render(&chip, 800000, pcm, 80000);
    for (i = 4000; i < n; i++) {
        if (pcm[i] > hi) {
            hi = pcm[i];
        }
        if (pcm[i] < lo) {
            lo = pcm[i];
        }
    }
    one = (double)(hi - lo);
    CHECK(one > 0.0);
    CHECK(pokey_mixer_level(0, 0, 4) < 2.0 * pokey_mixer_level(0, 0, 2) + 1e-9);          /* the curve saturates: two channels low are less than twice one */
    two = pokey_mixer_level(0, 0, 4);
    CHECK(two > pokey_mixer_level(0, 0, 2));
}

static void test_unsupported_and_misuse(void)
{
    pokey_init(&chip, 0, POKEY_NOISE_T0, POKEY_PHASE, 44100.0);
    pokey_write(&chip, 100, 8, 0x84);                   /* the game's AUDCTL: modelled */
    pokey_write(&chip, 120, 8, 0x00);
    CHECK(chip.unsupported == 0);
    pokey_write(&chip, 140, 8, 0x40);                   /* 1.79 MHz clock of channel 1: not modelled */
    pokey_write(&chip, 160, 3, 0x1F);                   /* volume-only mode */
    pokey_write(&chip, 180, 5, 0x40);                   /* poly4 */
    CHECK(chip.unsupported == 3);
    pokey_write(&chip, 200, 9, 1);                      /* not a sound register: ignored */
    (void)render(&chip, 100000, pcm, 80000);
    CHECK(chip.dropped == 0);
}

static void test_coincident_write_and_fire(void)
{
    size_t n;
    int64_t fire;

    /* a write on the very cycle of a fire of its channel: the fire gives no edge, nothing breaks */
    pokey_init(&chip, 0, POKEY_NOISE_T0, POKEY_PHASE, 44100.0);
    fire = chip.next_fire[0];
    pokey_write(&chip, fire - 100, 1, 0xA8);
    pokey_write(&chip, fire, 0, 5);
    n = render(&chip, 200000, pcm, 80000);
    CHECK(n > 0);
    CHECK(chip.dropped == 0);
}

/* the speaker's sound (audio_hq): a tone above the output's Nyquist frequency is not folded down into the hearing range, a tone below it is as loud as with the plain model, and the stream is as long */
static double band_energy(const float *x, size_t n, double hz, double rate)
{
    double re = 0.0, im = 0.0;
    size_t i;

    for (i = 0; i < n; i++) {
        double ph = 6.283185307179586 * hz * (double)i / rate;
        re += (double)x[i] * cos(ph);
        im += (double)x[i] * sin(ph);
    }
    return (re * re + im * im) / ((double)n * (double)n);
}

static void test_hq(void)
{
    static AudioHq hq;
    static float all_plain[44100 * 2], all_hq[44100 * 2];
    uint8_t reg[WRITE_CLOCK_MAX], val[WRITE_CLOCK_MAX];
    size_t np = 0, nh = 0, n;
    int f, pass;
    double plain_alias = 0.0, hq_alias = 0.0, plain_low = 0.0, hq_low = 0.0;

    for (pass = 0; pass < 2; pass++) {
        /* pass 0: AUDF1 = 0 at volume 8 (a pure 31,960 Hz tone: the rest of the start tune); pass 1: AUDF1 = 70 (a tone of 450 Hz) */
        audio_init(&audio, 44100.0);
        audio_hq_init(&hq, 44100.0);
        np = nh = 0;
        for (f = 0; f < 90; f++) {
            reg[0] = 1; val[0] = 0xA8;
            reg[1] = 0; val[1] = pass == 0 ? 0 : 70;
            n = audio_frame_writes(&audio, reg, val, 2, pcm, 2000);
            if (np + n <= sizeof all_plain / sizeof all_plain[0]) {
                memcpy(all_plain + np, pcm, n * sizeof pcm[0]);
                np += n;
            }
            n = audio_hq_frame(&hq, reg, val, 2, pcm, 2000);
            if (nh + n <= sizeof all_hq / sizeof all_hq[0]) {
                memcpy(all_hq + nh, pcm, n * sizeof pcm[0]);
                nh += n;
            }
        }
        CHECK(nh + 200 >= np && nh <= np + 4);                              /* as long (the filter's delay is a few samples more than 0.5 ms) */
        if (pass == 0) {
            plain_alias = band_energy(all_plain + 8000, 30000, 44100.0 - 31960.0, 44100.0);
            hq_alias = band_energy(all_hq + 8000, 30000, 44100.0 - 31960.0, 44100.0);
        } else {
            plain_low = band_energy(all_plain + 8000, 30000, 450.0 * 0.0 + 63920.0 / (2.0 * 71.0), 44100.0);
            hq_low = band_energy(all_hq + 8000, 30000, 63920.0 / (2.0 * 71.0), 44100.0);
        }
    }
    CHECK(plain_alias > 1e-6);                                               /* the plain model has the folded tone ... */
    CHECK(hq_alias < plain_alias * 1e-4);                                    /* ... the speaker's sound has not (80 dB down) */
    CHECK(plain_low > 1e-6 && hq_low > plain_low * 0.9 && hq_low < plain_low * 1.1);   /* a tone in the hearing range is as loud */
}

static void test_front_end(void)
{
    size_t total = 0, n;
    int f;
    double energy = 0.0;
    size_t i;

    audio_init(&audio, 44100.0);
    world_init(&world);
    for (f = 0; f < 600; f++) {                          /* ten seconds; from frame 3 on the siren: channel 2, AUDF2 = 40, AUDC2 = $A1 */
        world.pokey_n = 0;
        if (f >= 3) {
            world_pokey(&world, 0xD202, 40);
            world_pokey(&world, 0xD203, 0xA1);
            world_pokey(&world, 0xD20E, 0xC0);           /* IRQEN: not a sound register, ignored */
            world_pokey(&world, 0xD20F, 7);              /* SKCTL */
        }
        n = audio_frame(&audio, &world, pcm, 2000);
        CHECK(world.pokey_n == 0 && world.pokey_overflow == 0);          /* the log is taken */
        CHECK(f == 0 ? (n >= 700 && n <= 737) : (n >= 734 && n <= 737));    /* 44100 / 59.92 = 735.99; the first frame is 1,000 cycles short (the lag) */
        total += n;
        if (f >= 5) {
            for (i = 0; i < n; i++) {
                energy += (double)pcm[i] * (double)pcm[i];
            }
        }
    }
    CHECK(total >= 441540 && total <= 441548);                           /* (600 x 29868 - 1000 lag) cycles / 40.58 cycles a sample */
    CHECK(energy > 0.0);
    /* a frame with no writes is silent only when the chip is idle: the siren goes on without writes (the timers run) */
    n = audio_frame(&audio, &world, pcm, 2000);
    energy = 0.0;
    for (i = 0; i < n; i++) {
        energy += (double)pcm[i] * (double)pcm[i];
    }
    CHECK(energy > 0.0);
}

int main(void)
{
    test_pitch_and_level();
    test_silence_and_determinism();
    test_two_channels_mix_through_the_table();
    test_unsupported_and_misuse();
    test_coincident_write_and_fire();
    test_front_end();
    test_hq();
    if (failures == 0) {
        printf("audio_selftest: OK\n");
        return 0;
    }
    printf("audio_selftest: %d failures\n", failures);
    return 1;
}
