/* platform/timer.h - a monotonic clock in nanoseconds (stage 88): the only way the port reads time.  Used by the shell to measure the time a frame takes (`pacman_a8 run --time`); nothing in the game depends on it. */
#ifndef PM_PLATFORM_TIMER_H
#define PM_PLATFORM_TIMER_H

#include <stdint.h>

uint64_t pm_time_ns(void);   /* nanoseconds since an arbitrary start; never goes back */

#endif
