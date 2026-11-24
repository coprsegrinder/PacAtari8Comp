/* core/pacman.h - Pac-Man's movement in C (stage 76c, docs/44).  Twin of tools/core_pacman.py.  Pac-Man is entity 4: EntityX[4], EntityY[4], EntityDir[4]. */
#ifndef PM_CORE_PACMAN_H
#define PM_CORE_PACMAN_H

#include "constants.h"
#include "world.h"

#define PACMAN_TUNNEL_LEFT TUNNEL_X_LEFT
#define PACMAN_TUNNEL_RIGHT TUNNEL_X_RIGHT
#define PACMAN_MAZE_PTR_AFTER_LEFT MAZE_PTR_LEFT_EXIT_LO
#define PACMAN_MAZE_PTR_AFTER_RIGHT MAZE_PTR_RIGHT_EXIT_LO
#define PACMAN_ROW MAZE_ROW_STRIDE

void read_joystick(World *w, uint8_t mask);   /* the stick of the player on turn: the wanted direction and, when the maze allows it, the direction at once */
void move_pacman(World *w);                   /* MovePacMan $B179 with the drawing of the mouth and the missiles */

#endif
