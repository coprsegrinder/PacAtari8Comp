/* Stage 80c: renders sound-register writes to PCM with the model of src/c/audio.
 *   audio_check WRITES OUT RATE T_START T_NOISE PHASE ORIGIN END [LEVELS]
 *     WRITES: a text file, one write a line: "cycle reg value" (decimal; reg 0-7 = AUDF1, AUDC1, ..., 8 = AUDCTL), cycles not decreasing: the chip model with the exact cycles of a recording
 *     LEVELS: optional text file: every change of the mixed level, "cycle level" (tests compare it with the Python model)
 *   audio_check --frames WRITES OUT RATE FIRST_FRAME LAST_FRAME ORIGIN
 *     WRITES: "frame reg value" a line, frames not decreasing: the front end of the port (audio_frame_writes: the writes of a frame get their cycles from the measured write clock)
 *   OUT: the samples as 32-bit floats, little-endian, written byte by byte.  RATE: output samples a second; the cycles are CPU cycles; ORIGIN may have a fraction (the cycle at which output sample 0 starts).
 * Paths are relative to the main folder, opened through platform/fs.c. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../audio/audio.h"
#include "../audio/pokey.h"
#include "../platform/fs.h"

static Pokey pokey;
static Audio audio;
static PmFile *levels_file;
static char text[1 << 24];

static void on_level(void *ctx, int64_t cycle, double level)
{
    (void)ctx;
    pm_fs_printf(levels_file, "%lld %.9g\n", (long long)cycle, level);
}

static void put_float(PmFile *f, float v)
{
    uint32_t u;
    unsigned char b[4];

    memcpy(&u, &v, sizeof u);
    b[0] = (unsigned char)(u & 0xFFu);
    b[1] = (unsigned char)((u >> 8) & 0xFFu);
    b[2] = (unsigned char)((u >> 16) & 0xFFu);
    b[3] = (unsigned char)((u >> 24) & 0xFFu);
    pm_fs_write(f, b, 4);
}

static void put_floats(PmFile *f, const float *v, size_t n)
{
    size_t i;

    for (i = 0; i < n; i++) {
        put_float(f, v[i]);
    }
}

static int read_text(const char *path)
{
    PmFile *f = pm_fs_open(path, "rb");
    size_t got;

    if (f == NULL) {
        printf("cannot read %s\n", path);
        return 0;
    }
    got = pm_fs_read(f, text, sizeof text - 1);
    pm_fs_close(f);
    text[got] = '\0';
    return 1;
}

/* the next "a b c" line of the text: returns 0 at the end */
static int next_triple(char **cursor, long long *a, unsigned *b, unsigned *c)
{
    while (**cursor != '\0') {
        char *line = *cursor;
        char *eol = strchr(line, '\n');
        if (eol != NULL) {
            *eol = '\0';
            *cursor = eol + 1;
        } else {
            *cursor = line + strlen(line);
        }
        if (sscanf(line, "%lld %u %u", a, b, c) == 3) {
            return 1;
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    PmFile *out;
    char *line;
    float buf[4096];
    double rate, origin;
    long long t_start, t_noise, end;
    size_t n;
    unsigned phase;

    if (argc == 8 && strcmp(argv[1], "--frames") == 0) {
        long long first = atoll(argv[5]), last = atoll(argv[6]), f, fr = 0;
        uint8_t reg[WRITE_CLOCK_MAX], val[WRITE_CLOCK_MAX];
        unsigned count, r = 0, v = 0, have;

        rate = atof(argv[4]);
        origin = atof(argv[7]);
        if (!read_text(argv[2])) {
            return 2;
        }
        out = pm_fs_open(argv[3], "wb");
        if (out == NULL) {
            printf("cannot write %s\n", argv[3]);
            return 2;
        }
        audio_init(&audio, rate);
        audio_set_origin(&audio, origin);
        audio.frame = first;
        line = text;
        have = (unsigned)next_triple(&line, &fr, &r, &v);
        for (f = first; f <= last; f++) {
            count = 0;
            while (have && fr <= f) {
                if (fr == f && count < WRITE_CLOCK_MAX) {
                    reg[count] = (uint8_t)r;
                    val[count] = (uint8_t)v;
                    count++;
                }
                have = (unsigned)next_triple(&line, &fr, &r, &v);
            }
            n = audio_frame_writes(&audio, reg, val, count, buf, 4096);
            put_floats(out, buf, n);
        }
        pm_fs_close(out);
        printf("audio_check: ok, frames %lld-%lld, %u samples dropped\n", first, last, (unsigned)audio.pokey.dropped);
        return 0;
    }
    if (argc != 9 && argc != 10) {
        printf("usage: audio_check WRITES OUT RATE T_START T_NOISE PHASE ORIGIN END [LEVELS] | audio_check --frames WRITES OUT RATE FIRST LAST ORIGIN\n");
        return 2;
    }
    rate = atof(argv[3]);
    t_start = atoll(argv[4]);
    t_noise = atoll(argv[5]);
    phase = (unsigned)atoi(argv[6]);
    origin = atof(argv[7]);
    end = atoll(argv[8]);
    if (!read_text(argv[1])) {
        return 2;
    }
    pokey_init(&pokey, t_start, t_noise, phase, rate);
    pokey_set_origin(&pokey, origin);
    if (argc == 10) {
        levels_file = pm_fs_open(argv[9], "wb");
        if (levels_file == NULL) {
            printf("cannot write %s\n", argv[9]);
            return 2;
        }
        pokey.on_level = on_level;
    }
    out = pm_fs_open(argv[2], "wb");
    if (out == NULL) {
        printf("cannot write %s\n", argv[2]);
        return 2;
    }
    for (line = text; *line != '\0';) {
        long long c;
        unsigned r, v;
        char *eol = strchr(line, '\n');
        if (eol != NULL) {
            *eol = '\0';
        }
        if (sscanf(line, "%lld %u %u", &c, &r, &v) == 3) {
            while (pokey.now + 60000 < c) {                    /* long silences are run in steps so that the sample ring never overflows */
                pokey_run(&pokey, pokey.now + 50000);
                while ((n = pokey_take(&pokey, buf, 4096)) > 0) {
                    put_floats(out, buf, n);
                }
            }
            pokey_write(&pokey, c, r, (uint8_t)v);
            while ((n = pokey_take(&pokey, buf, 4096)) > 0) {
                put_floats(out, buf, n);
            }
        }
        line = eol != NULL ? eol + 1 : line + strlen(line);
    }
    while (pokey.now + 60000 < end) {
        pokey_run(&pokey, pokey.now + 50000);
        while ((n = pokey_take(&pokey, buf, 4096)) > 0) {
            put_floats(out, buf, n);
        }
    }
    pokey_run(&pokey, end);
    while ((n = pokey_take(&pokey, buf, 4096)) > 0) {
        put_floats(out, buf, n);
    }
    pm_fs_close(out);
    if (levels_file != NULL) {
        pm_fs_close(levels_file);
    }
    printf("audio_check: ok, %u writes not modelled, %u samples dropped\n", (unsigned)pokey.unsupported, (unsigned)pokey.dropped);
    return 0;
}
