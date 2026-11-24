/* render/interp.h - the in-between pictures of the FPS option (docs/69).  Portable C99, no allocation except InterpOut's two pictures.
 *
 * The game makes one new picture every 1/59.92 s.  A front end that shows more (or other) pictures a second than that needs pictures of the moments between two game frames.  They are invented here,
 * by the port itself and not by the graphics driver or the monitor, in the one way that keeps the picture the original's:
 *   - the PLAYFIELD (maze, dots, the text) is not moved or mixed: it is the playfield of the nearer of the two game frames, so it changes at the moments the game changed it;
 *   - the PLAYERS AND MISSILES (the four ghosts, and Pac-Man with the pop-up score, which the game draws with the missiles) are the objects that move.  Each is found in the two frames, the way it moved
 *     between them is measured (by matching its pixels: a shift of at most INTERP_MAX_MOVE pixels), and the object of the nearer frame is drawn the fraction of that move it is away from its frame;
 *   - an object that is in one frame only, or moved further than INTERP_MAX_MOVE (a ghost through the tunnel, a ghost back at the house), or does not match, is not moved: it is the nearer frame's;
 *   - nothing is mixed: every pixel of an in-between picture is a colour the game's own rules (the priority of GTIA, the colour registers of that line) give it, and the picture is made at the size it is
 *     shown at, so a sprite can stand a fraction of a game pixel away from where the game put it (nearest pixel, never smoothed).
 * With phi = 0 the picture is exactly the nearest-pixel picture of frame A, with phi = 1 that of frame B. */
#ifndef PM_RENDER_INTERP_H
#define PM_RENDER_INTERP_H

#include <stdint.h>

#include "render.h"

#define INTERP_OBJECTS 5          /* the four players, and the four missiles together (Pac-Man's body and the pop-up score) */
#define INTERP_MAX_MOVE 8         /* the longest move between two frames that is a move (picture pixels); a longer one is a jump */

/* where an object is in a frame */
typedef struct InterpObject {
    int present;
    int x0, y0, x1, y1;           /* the bounding box, x1 and y1 not included */
    int count;                    /* its pixels */
} InterpObject;

/* a game frame with what the in-between pictures need */
typedef struct InterpFrame {
    uint8_t colour[RENDER_W * RENDER_H];
    RenderLayers layers;
    InterpObject obj[INTERP_OBJECTS];
} InterpFrame;

/* how each object moved from one frame to the next one: `ok` is 0 for an object that is in one frame only, jumped, or did not match */
typedef struct InterpPair {
    int ok[INTERP_OBJECTS];
    int dx[INTERP_OBJECTS], dy[INTERP_OBJECTS];
} InterpPair;

/* the picture shown: BGRA, ow x oh, made of the nearest frame's picture with the moving objects drawn again */
typedef struct InterpOut {
    int ow, oh;
    uint32_t *base;               /* the nearest-pixel picture of the nearest frame */
    uint32_t *work;               /* base with the moving objects at their in-between places: what is shown */
    unsigned long base_id;        /* which frame base is of */
    int base_valid;
    int nrect;
    int rect[INTERP_OBJECTS][4];  /* the places on work that are not base (x0, y0, x1, y1) */
    int last_offx[INTERP_OBJECTS], last_offy[INTERP_OBJECTS];   /* the offsets work was made with (1/1024 picture pixel) */
    uint32_t lut[256];            /* the GTIA colour byte as BGRA */
} InterpOut;

/* after render_frame_layers: finds the objects in f->layers.cov */
void interp_prepare(InterpFrame *f);

/* how the objects of `a` moved to `b` */
void interp_pair(const InterpFrame *a, const InterpFrame *b, InterpPair *p);

/* what changed on `work` since the previous picture: all of it (`full`), or the rectangles r[i] = x0, y0, x1, y1 (x1 and y1 not included) */
typedef struct InterpDirty {
    int full;
    int n;
    int r[2 * INTERP_OBJECTS][4];
} InterpDirty;

/* a picture of ow x oh; 0 on success, 1 when there is no memory */
int interp_out_init(InterpOut *o);
int interp_out_size(InterpOut *o, int ow, int oh);   /* the pictures are ow x oh from now on (nothing is done when they already are); 1 when there is no memory */
void interp_out_free(InterpOut *o);                  /* gives the two pictures back */

/* the picture at `phi` (0 to 1) between frame a (number id_a) and frame b (number id_a + 1; b and pair may be NULL: the picture of a).  Makes o->work and says what differs from what the previous call
 * made (everything when the nearest frame changed or the size did), so that only that needs to be drawn to the window */
void interp_render(InterpOut *o, const InterpFrame *a, const InterpFrame *b, const InterpPair *pair, double phi, unsigned long id_a, InterpDirty *d);

#endif
