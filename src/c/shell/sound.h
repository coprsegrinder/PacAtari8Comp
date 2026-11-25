/* shell/sound.h - the Sound page's settings applied to the speaker's sound (docs/72): master volume, mute, and the output filter (Off, Soft, Warm).
 * Portable, no dependence on the game: it takes the two sounds the front end makes of each frame (the chip's plain output and the same chip at four times the rate, low-passed: audio.h) and makes the
 * one the speaker plays.  It never touches the game's own sound digest (which is of the plain output before this). */
#ifndef PM_SOUND_H
#define PM_SOUND_H

#include <stddef.h>

#define SOUND_VOLUME_STEPS 10    /* the master volume goes 0 .. 10 (0 % .. 100 %) */

typedef enum SoundFilter { SF_OFF = 0, SF_SOFT = 1, SF_WARM = 2, SF_COUNT = 3 } SoundFilter;

typedef struct SoundBiquad {
    double b0, b1, b2, a1, a2;
    double z1, z2;
} SoundBiquad;

typedef struct SoundFx {
    int volume;                  /* 0 .. SOUND_VOLUME_STEPS */
    int mute;
    int filter;                  /* SoundFilter */
    float gain;                  /* the gain now (it moves to the target over one frame: no click) */
    double rate;
    long chime_pos;              /* the achievement chime: samples played so far, or -1 when it is not sounding */
    SoundBiquad lp, hp;          /* Warm: a low-pass at 5 kHz and a high-pass at 140 Hz, run on the Soft sound all the time so that choosing Warm starts from settled filters */
} SoundFx;

void sound_init(SoundFx *s, double rate);
/* the gain of a volume step: 0 .. 1 on an audio taper (the square of the fraction), so that each step is about as loud a step as the next */
float sound_gain_of(int volume, int mute);
const char *sound_filter_name(int filter);
/* the chime of an achievement: four rising notes of about a third of a second, added to the speaker's sound before the volume and the mute (so they apply to it); starting it again restarts it */
void sound_chime(SoundFx *s);
/* makes the speaker's sound of one frame from the plain output (`plain`, nplain samples) and the Soft output (`soft`, nsoft samples); returns the number of samples written to `out` (at most cap):
 * the plain count for Off, else the Soft count */
size_t sound_process(SoundFx *s, const float *plain, size_t nplain, const float *soft, size_t nsoft, float *out, size_t cap);

#endif
