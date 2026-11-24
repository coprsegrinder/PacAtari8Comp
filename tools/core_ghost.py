"""OV-67 (stage 66): THE GHOST STATE MACHINE IN PORT FORM - the behaviour of every ghost state, the sight test, the chase timer and the forced chase, the movement step and the ghost house, written on the named
World of tools/core_world.py (no addresses, no memory image).  Each function is the logic of one ROM routine (named in its docstring); the drawing (the player-missile pages) and the sound calls are left out.
tools/check_ghost.py runs each function against the ROM routine and compares the whole zero page, the maze and the status rows.  `rnd` is an iterator of POKEY RANDOM values.
Entities 0-3 are the ghosts, 4 is Pac-Man.  Directions 1 up, 2 down, 4 left, 8 right."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_draw as D  # noqa: E402
import core_ref as R  # noqa: E402
import core_tables as T  # noqa: E402

PATROL_TIME = 0x96
CORNER_STATE, CHASE_STATE, PATROL_TRAVEL, PATROL, START_ROUTE = 0x20, 0x02, 0x08, 0x10, 0x01
DOOR_X, DOOR_Y = 0x7C, 0x64


def rom_word(addr):
    return T.rom(addr) | T.rom(addr + 1) << 8


# ------------------------------------------------------------------------------------------------ the lattice and the steering
def junction_lookup(w, i):
    """JunctionLookup $B48E: the exits at the entity's lattice point -> (mask, on_lattice_point)"""
    return R.junction_exits(i == 4, w.EntityX[i], w.EntityY[i], w.EntityDir[i], w.GhostState[i] if i < 4 else 0)


def steer_to_target(w, i, mask, rnd):
    """SteerToTarget $B999: fills WantVert / WantHoriz and sets the direction"""
    state = w.GhostState[i]
    wv, wh = R.wants(w.EntityY[i], w.EntityX[i], w.TargetY[i], w.TargetX[i], state)
    w.WantVert[i], w.WantHoriz[i] = wv, wh
    w.EntityDir[i] = R.steer(w.EntityY[i], w.EntityX[i], w.TargetY[i], w.TargetX[i], state, mask, rnd)


def step_entity(w, i, d=None):
    """StepAndDrawEntity $B902 with the drawing (core_draw, OV-69): one step in the direction d (default EntityDir; 1 pixel sideways, 2 vertically) unless DrawOnly is set"""
    D.step_and_draw_entity(w, i, d)


# ------------------------------------------------------------------------------------------------ the sight test
def _scan_up(base, y, limit):
    """the loop `lda base,y / cmp #$FF / beq found / cmp limit / bcs stop / iny / bne`: -> (value, hit_ff)"""
    while True:
        v = T.rom(base + y)
        if v == 0xFF:
            return v, True
        if v >= limit:
            return v, False
        y = (y + 1) & 0xFF
        if y == 0:
            return v, False


def sees(w, i):
    """the test of GhostSeesPacMan $BA19 without its effect: a ghost on Pac-Man's row or column, facing him, with no blocker between (the lists read with their run-on)"""
    gx, gy, d = w.EntityX[i], w.EntityY[i], w.EntityDir[i]
    px, py = w.EntityX[4], w.EntityY[4]
    ys = [T.rom(0xBB83 + k) for k in range(10)]
    xs = [T.rom(0xBB8D + k) for k in range(10)]
    if gy == py:
        y = next((k for k in range(9, -1, -1) if ys[k] == py), None)
        if y is None:
            return False
        if gx < px:
            if d != 8:
                return False
            v, ff = _scan_up(0xBBB8, y, gx)
            return True if ff else v >= px
        if d != 4:
            return False
        v, ff = _scan_up(0xBBB8, y, px)
        return True if ff else v >= gx
    if gx == px:
        y = next((k for k in range(9, -1, -1) if xs[k] == px), None)
        if y is None:
            return False
        if gy >= py:
            if d != 1:
                return False
            v, ff = _scan_up(0xBBD8, y, py)
            return True if ff else v >= gy
        if d != 2:
            return False
        v, ff = _scan_up(0xBBD8, y, gy)
        return True if ff else v >= py
    return False


def ghost_sees_pacman(w, i):
    """GhostSeesPacMan $BA19: the ghost goes to chase for 160 x 8 jiffies; ghost 2 reacts only while RTCLOK2 bit 7 is clear"""
    if sees(w, i) and not (i == 2 and w.RTCLOK2 & 0x80):
        w.GhostState[i] = CHASE_STATE
        w.ChaseTimer = 0xA0


