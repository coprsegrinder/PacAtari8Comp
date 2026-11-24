/* audio/write_clock.c - see write_clock.h. */
#include "write_clock.h"

void write_clock_stamp(unsigned n, int32_t *cycle)
{
    unsigned i;

    for (i = 0; i < n; i++) {
        cycle[i] = WRITE_CLOCK_START + (int32_t)i * WRITE_CLOCK_SPACING;
    }
}
