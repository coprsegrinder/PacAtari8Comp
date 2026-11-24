/* platform/pokey_random.h - the POKEY RANDOM register as a model (owner decision D1, 2026-11-18: "the POKEY polynomial model, seedable, the stream injectable").
 * The real register is the 17-bit polynomial counter that runs freely at one step per CPU cycle; the game reads its upper 8 bits at a few places.  The model:
 *   - the same generator as Altirra's tables (tools/pokey_noise.py: p = (p >> 1) + (~((p << 16) ^ (p << 11)) & 0x10000), period 131,071, the all-ones state never occurs);
 *   - one step per CPU cycle: the port advances the counter by a whole frame (PM_POKEY_FRAME_CYCLES) at the start of a frame, and by PM_POKEY_READ_STRIDE cycles before each read in the frame
 *     (the original's values depend on the cycle of the read; the port reads at fixed cycle offsets, so a seed replays exactly);
 *   - RANDOM = bits 16..9 of the counter.  What is NOT verified: that this byte equals the hardware's at the same cycle (the sequence is not measured against Altirra's RANDOM reads);
 *     the game's use (bit 7, the low nibble, the low bits as masks) only needs a full-period, well-spread byte. */
#ifndef PM_PLATFORM_POKEY_RANDOM_H
#define PM_PLATFORM_POKEY_RANDOM_H

#include <stdint.h>

#define PM_POKEY_FRAME_CYCLES 29868   /* an NTSC frame: 262 lines of 114 cycles */
#define PM_POKEY_READ_STRIDE 1000     /* CPU cycles between two reads in a frame */
#define PM_POKEY_POLY17_PERIOD 131071u

/* the POKEY RANDOM model: the 17-bit polynomial counter */
typedef struct PokeyRandom {
    uint32_t poly;    /* the 17-bit counter */
} PokeyRandom;

void pokey_random_init(PokeyRandom *r, uint32_t seed);    /* the seed's low 17 bits; the all-ones state is replaced by 0 */
void pokey_random_step(PokeyRandom *r, uint32_t cycles);  /* advance by `cycles` steps */
uint8_t pokey_random_peek(const PokeyRandom *r);          /* bits 16..9 */
uint8_t pokey_random_read(PokeyRandom *r);                /* advance by PM_POKEY_READ_STRIDE, then peek */
uint8_t pokey_poly17_bit8(const PokeyRandom *r);          /* bit 8 of the counter: the bit the sound model uses (tools/pokey_noise.py S17) */

#endif