# ------------------------------------------------------------------------------------------------ timers, siren, forced chase
def force_chase(w, x):
    """ForceChase $B616: ghosts x .. 0 in patrol travel, patrol or corner go to chase; the chase timer is left at $FF"""
    for k in range(x, -1, -1):
        if w.GhostState[k] in (0x08, 0x10, 0x20):
            w.GhostState[k] = CHASE_STATE
    w.ChaseTimer = 0xFF


def chase_timer_siren_sight(w):
    """ChaseTimerSirenSight $B5C7: every 8th jiffy the chase timer falls; the dots eaten set the siren step and, late in the board ($E0 / $F0 dots), force the chase; patrolling ghosts look for Pac-Man"""
    if w.RTCLOK2 & 7 == 0 and w.ChaseTimer != 0:
        w.ChaseTimer -= 1
    p = w.CurrentPlayer
    lo, hi = w.DotsEatenLo[p], w.DotsEatenHi[p]
    if hi != 0 or lo >= 0xF0:
        force_chase(w, 3)
        step = 5
    elif lo >= 0xE0:
        force_chase(w, 2)
        step = 4
    elif lo >= 0xB0:
        step = 3
    else:
        step = 2
    w.SirenStep = step
    for g in range(3, -1, -1):
        if w.GhostState[g] in (0x08, 0x10):
            ghost_sees_pacman(w, g)


# ------------------------------------------------------------------------------------------------ the behaviour of a ghost by its state
def ghost_behaviour(w, i, rnd):
    """GhostBehaviour $B7F5: one move of ghost i by its state"""
    s = w.GhostState[i]
    if s & 0x80:                                    # frightened: bit 2 clear -> flee (chase steering), bit 2 set -> stands
        if (s >> 2) & 1:
            return
        return ghost_chase(w, i, rnd)
    if s == 0x01:
        return ghost_start_route(w, i, rnd)
    if s == 0x02:
        return ghost_chase(w, i, rnd) if w.ChaseTimer != 0 else ghost_go_to_corner(w, i, rnd)
    if s == 0x08:
        return ghost_patrol_travel(w, i, rnd)
    if s == 0x10:
        return ghost_patrol(w, i, rnd)
    if s == 0x20:
        return ghost_go_to_corner(w, i, rnd)


def ghost_start_route(w, i, rnd):
    """GhostStartRoute $B826: follow the start route one junction at a time; its end ($0F) sends ghosts 1-3 to a patrol and ghost 0 to a chase with ChaseTimer $50"""
    mask, on = junction_lookup(w, i)
    if on:
        w.StartRouteStep[i] = (w.StartRouteStep[i] + 1) & 0xFF
    d = T.ram((rom_word(0xBCE6 + 2 * i) + w.StartRouteStep[i]) & 0xFFFF)
    if d == 0x0F:
        if i != 0:
            return ghost_select_patrol(w, i, rnd)
        w.ChaseTimer = 0x50
        w.GhostState[0] = CHASE_STATE
        return ghost_chase(w, i, rnd)
    w.EntityDir[i] = d
    step_entity(w, i)


def ghost_select_patrol(w, i, rnd):
    """GhostSelectPatrol $B84B: a random one of the 16 patrol routes (RANDOM AND $0F), its start junction as the target, 20 s of patrol"""
    w.GhostState[i] = PATROL_TRAVEL
    w.PatrolStep[i] = 0
    route = next(rnd) & 0x0F
    w.PatrolRoute[i] = route
    w.TargetX[i] = T.rom(0xBCEE + 2 * route)
    w.TargetY[i] = T.rom(0xBCEE + 2 * route + 1)
    w.GhostTimer[i] = PATROL_TIME
    return ghost_patrol_travel(w, i, rnd)


def ghost_patrol_travel(w, i, rnd):
    """GhostPatrolTravel $B87B: walk to the start junction of the chosen route; on arrival the state becomes patrol"""
    if w.GhostTimer[i] == 0:
        return ghost_go_to_corner(w, i, rnd)
    mask, on = junction_lookup(w, i)
    if not on:
        return step_entity(w, i)
    steer_to_target(w, i, mask, rnd)
    if w.WantHoriz[i] or w.WantVert[i]:
        return step_entity(w, i)
    w.GhostState[i] = PATROL
    return _read_patrol_route(w, i)


