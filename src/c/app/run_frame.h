/* app/run_frame.h - one frame of the running game on a platform (stage 77b; twin of tools/platform_iface.run_frame).
 * The inputs of the frame are read from the platform into the World (the stick shadows, the collision registers, the clock, the attract values), the frame runs with RANDOM from the platform,
 * and the platform is told the frame is done.  The frame is the whole deferred vertical-blank handler for a frame of the running game (core/play.h vbi_play_frame: the frame body and the
 * tunnel clip; the Python run_frame stops after play_frame, which is the same without the clip). */
#ifndef PM_APP_RUN_FRAME_H
#define PM_APP_RUN_FRAME_H

#include <stdint.h>

#include "../core/world.h"
#include "../platform/hal.h"

/* the inputs of one frame, copied into the World (STICK0 / STICK1 from the platform, STICK2 / 3 = $0F: nothing reads them) */
void read_inputs(World *w, const Platform *p);

/* one frame; returns the number of RANDOM values the frame took */
uint32_t run_frame(World *w, Platform *p);

#endif
