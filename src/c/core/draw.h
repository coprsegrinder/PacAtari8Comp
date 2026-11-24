/* core/draw.h - the drawing in port form (docs/44, tools/core_draw.py): what the original's drawing routines leave in the player-missile pages (w->pm), the eight
 * position registers (w->hpos) and the picture buffers (w->picbuf).  Stage 76b holds the part the ghosts need (StepAndDrawEntity); 76c adds the rest of core_draw.py. */
#ifndef PM_CORE_DRAW_H
#define PM_CORE_DRAW_H

#include <stdint.h>

#include "world.h"

#define DRAW_PM_LEN 0x500
#define DRAW_PIC_GHOST 0x10
#define DRAW_PIC_PAC 0x00

/* a byte of the ROM tables ($BA00-$BFFF); an address outside them reads 0 (as core_draw.rom) */
uint8_t draw_rom(int32_t addr);
uint16_t draw_rom_word(int32_t addr);   /* a little-endian word of the ROM tables (as draw_rom) */
/* a store into / a read of the player-missile pages at a 16-bit address; outside $2300-$27FF nothing is modelled (store ignored, read 0) */
void draw_put(World *w, int32_t addr, uint8_t v);
uint8_t draw_get(const World *w, int32_t addr);   /* the read of draw_put's pair */

/* StepAndDrawEntity $B902: `d` is the direction (1 up, 2 down, 4 left, 8 right); any other value does nothing at all.  The step is skipped while DrawOnly is set. */
void draw_ghost(World *w, int x, int a);
void step_and_draw_entity(World *w, int i, int32_t d);   /* see above */

/* Pac-Man's picture, the drawing part of MovePacMan $B179 (from $B2E9): y = twice the index of the picture in PacShapePtrs (0 full disc, 2 right, 4 left, 6 up, 8 down), a = the offset of the mouth frame (0 or $0A) */
void draw_pacman(World *w, int32_t y, int32_t a);
void draw_pacman_full(World *w);   /* the full disc: the mouth closed */
void draw_all_in_place(World *w);                                  /* DrawAllInPlace $AD49 */
/* the pop-up of an eaten ghost (GhostEaten $A886, the picture part) */
void draw_popup(World *w, int x);
/* the death (DeathAnimation $AEF7 / $AF48, the picture part) */
void death_animation_draw(World *w);
void death_animation_clear(World *w);   /* the clearing half of the death animation */
/* the tunnel (ClipEntityAtTunnel $AB57, ClipEntitiesOnTunnelRow $AB48) */
void clip_entity_at_tunnel(World *w, int x, uint8_t a);
void clip_entities_on_tunnel_row(World *w);   /* all entities (ClipEntitiesOnTunnelRow $AB48) */
/* clearing (FillPlayerPages $B100, ClearPlayerMemory $B0F1) */
void fill_player_pages(World *w, uint8_t a, int x);
void clear_player_memory(World *w);   /* ClearPlayerMemory $B0F1 */

#endif
