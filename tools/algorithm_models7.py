"""OV-58, seventh set: the ghost state machine, the turn handling and the whole frame (FrameDispatch, the vertical-blank handler), run against models (method: tools/algorithm_models2.py).

  ghost_behaviour       GhostBehaviour $B7F5 with GhostStartRoute, GhostSelectPatrol, GhostPatrolTravel, GhostPatrol, GhostGoToCorner, GhostChase (A11)
  turn_control          TurnControl $AA2D: turn change, two players, the board for the next turn, the high score (A18)
  frame_dispatch        FrameDispatch $A6CC: the title screens (states 1-4) and the game frame in the order of the code: the clocks, the intro tune, the death, the eaten-ghost pause, the bonus item, the contact
                        with ghosts and the bonus picture, the frightened tick, the pacing of Pac-Man and of every ghost (A03, A15, A17, A19, A20)
  vbi_handler           VbiHandler $A5FD: the frame, then the tunnel clip (A03)
A callee proved equal to its model in the sets 1-6 is called as Python; JunctionLookup and SteerToTarget (sets 1) are run as real ROM code inside the models (`run_verified`), the RANDOM values they use are counted and compared.
Usage: python -I tools/algorithm_models7.py [--write analysis/evidence-algorithms7-summary.txt]
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import algorithm_models3 as M3  # noqa: E402
import algorithm_models4 as M4  # noqa: E402
import algorithm_models5 as M5  # noqa: E402
import algorithm_models6 as M6  # noqa: E402

ROOT = A.ROOT
rd = A.rd
diff = M2.diff
CP, LEVEL = A.CURRENT_PLAYER, A.LEVEL
ENTITY_Y, ENTITY_X, ENTITY_DIR, GHOST_STATE = A.ENTITY_Y, A.ENTITY_X, A.ENTITY_DIR, A.GHOST_STATE
TARGET_X, TARGET_Y = A.TARGET_X, A.TARGET_Y
PAC_X, PAC_Y = 0x8E, 0x89


COVERAGE = {}


class Rnd:
    """the POKEY values handed to the ROM and to the model in the same order"""

    def __init__(self, vals):
        self.vals, self.pos = list(vals), 0

    def rest(self):
        return self.vals[self.pos:]


def jl(mem, x, R):
    c, used = M3.run_verified(mem, 0xB48E, x, R.rest())
    R.pos += used
    return c


def steer(mem, x, R):
    c, used = M3.run_verified(mem, 0xB999, x, R.rest())
    R.pos += used


def draw_step(mem, x):
    M3.model_step_and_draw(mem, x, mem[ENTITY_DIR + x])


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_ghost_select_patrol(mem, x, R):
    mem[GHOST_STATE + x] = 0x08
    mem[0xBE + x] = 0
    r = R.vals[R.pos] & 0x0F if R.pos < len(R.vals) else 0
    R.pos += 1
    mem[0xBA + x] = r
    mem[TARGET_X + x] = rd(0xBCEE + 2 * r)
    mem[TARGET_Y + x] = rd(0xBCEE + 2 * r + 1)
    mem[0xCA + x] = 0x96
    model_ghost_patrol_travel(mem, x, R)


def model_patrol_direction(mem, x):
    r = mem[0xBA + x]
    y = (rd(0xBD16 + r) + mem[0xBE + x]) & 0xFF            # the carry is clear here on every path
    a = mem[0x06AE + y]
    if a == 0:
        mem[0xBE + x] = 0
        a = mem[0x06AE + rd(0xBD16 + r)]
    mem[ENTITY_DIR + x] = a
    draw_step(mem, x)


def model_ghost_patrol_travel(mem, x, R):
    if mem[0xCA + x] == 0:
        model_ghost_go_to_corner(mem, x, R)
        return
    if not jl(mem, x, R):
        draw_step(mem, x)
        return
    steer(mem, x, R)
    if mem[0xDA + x] != 0 or mem[0xD6 + x] != 0:
        draw_step(mem, x)
        return
    mem[GHOST_STATE + x] = 0x10
    model_patrol_direction(mem, x)


def model_ghost_patrol(mem, x, R):
    if mem[0xCA + x] == 0:
        model_ghost_go_to_corner(mem, x, R)
        return
    if jl(mem, x, R):
        mem[0xBE + x] = (mem[0xBE + x] + 1) & 0xFF
    model_patrol_direction(mem, x)


def model_ghost_go_to_corner(mem, x, R):
    mem[GHOST_STATE + x] = 0x20
    mem[TARGET_X + x] = rd(0xBD0E + 2 * x)
    mem[TARGET_Y + x] = rd(0xBD0E + 2 * x + 1)
    if not jl(mem, x, R):
        draw_step(mem, x)
        return
    steer(mem, x, R)
    if mem[0xDA + x] != 0 or mem[0xD6 + x] != 0:
        draw_step(mem, x)
        return
    model_ghost_select_patrol(mem, x, R)


def model_ghost_chase(mem, x, R):
    mem[TARGET_X + x] = mem[PAC_X]
    mem[TARGET_Y + x] = mem[PAC_Y]
    if jl(mem, x, R):
        steer(mem, x, R)
    draw_step(mem, x)


def model_ghost_start_route(mem, x, R):
    if jl(mem, x, R):
        mem[0xD2 + x] = (mem[0xD2 + x] + 1) & 0xFF
    ptr = rd(0xBCE6 + 2 * x) | rd(0xBCE6 + 2 * x + 1) << 8
    mem[0x3C], mem[0x3D] = ptr & 0xFF, ptr >> 8
    a = mem[(ptr + mem[0xD2 + x]) & 0xFFFF]
    if a != 0x0F:
        mem[ENTITY_DIR + x] = a
        M3.model_step_and_draw(mem, x, a)
        return
    if x != 0:
        model_ghost_select_patrol(mem, x, R)
        return
    mem[0xAD] = 0x50
    mem[GHOST_STATE + x] = 0x02
    model_ghost_chase(mem, x, R)


def model_ghost_behaviour(mem, x, R):
    s = mem[GHOST_STATE + x]
    if s & 0x80:
        if (s >> 2) & 1:
            return
        model_ghost_chase(mem, x, R)
        return
    if s == 1:
        model_ghost_start_route(mem, x, R)
    elif s == 2:
        if mem[0xAD] != 0:
            model_ghost_chase(mem, x, R)
        else:
            model_ghost_go_to_corner(mem, x, R)
    elif s == 8:
        model_ghost_patrol_travel(mem, x, R)
    elif s == 0x10:
        model_ghost_patrol(mem, x, R)
    elif s == 0x20:
        model_ghost_go_to_corner(mem, x, R)


def ghost_setup(m, rng):
    for g in range(5):
        m.mem[ENTITY_X + g], m.mem[ENTITY_Y + g] = M2.lattice_position(rng) if rng.random() < 0.85 else (rng.randrange(256), rng.randrange(256))
        m.mem[ENTITY_DIR + g] = rng.choice([1, 2, 4, 8])
    m.mem[PAC_X], m.mem[PAC_Y] = M2.lattice_position(rng)
    for g in range(4):
        m.mem[GHOST_STATE + g] = rng.choice([0x00, 0x01, 0x01, 0x02, 0x08, 0x08, 0x10, 0x10, 0x20, 0x20, 0x80, 0x81, 0x82, 0x84, 0x88, 0x90, 0xA0, 0xC4, 0x42, 0x04, 0x40])
        m.mem[0xCA + g] = rng.choice([0, 0, 1, 0x96, rng.randrange(256)])
        m.mem[0xD2 + g] = rng.choice([0, 1, 2, 3, 5, 8, 12, rng.randrange(16)])
        m.mem[0xBA + g] = rng.randrange(16)
        m.mem[0xBE + g] = rng.choice([0, 1, 2, 5, 9, 10, 11, 12, 20, rng.randrange(256)])
    m.mem[0xAD] = rng.choice([0, 1, 0x50, rng.randrange(256)])
    m.mem[0x3C], m.mem[0x3D] = rng.randrange(256), 0x08 + rng.randrange(8)


def check_ghost_behaviour(n=15000, seed=120):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, kinds = [], {}
    for _ in range(n):
        m = M6.prepare(base, rng)
        ghost_setup(m, rng)
        x = rng.randrange(4)
        vals = [rng.randrange(256) for _ in range(6)]
        m.random = list(vals)
        mem = bytearray(m.mem)
        s0 = m.mem[GHOST_STATE + x]
        m.call(0xB7F5, x=x)
        R = Rnd(vals)
        model_ghost_behaviour(mem, x, R)
        kinds[s0] = kinds.get(s0, 0) + 1
        d = diff(m, mem)
        if d or len(m.random_reads) != R.pos:
            bad.append((hex(s0), [hex(k) for k in d[:4]], len(m.random_reads), R.pos))
    return n, bad, kinds


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_turn_control(mem):
    M5.model_show_power_pellets(mem)
    a = mem[0x23]
    if a != 0:
        if mem[0x25] != 0:
            mem[0x25] -= 1
            return
        if a == 1:
            M5.model_copy(mem, 0x1000, 0x0C00)
            M5.model_draw_label(mem, 2)
            mem[CP] = 0
            mem[0x23] = 3
            return
        if a == 2:
            M5.model_copy(mem, 0x1400, 0x0C00)
            M5.model_draw_label(mem, 1)
            mem[CP] = 1
            mem[0x23] = 3
            return
        M5.model_show_power_pellets(mem)
        mem[0x23] = 0
        return turn_next_board(mem)
    if mem[0x1A] == 0:
        return turn_next_board(mem)
    if mem[CP] != 0:
        if mem[0x2C] == 0:
            return turn_next_board(mem)
        if mem[0x2D] == 0:
            mem[0x23] = 1
            mem[0x25] = 0x30
            return turn_end(mem)
        M5.model_copy(mem, 0x0C00, 0x1400)
        mem[0x25] = 0x30
        mem[0x23] = 1
        return
    if mem[0x2D] == 0:
        return turn_next_board(mem)
    if mem[0x2C] != 0:
        M5.model_copy(mem, 0x0C00, 0x1000)
        mem[0x25] = 0x30
        mem[0x23] = 2
        return
    mem[0x23] = 2
    mem[0x25] = 0x30
    return turn_end(mem)


def turn_next_board(mem):
    x = mem[CP]
    if mem[0x2C + x] == 0:
        return turn_end(mem)
    M5.model_init_board(mem)
    M5.model_draw_level_indicator(mem)
    M5.model_draw_ready_screen(mem)


def turn_end(mem):
    for x in range(14):
        mem[0x0DED + x] = (0xAC + x) & 0xFF
    mem[0x02C7] = mem[0xD019] = 0x44
    if mem[0x23] != 0:
        return
    M5.model_compare_high_score(mem, 0x2A)
    M5.model_compare_high_score(mem, 0x47)
    mem[0x24] = 0
    mem[0x20] = 1
    mem[0x1E] = 0xE2
    M5.model_draw_label(mem, 1)
    M5.model_show_power_pellets(mem)


def turn_setup(m, rng):
    m.mem[0x23] = rng.choice([0, 0, 1, 2, 3, 3, 4])
    m.mem[0x25] = rng.choice([0, 0, 1, 0x30])
    m.mem[0x1A] = rng.randrange(2)
    m.mem[0x2C] = rng.choice([0, 1, 2, 3])
    m.mem[0x2D] = rng.choice([0, 1, 2, 3])
    for k in range(0x1000, 0x1800):
        m.mem[k] = rng.randrange(256)
    for k in range(0x2039, 0x203F):
        m.mem[k] = rng.choice([0, 0x10, 0x15, 0x19])
    for k in list(range(0x202A, 0x2030)) + list(range(0x2047, 0x204D)):
        m.mem[k] = rng.choice([0, 0x10, 0x15, 0x19])


def check_turn_control(n=6000, seed=121):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, ways = [], {}
    for _ in range(n):
        m = M6.prepare(base, rng)
        M5.setup_game(m, rng)
        turn_setup(m, rng)
        mem = bytearray(m.mem)
        m.call(0xAA2D)
        model_turn_control(mem)
        ways[(m.mem[0x23], m.mem[0x24])] = ways.get((m.mem[0x23], m.mem[0x24]), 0) + 1
        d = diff(m, mem)
        if d:
            bad.append(([hex(k) for k in d[:4]],))
    return n, bad, ways


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_move_delay_tick(mem, x):
    c = (mem[0xB5 + x] - 1) & 0xFF
    mem[0xB5 + x] = c
    if c != 0:
        return 0xFF
    cyc = mem[0xB0 + x]
    if cyc == 3:
        cyc = 0xFF
    cyc = (cyc + 1) & 0xFF
    mem[0xB0 + x] = cyc
    lv = min(mem[0x30 + mem[CP]], 6)
    base = rd(0xBDB9 + lv) if x == 4 else rd(0xBDC0 + lv)
    mem[0xB5 + x] = mem[0x07AE + ((base + cyc) & 0xFF)]
    return 0


def model_frightened_tick_full(mem):
    if mem[0xFC] == 0 and mem[0xF2] == 0:
        M5.model_siren(mem)                                   # $AF68 / $B508
        return
    M2.model_frightened_tick(mem)


def model_title_state(mem, y):
    """FrameDispatch for zp_19 = 1, 2 and 3 or more"""
    if y == 1:
        M6.model_init_display2(mem)
        for k in range(256):
            mem[0x1C00 + k] = mem[0x1D00 + k] = mem[0x0F00 + k] = 0
        mem[0x02C5] = 0
        for x in range(14):
            mem[0x1D57 + x] = rd(0xBDF7 + x)
        for x in range(12):
            mem[0x1C18 + x] = (x + 0xC1) & 0xFF
            mem[0x1C2C + x] = (x + 0xCD) & 0xFF
        mem[0x19] += 1
        return
    if y == 2:
        if mem[0x1D] == mem[0x14]:
            mem[0x19] += 1
        return
    one = mem[0x1A] == 0
    mem[0x1C54] = ((mem[0x1A] + 1) & 0xFF) | 0x50
    if one:
        if y == 3:
            M6.model_title_clear(mem, 1)
        a = 0x12
    else:
        if y == 3:
            M6.model_title_clear(mem, 2)
        a = 0x11
    mem[0x1C90] = a
    for x in range(10, -1, -1):
        t = rd(0xBFC6 + x)
        mem[0x1C92 + x] = t
        mem[0x1C56 + x] = t | 0x40
    M6.model_init_display2(mem)
    for x in range(15, -1, -1):
        mem[0x1C7A + x] = rd(0xBFD1 + x)
        mem[0x1CF2 + x] = rd(0xBFE1 + x)
        mem[0x1D56 + x] = rd(0xBDE7 + x)
    a = rd(0xBE05 + mem[0x1B])
    mem[0x1CC6] = a
    mem[0x1CC7] = (a + 1) & 0xFF
    for x in range(16, -1, -1):
        mem[0x1D05 + x] = rd(0xBDD6 + x)
    for x in range(8, -1, -1):
        mem[0x1D6D + x] = rd(0xBFF1 + x)


def model_frame(mem, R):
    y = mem[0x19]
    if y != 0:
        model_title_state(mem, y)
        return
    if mem[0x1E] != 0 and mem[0x14] & 7 == 0:
        mem[0x1E] -= 1
    if mem[0x9B] != 0:
        for k in range(8):
            mem[0xD200 + k] = 0
        return
    M5.model_blink_player_label(mem)
    if mem[0x1C] == 2:
        mem[0x22] = (mem[0x22] + 1) & 0xFF
        mem[0x4D] = mem[0x1C] = 0
        M5.model_draw_level_indicator(mem)
        return
    if mem[0x20] != 0:
        if mem[0x1A] != 0:
            M5.model_draw_label(mem, 2)
        M5.model_draw_label(mem, 1)
        return
    if mem[0x26] != 0:
        M5.model_level_complete_step(mem)
        return
    if mem[0x21] == 0:
        if mem[0x22] == 0:
            return
        if mem[0x14] & 3 != 0:
            return
        x = mem[0xA3]
        if x == 0x40:
            mem[0x21] = (mem[0x21] + 1) & 0xFF
            frame_start_tail(mem)
        else:
            mem[0xD200] = rd(0xBC50 + x)
            mem[0xD202] = rd(0xBC90 + x)
            mem[0xD201] = 0xA8
            mem[0xD203] = 0xA4
            mem[0xA3] = (mem[0xA3] + 1) & 0xFF
            if x == 0x28:
                M5.model_draw_ready_screen(mem)
            return
    # $A805
    a = mem[0x24]
    if a == 1:
        model_turn_control(mem)
        if mem[0x23] != 0 or mem[0x20] != 0:
            return
        mem[0x24] += 1
        mem[0x25] = 0x40
        return
    if a != 0:
        if mem[0x25] != 0:
            mem[0x25] -= 1
            return
        mem[0x24] = 0
        frame_start_tail(mem)
    model_play_frame(mem, R)


def frame_start_tail(mem):
    """$A800: the first ghost's state is raised and the READY text removed"""
    mem[GHOST_STATE] = (mem[GHOST_STATE] + 1) & 0xFF
    M5.model_clear_ready_text(mem)


