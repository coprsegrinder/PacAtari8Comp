/* shell/replay.h - recorded inputs of a game, one record a frame (stage 80d, docs/51, docs/49 D3).
 * A replay is everything the game takes from the outside (docs/45) frame by frame: the stick, the triggers, the console, the key code the OS stores, the key delay, the OS clock, the attract-mode values and,
 * optionally, the RANDOM bytes of the frame.  The format (little-endian, read and written one byte at a time):
 *   header  4 bytes "PMRP", u16 version (1), u16 flags (bit 0: every frame carries its RANDOM bytes), u32 seed (the RANDOM model's seed when the frames carry none), u32 number of frames,
 *           u8 the OS clock at power-on, 3 bytes 0                                                  = 20 bytes
 *   frame   10 bytes: STICK0, STICK1, STRIG0, STRIG1, CONSOL, CH (the key code, $FF = none), KEYDEL, RTCLOK2, DRKMSK, COLRSH;  if bit 0 of the flags: u16 n, n bytes of RANDOM
 *   trailer u32 FNV-1a (32 bit) of every byte before it
 * Nothing allocates: the caller gives the buffer. */
#ifndef PM_SHELL_REPLAY_H
#define PM_SHELL_REPLAY_H

#include <stddef.h>
#include <stdint.h>

#define REPLAY_VERSION 1
#define REPLAY_FLAG_RANDOM 1u
#define REPLAY_HEADER 20u
#define REPLAY_FRAME_BASE 10u
#define REPLAY_MAX_FRAMES 4000000u

/* the inputs of one frame: sticks, triggers, console, key, key delay, clock, the attract values and, when the replay carries them, the frame's RANDOM bytes */
typedef struct FrameInput {
    uint8_t stick0, stick1, trig0, trig1, console, key, keydelay, clock, drkmsk, colrsh;
    uint16_t nrandom;              /* the RANDOM bytes of this frame, when the replay carries them */
    const uint8_t *random;         /* NULL when it does not: the model (the seed) gives them */
} FrameInput;

/* why a replay is refused */
typedef enum ReplayError {
    REPLAY_OK = 0,
    REPLAY_TOO_SHORT,
    REPLAY_BAD_MAGIC,
    REPLAY_BAD_VERSION,
    REPLAY_BAD_FLAGS,
    REPLAY_BAD_COUNT,
    REPLAY_BAD_FRAME,             /* a frame runs past the end, or bytes are left over */
    REPLAY_BAD_CHECKSUM,
    REPLAY_OPEN_FAILED,
    REPLAY_TOO_BIG,
    REPLAY_WRITE_FAILED,
    REPLAY_FULL                   /* the writer's buffer is full */
} ReplayError;

/* a replay held in memory and the place in it */
typedef struct Replay {
    uint16_t flags;
    uint32_t seed;
    uint32_t nframes;
    uint8_t start_clock;
    const uint8_t *data;           /* the frames */
    size_t size;                   /* their bytes */
    size_t pos;
    uint32_t next;                 /* the number of the next frame */
} Replay;

const char *replay_error_text(ReplayError e);   /* the text of a ReplayError */

/* validate a replay held in memory (every frame is walked once, the checksum is checked) and set it up for replay_next */
ReplayError replay_parse(Replay *r, const uint8_t *buf, size_t size);
ReplayError replay_load(Replay *r, const char *path, uint8_t *buf, size_t cap);     /* through platform/fs.c */

/* the next frame: 1 and `f` filled, or 0 after the last */
int replay_next(Replay *r, FrameInput *f);
void replay_rewind(Replay *r);   /* back to frame 0 */

/* writing */
typedef struct ReplayWriter {
    uint8_t *buf;
    size_t cap, len;
    uint16_t flags;
    uint32_t seed, nframes;
    uint8_t start_clock;
    int over;
} ReplayWriter;

void replay_writer_init(ReplayWriter *w, uint8_t *buf, size_t cap, uint32_t seed, uint16_t flags, uint8_t start_clock);   /* start a replay in `buf`: its seed, flags and power-on clock */
ReplayError replay_writer_add(ReplayWriter *w, const FrameInput *f);   /* append one frame */
ReplayError replay_writer_finish(ReplayWriter *w, size_t *size);                   /* header counts and the trailer */
ReplayError replay_save(const char *path, const uint8_t *buf, size_t size);       /* through platform/fs.c */

#endif
