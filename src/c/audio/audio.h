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

#endif