def model_play_frame(mem, R):
    M5.model_blink_power_pellets(mem)
    if mem[0xED] != 0:
        M5.model_death_sequence(mem)
        M5.model_death_animation(mem)
        return
    used = M3.model_eyes_and_house(mem, R.rest())
    R.pos += used
    if mem[0xE5] != 0:
        M4.model_ghost_eaten_pause(mem)
        return
    M4.model_bonus_update(mem)
    M2.model_power_pellet(mem)
    a = 2
    if mem[0x26] == 0:
        for x in range(4):
            s = mem[GHOST_STATE + x]
            if s & 0x40:
                continue
            bit = 1 << x
            if not (bit & mem[0xD009]) or not (bit & mem[0xD00A]):
                continue
            ey = mem[ENTITY_Y + x]
            dist = mem[PAC_Y] - ey if mem[PAC_Y] >= ey else ey - mem[PAC_Y]
            if dist >= 5:
                continue
            if s & 0x80:
                M4.model_ghost_eaten(mem, x)
                return
            mem[0xAA] |= 0x80                                 # contact with a ghost that is not frightened: the death
            for k in range(8):
                mem[0xD200 + k] = 0
            mem[0xAE] = 1
            mem[0xED] = 1
            mem[0xEE] = 0x60
            break
    if mem[0xD002] & 2:                                       # the bonus item touched by Pac-Man
        lv = min(mem[LEVEL + mem[CP]], 0x0C)
        x = rd(0xBD6D + lv)
        for k in range(5):
            mem[0x0DF1 + k] = rd(0xBD45 + x + k)
        mem[0xA1], mem[0xA2] = 1, 0x40
        mem[0x9F] = mem[0x9D] = mem[0x9E] = 0
        mem[0xF7], mem[0xF8] = 1, 0x78
        lv = min(mem[LEVEL + mem[CP]], 0x0C)
        mem[0x96] = mem[0x0794 + 2 * lv]
        mem[0x97] = mem[0x0794 + 2 * lv + 1]
        a = M2.model_add_score(mem)
    mem[0xD01E] = a
    if mem[0xED] != 0:
        return
    model_frightened_tick_full(mem)
    if mem[0xE5] != 0:
        return
    M4.model_dot_sound(mem)
    M5.model_bonus_sound(mem)
    M5.model_toggle_leg_phase(mem)
    if mem[0xA8] != 0:
        v = 0
    elif mem[0xA9] != 0:
        v = mem[0xA9]
    else:
        v = model_move_delay_tick(mem, 4)
    mem[0xA7] = v
    mem[0xA8] = 0
    used = M4.model_move_pacman(mem, R.rest())
    R.pos += used
    mem[0xA9] = 0
    M2.model_eat_dot(mem)
    if mem[0x14] & 3 == 0:
        M3.model_house_waiting_tick(mem)
    M2.model_chase_timer_siren(mem)
    if mem[0xA8] != 0:
        return
    for x in (3, 2, 1, 0):
        s = mem[GHOST_STATE + x]
        if s & 0x7F == 0:
            continue
        if mem[0x14] & 7 == 0 and mem[0xCA + x] != 0:
            mem[0xCA + x] -= 1
        if mem[GHOST_STATE + x] & 0x3F == 0:
            continue
        if mem[GHOST_STATE + x] & 0x40:
            continue
        slow = False
        if mem[ENTITY_Y + x] == 0x74:
            ex = mem[ENTITY_X + x]
            slow = ex >= 0xA7 or ex < 0x52 or bool(mem[GHOST_STATE + x] & 0x80)
        else:
            slow = bool(mem[GHOST_STATE + x] & 0x80)
        if slow:
            if model_move_delay_tick(mem, x) != 0:
                continue
            if mem[0x5A + x] == 1:
                mem[0x5A + x] = 0
            else:
                mem[0x5A + x] = 1
                continue
        else:
            if model_move_delay_tick(mem, x) != 0:
                continue
        model_ghost_behaviour(mem, x, R)


