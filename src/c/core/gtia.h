/* core/gtia.h - the collision geometry of the GTIA in C (stage 77a, docs/50).  Twin of tools/gtia_collisions.py, the latch of tools/platform_iface.py (GtiaCollisions) and core_draw.scene.
 *
 * What the game reads in $D000-$D00F (the contact test: M1PL and M2PL; the bonus pick-up: M2PF) is computed by the hardware from the pictures of the players and missiles and the playfield; the port
 * has no such hardware and computes the registers here from the scene: the eight positions (HPOSP0-3, HPOSM0-3 in colour clocks), the player-missile pages (one byte a scan line) and the maze cells with
 * the character set.  SIZEP / SIZEM are 0 in the game (a player 8 clocks wide, a missile 2 wide).  Rules (verified on the real GTIA, docs/50): see tools/gtia_collisions.py. */
#ifndef PM_CORE_GTIA_H
#define PM_CORE_GTIA_H

#include <stdint.h>

#include "world.h"

#define GTIA_SCREEN_X0 48        /* the first colour clock of the playfield */
#define GTIA_MAZE_LINE0 40       /* the first scan line of the first mode-4 row, as the player-missile pages count */
#define GTIA_MAZE_ROWS 23
#define GTIA_MAZE_COLS 40
#define GTIA_MAZE_CELLS (GTIA_MAZE_ROWS * GTIA_MAZE_COLS)
#define GTIA_CHARSET_SIZE 1024   /* 128 glyphs of 8 bytes (the bytes at $3000) */
#define GTIA_VISIBLE_LO 34       /* the colour clocks at which an object's pixel counts */
#define GTIA_VISIBLE_HI 221
#define GTIA_LINE_LO 8           /* the scan lines at which an object's row counts */
#define GTIA_LINE_HI 247

/* a scene: hpos = [P0, P1, P2, P3, M0, M1, M2, M3]; the five pages are 256 bytes each (the missile page, then players 0-3); cells = 920 screen codes; charset = 1,024 bytes */
typedef struct GtiaScene {
    const uint8_t *hpos;
    const uint8_t *missile_page;
    const uint8_t *player_pages[4];
    const uint8_t *cells;
    const uint8_t *charset;
} GtiaScene;

/* the sixteen collision registers $D000-$D00F of a scene (M0PF..M3PF, P0PF..P3PF, M0PL..M3PL, P0PL..P3PL); `visible` / `lines` are the windows (the model's defaults above; the tests move them) */
void gtia_collision_registers(const GtiaScene *s, int visible_lo, int visible_hi, int line_lo, int line_hi, uint8_t out[16]);

/* the scene the World leaves on the screen (core_draw.scene): positions, the five pages and the maze cells; `charset` is the game's character set */
void gtia_scene_of_world(const World *w, const uint8_t charset[GTIA_CHARSET_SIZE], GtiaScene *s);

/* the latch (platform_iface.GtiaCollisions): the registers hold every overlap shown since the last HITCLR ($D01E).  `latch` is what the game reads at the start of a frame;
 * after the frame, gtia_latch_frame_done clears it when the frame wrote HITCLR (it is in the World's chip-write log) and ORs in the overlaps of the scene the frame left. */
typedef struct GtiaLatch {
    uint8_t reg[16];
} GtiaLatch;

void gtia_latch_init(GtiaLatch *l);   /* every register 0 */
void gtia_latch_frame_done(GtiaLatch *l, const World *w, const uint8_t charset[GTIA_CHARSET_SIZE]);   /* after a frame: cleared if the frame wrote HITCLR, then the overlaps of the scene it left are ORed in */
void gtia_latch_to_world(const GtiaLatch *l, World *w);   /* w->collide = the latch: the input of the next frame */

#endif
