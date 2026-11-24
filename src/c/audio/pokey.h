/* audio/pokey.h - the POKEY sound chip as the game uses it, from timed register writes to PCM (stage 80c, docs/22).
 *
 * A forward, event-driven model of what Altirra's POKEY renderer does for the sounds of this game, with every rule taken from the chapter and its tools (docs/22, tools/pokey_timers.py, pokey_noise.py,
 * analyze_ghost_sweep.py, analyze_full_waveform.py), each of them checked against Altirra's recorded audio:
 *   - the four channel timers fire on one 28-cycle grid (the 64 kHz divider); a channel reloads with the AUDF it has AT the fire: the next fire is (AUDF + 1) x 28 cycles later; a write does not touch the
 *     pending fire; a write on the very cycle of a fire comes after it;
 *   - a fire is processed in the AUDC / AUDCTL of 2 cycles AFTER it: a pure tone (AUDC bits 7-5 = 101, also 001 / 011 / 111 gated by poly5) toggles the channel's flip-flop, a noise mode (000, 100) sets it to the
 *     current bit of the 17-bit polynomial counter (9-bit with AUDCTL bit 7), gated by the 5-bit one; the counters are free-running from the cycle `t0_noise` (the OS writing SKCTL := 3);
 *   - a fire on the very cycle of a write that changes that channel's AUDF, or a write that changes AUDCTL, gives no edge;
 *   - the audible state of channels 3 and 4 is the flip-flop inverted, of channel 1 and 2 the flip-flop; with AUDCTL bit 2 (bit 1) channel 1 (2) goes through the high-pass flip-flop that channel 3 (4) clocks:
 *     state = flip-flop XOR latch XOR 1, the latch being the flip-flop as it was at the last fire of channel 3 (4);
 *   - the mixer is Altirra's non-linear table, indexed by the volume bits of the channels that are LOW (the output stage is inverting); only pure-tone channels have a volume; then the AC coupling (two discrete
 *     high-pass stages at 63,920 Hz); then the 28-cycle samples are averaged into the output samples (a box filter).
 * Not modelled (the game does not use it; `unsupported` counts the writes that ask for it): AUDCTL bits 0, 3-6, the poly4 modes, volume-only mode.
 * NTSC.  Pure C99; the only state is in the Pokey; 132 KB of it are the polynomial tables.
 */
#ifndef PM_AUDIO_POKEY_H
#define PM_AUDIO_POKEY_H

#include <stddef.h>
#include <stdint.h>

#define POKEY_TICK 28
#define POKEY_CPU_HZ (315e6 / 88.0 / 2.0)       /* 1,789,772.727 Hz */
#define POKEY_NOISE_T0 678973LL                  /* the cycle of the OS's SKCTL := 3 on the NTSC OS-B machine: frame 22, line 191, cycle 103 */
#define POKEY_PHASE 26                            /* residue of the fire grid (cycles mod 28) on the same machine */
#define POKEY_QUEUE 64
#define POKEY_RING 8192

#define POKEY_M17 131071
#define POKEY_M9 511
#define POKEY_M5 31

/* one timed change of the POKEY model: the time, the kind (mode, AUDF or level), the channel or AUDCTL, and the value */
typedef struct PokeyEvent {
    int64_t t;
    uint8_t kind;   /* 0 mode (the AUDC / AUDCTL that fires see), 2 AUDF, 3 level (the AUDC / AUDCTL that the mixer sees) */
    uint8_t arg;    /* 0-3: channel, 4: AUDCTL */
    uint8_t val;
} PokeyEvent;

typedef struct Pokey Pokey;
typedef void (*PokeyLevelFn)(void *ctx, int64_t cycle, double level);

struct Pokey {
    uint8_t audf[4];
    uint8_t mode_audc[4];
    uint8_t vol_audc[4];
    uint8_t mode_ctl, vol_ctl;
    int64_t next_fire[4];
    uint8_t ff[4];
    uint8_t latch[2];
    int64_t t0_noise;
    unsigned phase;
    int64_t now;                     /* every event at or before `now` has been processed */
    int64_t level_t;                 /* the level has been integrated up to here */
    double level;                    /* the current mixed level, in volume units (negative-going) */
    PokeyEvent queue[POKEY_QUEUE];
    int nq;
    uint32_t unsupported;
    PokeyLevelFn on_level;           /* optional: called at every change of the level (tests) */
    void *on_level_ctx;
    /* the output chain */
    double amp;                      /* volume units -> output units */
    double cell_sum;                 /* integral of the level over the 28-cycle cell in progress */
    double ac_c1;                    /* exp(-1 / (63920 tau)) */
    double hp1_x, hp1_y;             /* the first AC stage: previous input and output */
    double hp2_acc;                  /* the second AC stage */
    double step;                     /* CPU cycles per output sample */
    double out_pos;                  /* cycle at which the output sample in progress starts */
    double out_acc;                  /* its integral so far (output units x cycles) */
    float ring[POKEY_RING];
    uint32_t ring_r, ring_w;         /* free-running counters; the ring holds ring_w - ring_r samples */
    uint32_t dropped;                /* samples lost because nobody took them */
    uint8_t p17[POKEY_M17], p9[POKEY_M9], p5[POKEY_M5];
};

/* `t_start`: the cycle from which the chip is simulated (all registers 0 before the first write); `t0_noise`: the cycle at which the polynomial counters start (the OS writes SKCTL := 3), `phase`: the residue of the
 * 28-cycle fire grid (POKEY_PHASE on the NTSC OS-B machine; it is (26 + t0_noise - POKEY_NOISE_T0) mod 28 on a machine that boots with another timing); `sample_rate`: output samples a second */
void pokey_init(Pokey *p, int64_t t_start, int64_t t0_noise, unsigned phase, double sample_rate);

/* put the start of output sample 0 at cycle `cycle` (a real number: the shell and the checks align the audio to a clock); call before the first output is made */
void pokey_set_origin(Pokey *p, double cycle);

/* a write to the sound registers: reg 0-7 = AUDF1, AUDC1, AUDF2, AUDC2, ... (address - $D200), 8 = AUDCTL; `cycle` must not go backwards */
void pokey_write(Pokey *p, int64_t cycle, unsigned reg, uint8_t value);

/* advance the chip to `cycle` (the last 3 cycles stay pending: a later write can still reach back 2 cycles); output samples that are complete become readable */
void pokey_run(Pokey *p, int64_t cycle);

/* copy up to `max` finished samples out */
size_t pokey_take(Pokey *p, float *dst, size_t max);

/* the mixer's table: volume units of the channels that are low (n0 = bit 0 count, n1 = bit 1 count, n23 = bit 2 + 2 x bit 3 count) */
double pokey_mixer_level(int n0, int n1, int n23);

#endif
