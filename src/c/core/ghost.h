/* core/ghost.h - the ghost state machine and the ghost house in C (stage 76b, docs/44).  Twin of tools/core_ghost.py, function by function.
 * `i` is the ghost (0-3) unless a function says otherwise; entity 4 is Pac-Man.  `rnd` supplies the POKEY RANDOM values. */
#ifndef PM_CORE_GHOST_H
#define PM_CORE_GHOST_H

#include "constants.h"
#include "random_feed.h"
#include "world.h"

#define GHOST_PATROL_TIME PATROL_TIME
#define GHOST_CORNER GS_CORNER
#define GHOST_CHASE GS_CHASE
#define GHOST_PATROL_TRAVEL GS_PATROL_TRAVEL
#define GHOST_PATROL GS_PATROL
#define GHOST_DOOR_X DOOR_X
#define GHOST_DOOR_Y DOOR_Y

/* the lattice and the steering */
uint8_t junction_lookup(const World *w, int i, int *on_lattice_point);   /* JunctionLookup $B48E */
void steer_to_target(World *w, int i, uint8_t mask, RandomFeed *rnd);    /* SteerToTarget $B999 */
void step_entity(World *w, int i, int32_t d);                            /* StepAndDrawEntity $B902 (draw.c) */

/* the sight test, the timers, the forced chase */
int ghost_sees(const World *w, int i);                                    /* the test of GhostSeesPacMan $BA19 without its effect */
void ghost_sees_pacman(World *w, int i);                                  /* GhostSeesPacMan $BA19 */
void force_chase(World *w, int x);                                        /* ForceChase $B616 */
void chase_timer_siren_sight(World *w);                                   /* ChaseTimerSirenSight $B5C7 */

/* the behaviour of a ghost by its state */
void ghost_behaviour(World *w, int i, RandomFeed *rnd);                   /* GhostBehaviour $B7F5 */
void ghost_start_route(World *w, int i, RandomFeed *rnd);                 /* $B826 */
void ghost_select_patrol(World *w, int i, RandomFeed *rnd);               /* $B84B */
void ghost_patrol_travel(World *w, int i, RandomFeed *rnd);               /* $B87B */
void ghost_patrol(World *w, int i, RandomFeed *rnd);                      /* $B898 */
void ghost_go_to_corner(World *w, int i, RandomFeed *rnd);                /* $B8C5 */
void ghost_chase(World *w, int i, RandomFeed *rnd);                       /* $B8EB */

/* the ghost house (house.c) */
void house_bob_step(World *w, int i);                                     /* $B7D6 */
void house_leave_step(World *w, int i);                                   /* $B738 */
void house_leave_ghost2(World *w, int i);                                 /* $B76D */
void house_leave_ghost3(World *w, int i);                                 /* $B777 */
void house_leave(World *w, int i);
void house_enter_step(World *w, int i);                                   /* $B781 */
void house_waiting_tick(World *w);                                        /* $B7A5 */

#endif
