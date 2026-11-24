/* tests/constants_check.c - stage 94: core/constants.h (the named constants of the original, generated from docs/31) compiles together with every other header of the core and the application layer (no name clashes), and
 * a few of its values are the ones the chapters give (the door square, the tunnel, the bit masks of GhostState).  The values themselves are checked against the ROM's immediate operands by tests/test_constants.py. */
#include <stdio.h>

#include "../app/dispatch.h"
#include "../app/keyloop.h"
#include "../core/constants.h"
#include "../core/ghost.h"
#include "../core/play.h"
#include "../core/ref.h"
#include "../core/score.h"
#include "../core/sound.h"
#include "../core/world.h"

int main(void)
{
    int bad = 0;

    if (PM_NAMED_CONSTANTS != 51) {
        printf("constants_check: %d constants, expected 51\n", PM_NAMED_CONSTANTS);
        bad++;
    }
    if (DOOR_X != 0x7C || DOOR_Y != 0x64 || TUNNEL_Y != 0x74 || TUNNEL_X_LEFT != 0x2A || TUNNEL_X_RIGHT != 0xCA) {
        printf("constants_check: a position of the maze is not the one of docs/18, docs/20\n");
        bad++;
    }
    if ((GS_EYES & 0x40) == 0 || (GS_EYES_AT_DOOR & 0x40) == 0 || (GS_CHASE | GS_PATROL_TRAVEL | GS_PATROL | GS_CORNER) != 0x3A || GS_FRIGHTENED_BIT != 0x80) {
        printf("constants_check: the ghost states (bit 6 marks an eaten ghost, bit 7 a frightened one)\n");
        bad++;
    }
    if (DIR_UP != 1 || DIR_DOWN != 2 || DIR_LEFT != 4 || DIR_RIGHT != 8) {
        printf("constants_check: the direction bits\n");
        bad++;
    }
    if (LEVEL_COMPLETE_SET != 1 || REF_DOTS_PER_BOARD != 0x0104) {
        printf("constants_check: the level-complete flag, or the dot count of a completed board ($0104)\n");
        bad++;
    }
    if (bad == 0) {
        printf("constants_check: OK (%d constants)\n", PM_NAMED_CONSTANTS);
    }
    return bad != 0;
}