def model_vbi(mem, R):
    mem[0x18] = 0
    mem[0x45] = (mem[0x45] - 1) & 0xFF
    model_frame(mem, R)
    if mem[0xE5] == 0:
        M5.model_clip_entities(mem)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def frame_setup(m, rng, mode):
    M5.setup_game(m, rng)
    ghost_setup(m, rng)
    m.mem[0x3C], m.mem[0x3D] = rng.randrange(256), 0x08 + rng.randrange(8)
    m.mem[0x19] = 0 if mode != "title" else rng.choice([1, 2, 3, 4, 5])
    m.mem[0x1D] = m.mem[0x14] if rng.random() < 0.5 else rng.randrange(256)
    m.mem[0x1A] = rng.randrange(2)
    m.mem[0x1B] = rng.choice([0, 1, 2, 4, 6, 8, 10, 12])
    m.mem[0x9B] = rng.choice([0, 0, 0, 0, 0, 1])
    m.mem[0x1E] = rng.choice([0, 0, 1, 5])
    m.mem[0x1C] = rng.choice([0, 0, 0, 1, 2])
    m.mem[0x20] = rng.choice([0, 0, 0, 0, 0, 0, 1])
    m.mem[0x26] = rng.choice([0, 0, 0, 0, 0, 1])
    m.mem[0x21] = rng.choice([0, 1, 1, 1, 1, 1, 1])
    m.mem[0x22] = rng.choice([0, 1, 1, 1, 1])
    m.mem[0xA3] = rng.choice([0, 0x27, 0x28, 0x3F, 0x40, rng.randrange(0x41)])
    m.mem[0x24] = rng.choice([0, 0, 0, 0, 0, 0, 1, 2, 2])
    m.mem[0x25] = rng.choice([0, 0, 1])
    m.mem[0x23] = rng.choice([0, 0, 0, 0, 1, 2, 3])
    m.mem[0xED] = rng.choice([0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6])
    m.mem[0xE5] = rng.choice([0, 0, 0, 0, 0, 0, 0, 1])
    m.mem[0xAA] = rng.choice([0, 0, 0, 0x80])
    m.mem[0xA6] = rng.randrange(4)
    m.mem[0x82] = rng.randrange(4)
    m.mem[0xA7] = rng.choice([0, 0, 1])
    for g in range(4):
        m.mem[0x5A + g] = rng.randrange(2)                   # the second-step flag of ghosts in the tunnel and frightened ghosts
    m.mem[0xA8] = rng.choice([0, 0, 0, 1])
    m.mem[0xA9] = rng.choice([0, 0, 0, 1])
    m.mem[0xAB] = rng.randrange(4)
    m.mem[0xAC] = rng.choice([1, 2, 4, 8])
    m.mem[0x93] = rng.choice([1, 2, 4, 8])
    m.mem[0x0278], m.mem[0x0279] = rng.choice([0x0F, 0x0E, 0x0D, 0x0B, 0x07]), rng.choice([0x0F, 0x0E])
    m.mem[0x80], m.mem[0x81] = rng.randrange(256), 0x08 + rng.randrange(3)
    ptr = m.mem[0x80] | m.mem[0x81] << 8
    m.mem[ptr] = rng.choice([0, 1, 1, 2, 3])
    m.mem[0x84], m.mem[0x83] = rng.randrange(256), rng.randrange(256)
    m.mem[0xD009] = rng.choice([0, 0x0F, 0x0F, 0x03, 0x05])
    m.mem[0xD00A] = rng.choice([0, 0x0F, 0x0F, 0x09, 0x06])
    m.mem[0xD002] = rng.choice([0, 0, 0, 2, 3])
    m.mem[0xF2] = rng.choice([0, 1])
    m.mem[0xFC] = rng.choice([0, 0, 1, 2, rng.randrange(256)])
    m.mem[0xFD] = rng.choice([0, 0, 1, 5])
    m.mem[0xFB] = rng.choice([0, 1, 0x18])
    m.mem[0xF4] = rng.choice([0, 1])
    m.mem[0xF5] = rng.randrange(7)
    m.mem[0xF7] = rng.choice([0, 0, 1, 7, 9])
    m.mem[0xF8] = rng.choice([0x78, 0xB4, 0x82, 0x60])
    m.mem[0xE0] = rng.choice([0, 1])
    m.mem[0xDE] = rng.choice([0x28, 0x30, 0x3F, 0x40, 0x20])
    m.mem[0xDF] = rng.choice([0, 1, 2])
    m.mem[0x9C] = rng.choice([2, 3, 4, 5])
    m.mem[0xE8] = rng.choice([0xFF, 0xFF, 0, 1, 2, 3])
    m.mem[0xE9] = rng.choice([0xFF, 0, 1, 2, 3])
    for g in range(4):
        m.mem[0x02C0 + g] = rng.choice([0xDC, 0x44, 0x84, 0x0C])
    m.mem[0x14] = rng.randrange(256)
    for k in range(6):
        m.mem[0x94 + k] = 0                                  # ScoreAdd is always cleared by AddToScore
    m.mem[0x34] = rng.choice([rng.randrange(256), 0x50, 0xA0, 0xB0, 0xE0, 0xF0])
    m.mem[0x35] = rng.choice([rng.randrange(256), 0x50, 0xA0, 0xB0, 0xE0, 0xF0])
    m.mem[0x36] = rng.choice([0, 0, 0, 1])
    m.mem[0x37] = rng.choice([0, 0, 0, 1])
    m.mem[0x43] = rng.choice([0, 1, 2])
    m.mem[0x44] = rng.choice([0, 1, 2])
    m.mem[0x32] = rng.choice([0x0F, rng.randrange(16)])
    m.mem[0x33] = rng.choice([0x0F, rng.randrange(16)])
    m.mem[0x2E] = rng.choice([0, 1, 1])
    m.mem[0x2F] = rng.choice([0, 1, 1])
    m.mem[0xA1] = rng.choice([0, 0, 1])
    m.mem[0xA2] = rng.choice([0, 3])
    m.mem[0x9F] = rng.choice([0, 0, 1])
    for k in list(range(0x2039, 0x203F)) + list(range(0x202A, 0x2030)) + list(range(0x2047, 0x204D)):
        m.mem[k] = rng.choice([0, 0x10, 0x11, 0x15, 0x19])
    for k in range(0x1000, 0x1800):
        m.mem[k] = rng.randrange(256)
    if mode == "play":                                        # frames of real play: the paths that the random flags above leave rarely
        for a, v in ((0x19, 0), (0x9B, 0), (0x1C, 0), (0x20, 0), (0x26, 0), (0x21, 1), (0x22, 1), (0x24, 0), (0x23, 0), (0xAA, 0)):
            m.mem[a] = v
        m.mem[0xED] = rng.choice([0, 0, 0, 0, 0, 1, 3])
        m.mem[0xE5] = rng.choice([0, 0, 0, 0, 0, 0, 1])
        m.mem[0xA8] = rng.choice([0, 0, 0, 0, 1])
        m.mem[0xA7] = 0
        m.mem[0xFC] = rng.choice([0, 0, 0, 1, 2, 5])
        ptr = m.mem[0x80] | m.mem[0x81] << 8
        m.mem[ptr] = rng.choice([1, 1, 2, 0])
        if rng.random() < 0.3:
            m.mem[PAC_Y], m.mem[PAC_X] = rng.choice(M2.PELLET_SQUARES)
            m.mem[0x32 + m.mem[CP]] = rng.choice([0x0F, 0x0F, 0x05, 0x0A])
        if rng.random() < 0.15:
            p = m.mem[CP]
            m.mem[0x34 + p], m.mem[0x36 + p] = 3, 1
            m.mem[0x84], m.mem[0x83] = (m.mem[PAC_X] + 1) & 0xFF, m.mem[PAC_Y]
            m.mem[0x82] = m.mem[0xA6] = 0
        for g in range(4):
            if rng.random() < 0.4:
                m.mem[ENTITY_X + g], m.mem[ENTITY_Y + g] = m.mem[PAC_X], (m.mem[PAC_Y] + rng.randrange(-5, 6)) & 0xFF
        m.mem[0xD009] = m.mem[0xD00A] = rng.choice([0x0F, 0x0F, 0x0F, 0x03])
        for g in range(4):
            m.mem[0x02C0 + g] = rng.choice([0xDC, 0x44, 0x84, 0x0C, 0x0C])


