/* render/render.h - the picture of the screen from the World (stage 80b, docs/42, docs/35, docs/47).
 *
 * What the original's hardware makes of the World, one frame: ANTIC runs the display list the game gave it (DLIST shadow; the two lists of the ROM are read from the ROM window, modes 2, 4, 6, 7
 * and blank lines, LMS, JVB, the display-list-interrupt bit), fetches the screen rows from the screen memory of the World (the maze band, the status rows, the title screen), draws the characters
 * from the character set CHBASE selects, the display-list interrupt handlers of the game change the colour registers and CHBASE between the bands (what DliHandler1 and DliHandler2 do, read from the
 * code: docs/35), and GTIA puts the five player-missile objects over the playfield by PRIOR and gives every pixel its colour.  The result is a picture of colour bytes (hue, luminance), and with the
 * measured NTSC palette (palette.h) an RGB picture.  NTSC only.
 *
 * The picture is RENDER_W x RENDER_H hires pixels: scan lines 8-247 (240 lines), colour clocks 32-223 (192 clocks of 2 pixels).  The playfield starts at colour clock 48.
 *
 * Not modelled (the game never uses it): narrow and wide playfield, double-line player-missile resolution, the player and missile size registers, the multicolour player bit of PRIOR, the
 * overlap bits, fine scrolling, vertical reflection.  A frame that asks for them is drawn as if it did not (the checks in tests/test_render.py show that the game's frames do not).
 *
 * Timing: the colour registers at the start of a frame are the OS shadows of the PREVIOUS frame (the OS copies them to GTIA in the vertical blank, before the game's handler changes them);
 * the screen memory and the player-missile memory are the ones of this frame.  So render_frame remembers the colours of each call for the next: the first call after render_reset uses the
 * World's own shadows.  Pure C99: no file, no allocation, no global state (everything is in the Renderer).
 */
#ifndef PM_RENDER_RENDER_H
#define PM_RENDER_RENDER_H

#include <stdint.h>

#include "../core/world.h"

#define RENDER_W 384
#define RENDER_H 240
#define RENDER_FIRST_LINE 8     /* the scan line of picture row 0 */
#define RENDER_FIRST_CLOCK 32   /* the colour clock of picture column 0 (two pixels a clock) */

/* the renderer's state: the three character sets and the colour registers latched for the next frame */
typedef struct Renderer {
    uint8_t chargen_title[1024];   /* $1800-$1BFF */
    uint8_t chargen_game[1024];    /* $3000-$33FF */
    uint8_t chargen_font[1024];    /* $E000-$E3FF: the OS character set */
    uint8_t latched[9];            /* the colour registers at the start of the next frame: COLPF0-3, COLBK, COLPM0-3 (after the attract-mode transform) */
    uint8_t latched_chbase;
    uint8_t have_latched;
} Renderer;

/* `image` is the 64 KB image of the assets (assets_ram_image): the character sets are cut out of it */
void render_init(Renderer *r, const uint8_t image[65536]);

/* forget the colours of the previous frame: the next frame uses the shadows of its own World */
void render_reset(Renderer *r);

/* draw one frame into `colour` (RENDER_W * RENDER_H bytes, row by row: the GTIA colour byte of every pixel).  `w->hpos` are the positions the game wrote (HPOSP0-3, HPOSM0-3). */
void render_frame(Renderer *r, const World *w, uint8_t colour[RENDER_W * RENDER_H]);

/* what a frame is made of before the players and missiles are put over the playfield (docs/69: the in-between pictures of the FPS option are made from it) */
typedef struct RenderLayers {
    uint8_t pri[RENDER_W * RENDER_H];   /* the playfield of each pixel: 0 background, 1-4 playfield 0-3 */
    uint8_t col[RENDER_W * RENDER_H];   /* the colour byte of that playfield pixel */
    uint8_t cov[RENDER_W * RENDER_H];   /* the players and missiles on each pixel: bit k player k, bit 4 + k missile k */
    uint8_t regs[RENDER_H][9];          /* COLPF0-3, COLBK, COLPM0-3 at each line (the display-list interrupts change them between the rows) */
    uint8_t prior;                      /* PRIOR: the order of players and playfields */
} RenderLayers;

/* render_frame, and the layers of the frame as well when `layers` is not NULL (`colour` is the same either way) */
void render_frame_layers(Renderer *r, const World *w, uint8_t colour[RENDER_W * RENDER_H], RenderLayers *layers);

/* the colour byte GTIA gives a pixel from its layers: the same rule render_frame uses */
uint8_t render_compose(const uint8_t regs[9], uint8_t prior, uint8_t pri, uint8_t col, uint8_t cov);

/* the same picture in RGB (3 bytes a pixel) through the measured NTSC palette */
void render_to_rgb(const uint8_t colour[RENDER_W * RENDER_H], uint8_t rgb[RENDER_W * RENDER_H * 3]);

#endif
