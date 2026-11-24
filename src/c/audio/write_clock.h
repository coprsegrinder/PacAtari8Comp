/* audio/write_clock.h - the cycle of each sound-register write inside a frame (stage 80c).
 * The core runs a frame as one call and knows no cycles; the chip model needs them.  Measured on the recorded sessions (tools/measure_write_clock.py, 45,527 frames with sound writes): the handler of a
 * frame writes its sound registers in one burst; the first write is a median 39-42 cycles after the frame boundary (10th to 90th percentile: -108 to +542), consecutive writes are a median 9 cycles apart.
 * A table of the measured cycles of each sequence of registers (the code paths are few: 18 sequences) was tried and is no better than this rule (docs/22, OPEN-VERIFICATION.md C-115): what the
 * phase between channels needs is the exact cycle of the instruction, which only a cycle-exact machine knows. */
#ifndef PM_AUDIO_WRITE_CLOCK_H
#define PM_AUDIO_WRITE_CLOCK_H

#include <stdint.h>

#define WRITE_CLOCK_MAX 16
#define WRITE_CLOCK_START 40       /* cycles after the frame start */
#define WRITE_CLOCK_SPACING 9      /* cycles between writes of a frame */

/* the cycles (relative to the frame start) of the n writes of one frame; increasing, at least 4 apart */
void write_clock_stamp(unsigned n, int32_t *cycle);

#endif