def check_frame(call, model, label, n, seed, mode):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, paths = [], {}
    cov = dict.fromkeys(["frames", "death started", "ghost eaten", "bonus picked", "power pellet", "dot eaten", "RANDOM used", "ghost moved", "Pac-Man moved", "level complete", "state change 1 -> 2"], 0)
    for _ in range(n):
        m = M6.prepare(base, rng)
        frame_setup(m, rng, mode)
        vals = [rng.randrange(256) for _ in range(12)]
        m.random = list(vals)
        mem = bytearray(m.mem)
        pre = (m.mem[0x19], m.mem[0x1C], m.mem[0x20], m.mem[0x26], m.mem[0x21], m.mem[0x24], m.mem[0xED], m.mem[0xE5])
        before = bytes(m.mem[:0x100])
        call(m)
        cov["frames"] += 1
        cov["death started"] += before[0xED] == 0 and m.mem[0xED] == 1
        cov["ghost eaten"] += before[0xE5] == 0 and m.mem[0xE5] != 0 and m.mem[0xE5] != before[0xE5]
        cov["bonus picked"] += before[0xA1] == 0 and m.mem[0xA1] == 1
        cov["power pellet"] += before[0xFC] == 0 and m.mem[0xFC] == 1
        cov["dot eaten"] += m.mem[0xF4] == 1 and before[0xF4] == 0
        cov["RANDOM used"] += len(m.random_reads) > 0
        cov["ghost moved"] += any(m.mem[0x85 + g] != before[0x85 + g] or m.mem[0x8A + g] != before[0x8A + g] for g in range(4))
        cov["Pac-Man moved"] += m.mem[0x89] != before[0x89] or m.mem[0x8E] != before[0x8E]
        cov["level complete"] += before[0x26] == 0 and m.mem[0x26] == 1
        cov["state change 1 -> 2"] += before[0x19] == 1 and m.mem[0x19] == 2
        R = Rnd(vals)
        model(mem, R)
        paths[pre] = paths.get(pre, 0) + 1
        d = diff(m, mem)
        if d or len(m.random_reads) != R.pos:
            bad.append((pre, [hex(k) for k in d[:4]], len(m.random_reads), R.pos))
    COVERAGE[label] = cov
    return n, bad, paths


