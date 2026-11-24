/* The table of the pure functions for the vector runner (stage 76a). */
#ifndef PM_TESTS_PURE_FUNCTIONS_H
#define PM_TESTS_PURE_FUNCTIONS_H

#include <stddef.h>

#include "../core/ref.h"
#include "vector.h"

/* returns 0 when the call was run (the result is in `out`), 1 when the recorded arguments have the wrong shape;
 * *rnd_ok is set to 0 when the function used a different number of RANDOM values than the call supplied */
typedef int (*PureFn)(const PureVec *in, VecValue *out, int *rnd_ok);

typedef struct PureEntry {
    const char *name;
    PureFn fn;
} PureEntry;

PureFn pure_lookup(const char *name);   /* the pure function of that name, or NULL */
size_t pure_count(void);   /* how many pure functions are registered */
const char *pure_name(size_t i);   /* the name of the i-th */
int value_equal(const VecValue *a, const VecValue *b);   /* 1 when two recorded values have the same shape and numbers */

#endif
