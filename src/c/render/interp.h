/* render/interp.h - the in-between pictures of the FPS option (docs/69).  Portable C99, no allocation except InterpOut's two pictures.
 *
 * The game makes one new picture every 1/59.92 s, but it moves each ghost and Pac-Man in steps of two pixels every second or third frame (its own speed pacing), so its motion is a staircase.  A front end
 * that shows more (or other) pictures a second than the game has frames needs pictures of the moments in between, and to look smooth they have to glide through the steps.  They are invented here, by the
 * port itself and not by the graphics driver or the monitor, in the one way that keeps the picture the original's:
 *   - the PLAYFIELD (maze, dots, the text) is not moved or mixed: it is the playfield of the nearer game frame, so it changes at the moments the game changed it;
 *   - the PLAYERS AND MISSILES (the four ghosts, and Pac-Man with the pop-up score, which the game draws with the missiles) are the objects that move.  Each is found in the frames, how it moved from each
 *     frame to the next is measured (by matching its pixels: a shift of at most INTERP_MAX_MOVE), and the place it is drawn at is on the straight way from the place of one of its moves to the place of the
 *     next one, so that it glides the whole time between two steps of the game and is where the game put it at the moment the game did.  The game is a frame or two ahead of the picture, which is often the
 *     next step already; when it is not, the object goes on the way its last step went, no further than one step;
 *   - an object that appears, vanishes, jumps further than INTERP_MAX_MOVE (a ghost through the tunnel, back at the house) or does not match is not moved: it is the nearer frame's;
 *   - nothing is mixed: every pixel of an in-between picture is a colour the game's own rules (the priority of GTIA, the colour registers of that line) give it, and the picture is made at the size it is
 *     shown at, so a sprite can stand a fraction of a game pixel away from where the game put it (nearest pixel, never smoothed). */
#ifndef PM_RENDER_INTERP_H
#define PM_RENDER_INTERP_H

#include <stdint.h>

#include "render.h"

#define INTERP_OBJECTS 5          /* the four players, and the four missiles together (Pac-Man's body and the pop-up score) */
#define INTERP_MAX_MOVE 8         /* the longest move between two frames that is a move (picture pixels); a longer one is a jump */
#define INTERP_SIMILAR 45         /* two shapes are the same object moved only when this share (percent) of their joined pixels is on both: a ghost and the eyes it becomes, Pac-Man and the score that takes his place are not */

/* the share above, a variable only so that the audit (tests/interp_audit.c) can try other values; the program leaves it alone */
extern int interp_similar_percent;

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
    int px[INTERP_OBJECTS], py[INTERP_OBJECTS];   /* where each object is, counted from the start of its run of frames (the sum of the matched moves; see interp_follow) */
    int run[INTERP_OBJECTS];                      /* which run: a new one starts when the object appears or jumps */
    int mv[INTERP_OBJECTS];                       /* 1 when the object moved since the frame before */
} InterpFrame;

/* how each object moved from one frame to the next one: `ok` is 0 for an object that is in one frame only, jumped, or did not match */
typedef struct InterpPair {
    int ok[INTERP_OBJECTS];
    int dx[INTERP_OBJECTS], dy[INTERP_OBJECTS];
    int similar[INTERP_OBJECTS];  /* the share of the joined pixels of the two shapes that is on both, at the best shift (percent) */
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
    int still;                    /* set by the caller: the picture is the nearer frame as the game made it, no object moved (the choices of fewer pictures a second than the game makes) */
} InterpOut;

/* after render_frame_layers: finds the objects in f->layers.cov */
void interp_prepare(InterpFrame *f);

/* after interp_prepare, with the frame before it (NULL for the first): matches the objects of the two frames and keeps where each is (px, py, run, mv) */
void interp_follow(InterpFrame *cur, const InterpFrame *prev);

/* how a frame is found by its number (NULL when it is not kept) */
typedef const InterpFrame *(*InterpGet)(void *ctx, unsigned long id);

/* where object k is drawn at the game time t, in the units of the frames' px and py (the audit looks at it); 0 when the object is not in a run at t */
int interp_place(InterpGet get, void *ctx, double t, unsigned long newest, int k, double *x, double *y);

/* how the objects of `a` moved to `b` */
void interp_pair(const InterpFrame *a, const InterpFrame *b, InterpPair *p);

#define INTERP_MAX_RECTS 48       /* 30 bands of the picture that changed when the nearer frame changes, and the places of the objects before and after */

/* what changed on `work` since the previous picture: all of it (`full`), or the rectangles r[i] = x0, y0, x1, y1 (x1 and y1 not included) */
typedef struct InterpDirty {
    int full;
    int n;
    int r[INTERP_MAX_RECTS][4];
} InterpDirty;

/* a picture of ow x oh; 0 on success, 1 when there is no memory */
int interp_out_init(InterpOut *o);
int interp_out_size(InterpOut *o, int ow, int oh);   /* the pictures are ow x oh from now on (nothing is done when they already are); 1 when there is no memory */
void interp_out_free(InterpOut *o);                  /* gives the two pictures back */

/* the picture at the game time t (in frames: 5.5 is half way from frame 5 to frame 6), the frames up to `newest` being made.  The playfield is that of the nearer frame; the ghosts and Pac-Man are drawn
 * where they are on the way between the moves of the game (their steps are every second or third frame, so they glide the whole time between two steps), which needs the next move when it is made, and the
 * way of the move before it when it is not.  Makes o->work and says what differs from what the previous call made (everything when the nearest frame changed or the size did), so that only that needs to
 * be drawn to the window.  o->base_id is the number of the nearer frame */
void interp_render(InterpOut *o, InterpGet get, void *ctx, double t, unsigned long newest, InterpDirty *d);

/* the picture made k times as wide (every k pixels across are one pixel of the result): the colours of each group are averaged, per channel.  With k = 1 it is a copy.  What a CRT shader is given: the picture
 * is made at k times the width so that an object can stand a fraction of a game pixel off its place, and this brings it back to the Atari's width, the edges of a moving object averaged over 1/k of a pixel */
void interp_box_x(const uint32_t *src, int src_w, int h, int k, uint32_t *dst);

#endif