def check_frame_dispatch(n=12000):
    return check_frame(lambda m: m.call(0xA6CC), model_frame, "frame", n, 122, "game")


def check_play(n=12000):
    return check_frame(lambda m: m.call(0xA6CC), model_frame, "play", n, 125, "play")


def check_title(n=3000):
    return check_frame(lambda m: m.call(0xA6CC), model_frame, "title", n, 123, "title")


def check_vbi(n=6000):
    def call(m):
        m.call(0xA5FD)
    return check_frame(call, model_vbi, "vbi", n, 124, "game")


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def report():
    L = []
    P = L.append
    P("Seventh set of algorithm models against the ROM executed in tools/cpu6502.py (tools/algorithm_models7.py, OV-58); whole memory (zero page, $0200-$9FFF, $D000-$D7FF) compared after every call, RANDOM reads counted")
    P("")
    R = []
    n, bad, kinds = check_ghost_behaviour()
    P("ghost_behaviour: %d calls (21 ghost states, lattice and other positions, timers 0 / any, start-route steps through the end marker, every patrol route and step, RANDOM and the steering through the real JunctionLookup / SteerToTarget): %d differences" % (n, len(bad)))
    R.append(("ghost_behaviour", bad))
    n, bad, ways = check_turn_control()
    P("turn_control: %d calls (both players, lives 0-3, the 1UP / 2UP hand-over, the board copies, the high score; %d different end states): %d differences" % (n, len(ways), len(bad)))
    R.append(("turn_control", bad))
    n, bad, paths = check_title()
    P("frame_dispatch, title screens: %d calls (states 1-5, one and two players, every start level): %d differences" % (n, len(bad)))
    R.append(("frame_title", bad))
    n, bad, paths = check_frame_dispatch()
    P("frame_dispatch, game frame: %d calls (%d different combinations of the state flags: pause, demo, level complete, intro tune, turn control, death, eaten-ghost pause; contacts with ghosts, the bonus item, the frightened tick, Pac-Man, the pacing of every ghost; RANDOM count compared): %d differences" % (n, len(paths), len(bad)))
    R.append(("frame_dispatch", bad))
    n, bad, paths = check_play()
    P("frame_dispatch, frames of play: %d calls (the same, with the intro and the turn handling finished, so that every call runs the play frame: dots and pellets eaten, the level complete flag, contacts, eaten ghosts, deaths, the frightened period): %d differences" % (n, len(bad)))
    R.append(("frame_play", bad))
    n, bad, paths = check_vbi()
    P("vbi_handler: %d calls (the same frames through $A5FD, with the tunnel clip afterwards): %d differences" % (n, len(bad)))
    R.append(("vbi_handler", bad))
    cov = COVERAGE["play"]
    P("coverage of the frames of play: " + ", ".join("%s %d" % kv for kv in cov.items() if kv[0] != "state change 1 -> 2"))
    for name, b in R:
        for t in b[:3]:
            P("  %s: %s" % (name, t))
    return L, R


def main():
    L, R = report()
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print(txt)


if __name__ == "__main__":
    main()
