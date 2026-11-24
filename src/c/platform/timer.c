/* platform/timer.c - see timer.h.  The system's monotonic clock: QueryPerformanceCounter on Windows, clock_gettime(CLOCK_MONOTONIC) elsewhere. */
#if !defined(_WIN32) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L          /* clock_gettime with a strict -std=c99 build */
#endif
#include "timer.h"

#if defined(_WIN32)
#include <windows.h>

uint64_t pm_time_ns(void)
{
    LARGE_INTEGER f, c;
    uint64_t freq, ticks;

    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    freq = (uint64_t)f.QuadPart;
    ticks = (uint64_t)c.QuadPart;
    return (ticks / freq) * 1000000000u + (ticks % freq) * 1000000000u / freq;     /* no overflow: the remainder is below freq */
}
#else
#include <time.h>

uint64_t pm_time_ns(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000u + (uint64_t)ts.tv_nsec;
}
#endif
