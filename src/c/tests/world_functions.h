/* The table of the World functions for the vector runner (stage 75b: the test functions; 76b onwards: the game's functions). */
#ifndef PM_TESTS_WORLD_FUNCTIONS_H
#define PM_TESTS_WORLD_FUNCTIONS_H

#include "../core/random_feed.h"
#include "../core/world.h"

/* a recorded call: the integer arguments in order, the RANDOM values supplied.  Returns 0 when the call was run (*ret is its return value, 0 for none),
 * 1 when the recorded arguments have the wrong shape or are outside what the function takes (the call is then counted as a difference, never guessed). */
typedef int (*WorldFn)(World *w, const int32_t *args, int nargs, RandomFeed *rnd, int32_t *ret);

WorldFn world_lookup(const char *name);   /* the World function of that name, or NULL */

#endif
