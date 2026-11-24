/* platform/pokey_random.c - the POKEY RANDOM model, see pokey_random.h. */
#include "pokey_random.h"

#define MASK17 0x1FFFFu

void pokey_random_init(PokeyRandom *r, uint32_t seed)
{
    r->poly = seed & MASK17;
    if (r->poly == MASK17) {
        r->poly = 0;                                 /* the all-ones state is the one the XNOR generator never leaves */
    }
}

static uint32_t step_once(uint32_t p)
{
    return ((p >> 1) + (~((p << 16) ^ (p << 11)) & 0x10000u)) & MASK17;
}

void pokey_random_step(PokeyRandom *r, uint32_t cycles)
{
    uint32_t p = r->poly;
    while (cycles--) {
        p = step_once(p);
    }
    r->poly = p;
}

uint8_t pokey_random_peek(const PokeyRandom *r)
{
    return (uint8_t)((r->poly >> 9) & 0xFFu);
}

uint8_t pokey_random_read(PokeyRandom *r)
{
    pokey_random_step(r, PM_POKEY_READ_STRIDE);
    return pokey_random_peek(r);
}

uint8_t pokey_poly17_bit8(const PokeyRandom *r)
{
    return (uint8_t)((r->poly >> 8) & 1u);
}