def ghost_patrol(w, i, rnd):
    """GhostPatrol $B898: one direction nibble per junction of the route; the route is a loop (a 0 ends it and starts again)"""
    if w.GhostTimer[i] == 0:
        return ghost_go_to_corner(w, i, rnd)
    mask, on = junction_lookup(w, i)
    if on:
        w.PatrolStep[i] = (w.PatrolStep[i] + 1) & 0xFF
    return _read_patrol_route(w, i)


def _read_patrol_route(w, i):
    off = T.rom(0xBD16 + w.PatrolRoute[i])
    d = T.ram(0x06AE + ((off + w.PatrolStep[i]) & 0xFF))
    if d == 0:
        w.PatrolStep[i] = 0
        d = T.ram(0x06AE + off)
    w.EntityDir[i] = d
    step_entity(w, i)


def ghost_go_to_corner(w, i, rnd):
    """GhostGoToCorner $B8C5: head for the ghost's corner; on arrival choose a new patrol"""
    w.GhostState[i] = CORNER_STATE
    w.TargetX[i] = T.rom(0xBD0E + 2 * i)
    w.TargetY[i] = T.rom(0xBD0E + 2 * i + 1)
    mask, on = junction_lookup(w, i)
    if not on:
        return step_entity(w, i)
    steer_to_target(w, i, mask, rnd)
    if w.WantHoriz[i] or w.WantVert[i]:
        return step_entity(w, i)
    return ghost_select_patrol(w, i, rnd)


def ghost_chase(w, i, rnd):
    """GhostChase $B8EB: the target is Pac-Man (a frightened ghost steers away from it)"""
    w.TargetX[i] = w.EntityX[4]
    w.TargetY[i] = w.EntityY[4]
    mask, on = junction_lookup(w, i)
    if on:
        steer_to_target(w, i, mask, rnd)
    step_entity(w, i)


# ------------------------------------------------------------------------------------------------ the ghost house
def house_bob_step(w, i):
    """HouseBobStep $B7D6: a waiting ghost moves between y $70 and $78"""
    if w.EntityDir[i] == 1:
        if w.EntityY[i] == 0x70:
            w.EntityDir[i] = 2
    elif w.EntityY[i] == 0x78:
        w.EntityDir[i] = 1
    step_entity(w, i)


def _set_dir_step(w, i, d):
    w.EntityDir[i] = d
    step_entity(w, i)


def house_leave_step(w, i):
    """HouseLeaveStep $B738: up the door column; at the door row the ghost leaves the house (a frightened one also loads ChaseTimer with its state: a quirk of the code)"""
    if w.EntityY[i] != DOOR_Y:
        return _set_dir_step(w, i, 1)
    s = w.GhostState[i]
    if s == 0:
        a, d = 1, 4
    else:
        a = (s & 0x80) | 2
        if a & 0x80:
            w.ChaseTimer = a
            d = 8
        else:
            d = 4
    w.EntityDir[i] = d
    w.GhostState[i] = a


def house_leave_ghost2(w, i):
    """HouseLeaveGhost2 $B76D: ghost 2 walks right to the door column first"""
    return house_leave_step(w, i) if w.EntityX[i] == DOOR_X else _set_dir_step(w, i, 8)


def house_leave_ghost3(w, i):
    """HouseLeaveGhost3 $B777: ghost 3 walks left to the door column first"""
    return house_leave_step(w, i) if w.EntityX[i] == DOOR_X else _set_dir_step(w, i, 4)


def house_leave(w, i):
    return house_leave_ghost3(w, i) if i == 3 else house_leave_ghost2(w, i) if i == 2 else house_leave_step(w, i)


def house_enter_step(w, i):
    """HouseEnterStep $B781: an eaten ghost goes down to the floor (y $74); ghosts 2 and 3 move sideways to x $70 / $88; then the eaten bits are cleared and the ghost's colour comes back"""
    if w.EntityY[i] != 0x74:
        return _set_dir_step(w, i, 2)
    if i == 2 and w.EntityX[i] != 0x70:
        return _set_dir_step(w, i, 4)
    if i == 3 and w.EntityX[i] != 0x88:
        return _set_dir_step(w, i, 8)
    w.GhostState[i] &= 0x0F
    w.shadow[0xC0 + i] = T.rom(0xBBE2 + i)           # PCOLR0 + i


def house_waiting_tick(w):
    """HouseWaitingTick $B7A5 (every 4th jiffy): ghosts 1-3 in the house count their release timer down and bob; at 0 they leave"""
    for i in (1, 2, 3):
        if w.GhostState[i] & 0x7F:
            continue
        if w.GhostTimer[i]:
            w.GhostTimer[i] -= 1
            house_bob_step(w, i)
        else:
            house_leave(w, i)
