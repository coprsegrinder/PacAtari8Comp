/* shell/shell.h - the headless shell of the port (stage 80d, docs/51, docs/49 D3): the whole program on a platform that takes its inputs from a replay (or from a front end), a hash of the state after
 * every frame, the picture and the sound of the frame on request, and the little the port keeps between runs: the high score and the options under `save/`, a log under `logs/`, all through platform/fs.c.
 * No window, no sound device and no input library (owner decision D3): a front end gives FrameInput records and takes the buffers (render_to_rgb, audio_frame).  NTSC. */
#ifndef PM_SHELL_SHELL_H
#define PM_SHELL_SHELL_H

#include <stddef.h>
#include <stdint.h>

#include "../app/keyloop.h"
#include "../core/gtia.h"
#include "../core/world.h"
#include "../platform/pokey_random.h"
#include "replay.h"

/* what the shell keeps between runs besides the high score: the RANDOM seed and the power-on clock */
typedef struct ShellOptions {
    uint32_t seed;                 /* the seed of the RANDOM model (a front end plays with it; a replay that carries RANDOM bytes does not need it) */
    uint8_t start_clock;           /* the OS clock at power-on */
} ShellOptions;

/* the whole program on a replay's platform: the World, the key loop, the collision latch, the RANDOM model and the digest of the run */
typedef struct Shell {
    World world;
    KeyLoop kl;
    GtiaLatch latch;
    uint8_t charset[GTIA_CHARSET_SIZE];
    FrameInput in;
    PokeyRandom poke;
    uint32_t stream_pos;           /* the RANDOM bytes of the frame taken so far */
    uint32_t stream_overrun;       /* reads past the end of a frame's recorded RANDOM bytes (a recorded frame never does) */
    uint32_t frame;                /* frames run */
    uint64_t chain;                /* the digest of the run: FNV-1a (64 bit) over the hashes of every frame */
    uint8_t pack[PM_STATE_SIZE];
} Shell;

/* the power-on RAM, `Start`, the main program at its first pass.  `charset`: the 1,024 bytes of the game character set (the collision model draws the maze with it: assets_ram_image + 0x3000) */
void shell_init(Shell *s, const uint8_t charset[GTIA_CHARSET_SIZE], uint32_t seed, uint8_t start_clock);

/* one frame of the whole program with these inputs; returns the hash of the whole state after it (the state of docs/43: the zero page, the screens, the shadows, the pages, the positions) */
uint64_t shell_frame(Shell *s, const FrameInput *in);

uint64_t shell_state_hash(Shell *s);                       /* FNV-1a (64 bit) of world_pack */
uint64_t shell_digest(const Shell *s);

/* what is kept between runs, under the main folder (the folders are made when needed); every function returns 0 on success */
int shell_make_folders(void);
int shell_highscore_load(Shell *s);                        /* save/highscore.pmo into the six cells of the high score ($2039-$203E); 1 when there is none or it is not valid */
int shell_highscore_save(const Shell *s);                  /* only when the six cells hold a score above 0 */
int shell_options_load(ShellOptions *o);                   /* 1 when there is none or it is not valid: the caller keeps its defaults */
int shell_options_save(const ShellOptions *o);
int shell_log(const char *line);                           /* appends a line to logs/shell.log */

/* the six high-score cells as a number: $10 + digit each, $00 (blank: the leading zeros are not drawn) counts as 0; -1 when a cell is neither */
long shell_highscore_value(const Shell *s);

#endif
