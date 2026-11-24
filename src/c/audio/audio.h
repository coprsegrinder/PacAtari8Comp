/* audio/audio.h - the sound of the game as a function of the World, frame by frame (stage 80c, docs/22, docs/44).
 * The core logs every write to the sound chip in World.pokey_addr / pokey_val (core/sound.c: sound_wr).  audio_frame takes the log of one frame, gives the writes their cycles inside the frame (write_clock.h),
 * feeds the POKEY model (pokey.h) and returns the PCM of the frame: mono, 32-bit float, about 735.99 samples at 44,100 Hz.  The audio runs about 1,000 cycles (0.56 ms) behind the frame it belongs to,
 * a constant: the writes of a handler start a few hundred cycles before the frame boundary and the chip model needs them in order.
 * NTSC.  The writes carry no cycles in the core, so the waveform has the pitch, level and timing of each frame of the original but not its phase (docs/22: 98 % of the 50 ms windows have the spectrum of
 * the recording; the others are ghost-eaten sweeps, whose loudness depends on the phase between three channels). */
#ifndef PM_AUDIO_AUDIO_H
#define PM_AUDIO_AUDIO_H

#include <stddef.h>
#include <stdint.h>

#include "../core/world.h"
#include "pokey.h"
#include "write_clock.h"

#define AUDIO_FRAME_CYCLES 29868LL     /* 262 lines x 114 cycles */
#define AUDIO_LAG_CYCLES 1000LL

/* the audio front end: the POKEY model and the number of the next frame */
typedef struct Audio {
    Pokey pokey;
    int64_t frame;                     /* the number of the next frame */
} Audio;

void audio_init(Audio *a, double sample_rate);   /* the sound-chip model at power-on, making samples at `sample_rate` Hz */

/* only for tests and tools that align the audio to a recording: the cycle at which output sample 0 starts (call before the first frame) */
void audio_set_origin(Audio *a, double cycle);

/* one frame: consumes the sound writes of `w` (and empties its log: w->pokey_n = 0, w->pokey_overflow = 0), returns the number of samples copied to `out` (at most `cap`) */
size_t audio_frame(Audio *a, World *w, float *out, size_t cap);

/* the same with the writes given as a list (register 0-8 and value) instead of a World: the frame number selects the time */
size_t audio_frame_writes(Audio *a, const uint8_t *reg, const uint8_t *val, unsigned n, float *out, size_t cap);

/* the sound writes of one frame as the chip sees them (register 0-8 and value), without taking them from the World's log; returns their number */
unsigned audio_world_writes(const World *w, uint8_t reg[WRITE_CLOCK_MAX], uint8_t val[WRITE_CLOCK_MAX]);

/* The sound for a speaker (docs/22 section on the output stage).  The chip model above renders straight to the output rate by averaging the chip's 63.9 kHz samples, which is what the recordings of Altirra
 * were compared with (100 Hz - 5 kHz): above the output's Nyquist frequency it lets the tones through folded down.  The game has such a tone: between the notes of the start tune voice 1 is given AUDF = 0 at
 * volume 8, a pure tone of 31,960 Hz that nobody hears and no speaker plays, and a rate of 44.1 kHz folds it down to 12.1 kHz, a thin ringing.  The output for a speaker therefore renders at four times the
 * rate and takes the samples down with a low-pass filter (a Kaiser-windowed sinc, 191 taps, flat to 18 kHz, 70 dB down from 22.05 kHz): what is audible is the same, the folded tones are gone.  The model
 * above (and so every digest) is not changed; only the front end uses this. */
#define AUDIO_HQ_OVER 4
#define AUDIO_HQ_TAPS 191
#define AUDIO_HQ_MAX 8192

/* the speaker's sound: the chip model at four times the output rate, the filter and the samples not yet used up */
typedef struct AudioHq {
    Audio audio;                                    /* the chip model at four times the output rate */
    float coef[AUDIO_HQ_TAPS];
    float hist[AUDIO_HQ_TAPS + AUDIO_HQ_MAX];       /* the samples of the fast rate not yet used up */
    size_t n;
} AudioHq;

/* the speaker's sound at power-on, making samples at `out_rate` Hz */
void audio_hq_init(AudioHq *h, double out_rate);
/* one frame: the writes as audio_frame_writes takes them; returns the samples at the output rate (at most `cap`) */
size_t audio_hq_frame(AudioHq *h, const uint8_t *reg, const uint8_t *val, unsigned n, float *out, size_t cap);

#endif
