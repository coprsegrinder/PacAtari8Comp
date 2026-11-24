"""OV-58, fifth set: scores, drawing, the death sequence, the level change and the turn handling, run against models (method: tools/algorithm_models2.py, the whole memory is compared after every call).

  Leaves:   compare_high_score $AB26, clip_entity $AB57 / clip_entities $AB48, bonus_sound $ABC9, toggle_leg_phase $AC05, draw_level_indicator $AC93, draw_lives $AD15,
            draw_all_in_place $AD49, clear_ready_text $AD5E, blink_player_label $AD69, draw_labels $AD87 / $AD9F, load_shadow_colors $B113, copies $B11F / $B13D / $B15B, clear_player_memory $B0F1,
            show_power_pellets $B55A, blink_power_pellets $B54F, siren $B508, clear_player_counters $AE1E
  Composed: init_board $ADAF, new_game_init $ADF1, new_board_init $AE02, advance_level $AC75, level_complete_step $AC18, death_sequence $AE3D, death_animation $AEF7, turn_control $AA2D
A routine that is proved equal to its model earlier in this set (or in the sets 1-4) is called by the models of the routines above it as Python code, not as ROM code (except JunctionLookup / SteerToTarget).
Usage: python -I tools/algorithm_models5.py [--write analysis/evidence-algorithms5-summary.txt]
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

ROOT = A.ROOT
rd = A.rd
diff, randomize = M2.diff, M2.randomize
ENTITY_Y, ENTITY_X, ENTITY_DIR, GHOST_STATE = A.ENTITY_Y, A.ENTITY_X, A.ENTITY_DIR, A.GHOST_STATE
CURRENT_PLAYER, LEVEL = A.CURRENT_PLAYER, A.LEVEL
PCOLR0, COLOR0 = 0x02C0, 0x02C4


def cell(mem, a, v):
    mem[a] = v & 0xFF


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_compare_high_score(mem, x):
    y = 0
    while True:
        a, c = mem[0x2000 + x], mem[0x2039 + y]
        if a == c:
            x, y = x + 1, y + 1
            if y == 6:
                return
            continue
        if a < c:
            return
        while y != 6:
            mem[0x2039 + y] = mem[0x2000 + x]
            x, y = x + 1, y + 1
        return


def check_compare_high_score(n=8000, seed=90):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, replaced = [], 0
    for _ in range(n):
        m = A.fresh(base)
        x = rng.choice([0x2A, 0x47])
        digits = [rng.choice([0, 0x10, 0x11, 0x12, 0x15, 0x19]) for _ in range(6)]
        hs = list(digits)
        for _k in range(rng.randrange(3)):
            hs[rng.randrange(6)] = rng.choice([0, 0x10, 0x13, 0x19])
        if rng.random() < 0.3:
            hs = list(digits)
        for k in range(6):
            m.mem[0x2000 + x + k] = digits[k]
            m.mem[0x2039 + k] = hs[k]
        mem = bytearray(m.mem)
        m.call(0xAB26, x=x)
        model_compare_high_score(mem, x)
        replaced += mem[0x2039:0x203F] != bytes(hs)
        d = diff(m, mem)
        if d:
            bad.append((x, [hex(k) for k in d[:4]]))
    return n, bad, replaced


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_clip_entity(mem, x, a):
    mem[0x47] = a
    idx = 0xFF if x == 4 else x
    mem[0x48] = (idx + 0x24) & 0xFF
    fe, ff = 0xFF, mem[ENTITY_X + x]
    mem[0xFE], mem[0xFF] = fe, ff
    if ff >= 0xC0:
        while True:
            if 0xC0 == mem[0xFF]:
                break
            mem[0xFF] = (mem[0xFF] - 1) & 0xFF
            carry = mem[0xFE] >> 7
            mem[0xFE] = (mem[0xFE] << 1) & 0xFF
            if carry:
                continue
            if mem[ENTITY_X + x] >= 0xCA and mem[ENTITY_DIR + x] == 8:
                mem[ENTITY_X + x] = 0x2A
                if x == 4:
                    mem[0x80] = 0x8F
            break
    else:
        if ff >= 0x39:
            return
        while True:
            if 0x38 == mem[0xFF]:
                break
            mem[0xFF] = (mem[0xFF] + 1) & 0xFF
            carry = mem[0xFE] & 1
            mem[0xFE] >>= 1
            if carry:
                continue
            if mem[ENTITY_X + x] == 0x2A and mem[ENTITY_DIR + x] == 4:
                mem[ENTITY_X + x] = 0xCA
                if x == 4:
                    mem[0x80] = 0xB7
            break
    ptr = mem[0x47] | mem[0x48] << 8
    for y in range(15, -1, -1):
        mem[ptr + y] &= mem[0xFE]


def model_clip_entities(mem):
    for x in (4, 3, 2, 1, 0):
        if mem[ENTITY_Y + x] == 0x74:
            model_clip_entity(mem, x, 0x74)


def tunnel_setup(m, rng):
    for g in range(5):
        m.mem[ENTITY_X + g] = rng.choice([rng.randrange(0x20, 0x60), rng.randrange(0xA0, 0xE0), 0x2A, 0xCA, 0x38, 0x39, 0xC0, 0xC1, 0xCB, 0x29, rng.randrange(256)])
        m.mem[ENTITY_Y + g] = rng.choice([0x74, 0x74, 0x74, 0x64, rng.randrange(256)])
        m.mem[ENTITY_DIR + g] = rng.choice([1, 2, 4, 8, 4, 8])
    for k in range(0x2300, 0x2800):
        m.mem[k] = rng.randrange(256)


def check_clip(n=6000, seed=91):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, masked = [], 0
    for i in range(n):
        m = A.fresh(base)
        randomize(m, rng)
        tunnel_setup(m, rng)
        mem = bytearray(m.mem)
        if i % 2:
            x = rng.randrange(5)
            a = rng.choice([0x74, 0x74, rng.randrange(256)])
            m.call(0xAB57, a=a, x=x)
            model_clip_entity(mem, x, a)
        else:
            m.call(0xAB48)
            model_clip_entities(mem)
        masked += m.mem[0xFE] != 0xFF and mem[0xFE] != 0xFF
        d = diff(m, mem)
        if d:
            bad.append((i % 2, [hex(k) for k in d[:4]]))
    return n, bad, masked


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_bonus_sound(mem):
    x = mem[0xF7]
    if x == 0:
        return
    a, y = mem[0xF8], 0xA5
    if x < 7:
        if a == 0xB4:
            mem[0xF7] = (mem[0xF7] + 1) & 0xFF
            y = 0xA3
        else:
            a = (a + 5) & 0xFF
            if a == 0:                                        # a sum of 0 falls into $ABDE (the same as a == $B4)
                mem[0xF7] = (mem[0xF7] + 1) & 0xFF
                y = 0xA3
    if x >= 7:
        if x == 9:
            mem[0xF7] = (mem[0xF7] + 1) & 0xFF
        else:
            y = 0xA3
        if a == 0x78:
            mem[0xF7] = 0
            a = y = 0
        else:
            a = (a - 5 - (1 if a < 0x78 else 0)) & 0xFF      # `sec` is undone by `cmp #$78`: the borrow is the carry of the compare
    mem[0xF8] = a
    mem[0xD200] = a
    mem[0xD201] = y


def model_toggle_leg_phase(mem):
    if mem[0x14] & 0x0F == 0:
        mem[0xAF] = 0 if mem[0xAF] else 1


def check_bonus_sound(n=8000, seed=92):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        m.mem[0xF7] = rng.choice([0, 1, 2, 6, 7, 8, 9, 10, 11])
        m.mem[0xF8] = rng.choice([0x78, 0xB4, 0x50, 0x82, 0x87, 0x7D, rng.randrange(256)])
        mem = bytearray(m.mem)
        m.call(0xABC9)
        model_bonus_sound(mem)
        d = diff(m, mem)
        if d:
            bad.append(([hex(k) for k in d[:4]],))
    m = A.fresh(base)                                         # the whole sound from the first note, frame after frame
    m.mem[0xF7], m.mem[0xF8] = 1, 0x78
    mem = bytearray(m.mem)
    for f in range(300):
        m.call(0xABC9)
        model_bonus_sound(mem)
        if diff(m, mem):
            bad.append(("sweep", f))
            break
    n2 = n + 300
    for _ in range(2000):
        m = A.fresh(base)
        m.mem[0x14] = rng.randrange(256)
        m.mem[0xAF] = rng.randrange(2)
        mem = bytearray(m.mem)
        m.call(0xAC05)
        model_toggle_leg_phase(mem)
        if diff(m, mem):
            bad.append(("leg", m.mem[0x14]))
    return n2 + 2000, bad


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_draw_level_indicator(mem):
    for x in range(10):
        mem[0x0DEF + x] = (0xA2 + x) & 0xFF
    lv = mem[LEVEL + mem[CURRENT_PLAYER]]
    mem[0xA0] = 0xDA if 6 <= lv < 0x0A else 0x44
    if lv < 6:
        mem[0x2A] = lv
        dst = 0x0F92
        mem[0x3F] = 0x0F
        x = 0
        while True:
            lo = dst & 0xFF
            code = rd(0xBD26 + x)
            mem[0x0F00 + lo] = code
            lo = (lo + 1) & 0xFF
            mem[0x0F00 + lo] = (code + 1) & 0xFF
            mem[0x3E] = lo
            if x == lv:
                return
            x += 1
            lo = (lo - 3) & 0xFF
            mem[0x3E] = lo
            dst = 0x0F00 | lo
            if lo == 0:
                break
        return
    a = min(lv, 0x12)
    mem[0x2A] = a - 6
    src = 0xBD3E - (a - 6)
    mem[0x3C], mem[0x3D] = src & 0xFF, src >> 8
    for y in range(7):
        v = rd(src + y)
        mem[0x0F86 + 2 * y] = v
        mem[0x0F87 + 2 * y] = (v + 1) & 0xFF


def model_draw_lives(mem):
    n = mem[0x2C + mem[CURRENT_PLAYER]]
    y = 0x9B
    if n == 3:
        mem[0x0F78] = mem[0x0F76] = mem[0x0F74] = y
    elif n == 2:
        mem[0x0F78] = 0
        mem[0x0F76] = mem[0x0F74] = y
    elif n == 1:
        mem[0x0F76] = mem[0x0F78] = 0
        mem[0x0F74] = y
    else:
        mem[0x0F74] = mem[0x0F76] = mem[0x0F78] = 0


def model_draw_all_in_place(mem):
    mem[0xAE] = 1
    for x in (3, 2, 1, 0):
        M3.model_step_and_draw(mem, x, mem[ENTITY_DIR + x])
    mem[0xAE] = 0
    M4.model_pacman_draw(mem, 0, 0)


def model_clear_ready_text(mem):
    for x in range(14):
        mem[0x0DED + x] = 0


def model_draw_label(mem, up):
    base, code = (0x2021, 0x12) if up == 2 else (0x2004, 0x11)
    mem[base], mem[base + 1], mem[base + 2] = code, 0x35, 0x30


def model_blink_player_label(mem):
    if mem[0x14] & 0x0F:
        return
    mem[0xFA] = 0 if mem[0xFA] else 1
    up = 2 if mem[CURRENT_PLAYER] else 1
    if mem[0xFA]:
        model_draw_label(mem, up)
    else:
        base = 0x2021 if up == 2 else 0x2004
        mem[base] = mem[base + 1] = mem[base + 2] = 0


def model_load_shadow_colors(mem):
    for x in range(8):
        mem[PCOLR0 + x] = rd(0xBBE2 + x)


def model_copy(mem, src, dst):
    for k in range(0x400):
        mem[dst + k] = mem[src + k]


def model_clear_player_memory(mem):
    for p in range(0x2300, 0x2800):
        mem[p] = 0
    for x in range(0xF0, 0x100):
        for page in range(5):
            mem[0x2300 + 0x100 * page + x] = 0xFE


def model_show_power_pellets(mem):
    flags = mem[0x32 + mem[CURRENT_PLAYER]]
    mem[0x2A] = flags
    y = 2
    if flags & 1:
        mem[0x0C7B] = y
    if flags & 2:
        mem[0x0C9C] = y
    if flags & 4:
        mem[0x0E83] = y
    if flags & 8:
        mem[0x0EA4] = y


def model_blink_power_pellets(mem):
    a = mem[0x14] & 0x0F
    if a == 0:
        model_show_power_pellets(mem)
    elif a == 8:
        mem[0x0C7B] = mem[0x0C9C] = mem[0x0E83] = mem[0x0EA4] = 0


def model_siren(mem):
    """$B508: the siren on channel 2 (a triangle between $28 and $40 in steps of SirenStep); the labels are those of the code"""
    mem[0xE4] = 0
    if mem[0xE0] == 0:
        mem[0xDE] = 0x28
        mem[0xE0] = 1
        mem[0xDF] = 1
    step = mem[0x9C]
    label = "51A"
    while True:
        de = mem[0xDE]
        if label == "51A":
            if mem[0xDF] == 1:
                if de >= 0x40:
                    mem[0xDF] = 2
                    label = "53F"
                else:
                    label = "52C"
            else:
                label = "533"
        elif label == "52C":
            a = (step + de) & 0xFF
            if a != 0:
                break
            label = "533"                                     # a sum of 0 falls into $B533
        elif label == "533":
            if de >= 0x28:
                label = "53F"
            else:
                mem[0xDF] = 1
                label = "52C"
        else:                                                 # 53F
            a = (de - step) & 0xFF
            break
    mem[0xDE] = a
    mem[0xD202] = a
    mem[0xD203] = 0xA1


def model_set_release_timers(mem, y):
    y = min(y, 3)
    for x in (2, 1, 0):
        mem[0xCB + x] = rd(0xBBF2 + y)
        y += 1
    return rd(0xBBF2 + y - 1)


def model_clear_player_counters(mem, x):
    mem[0x32 + x] = 0x0F
    mem[0x43 + x] = 0
    mem[0x34 + x] = 0
    mem[0x36 + x] = 0


def model_init_board(mem):
    model_clear_player_memory(mem)
    for x in range(0x80, 0x100):
        mem[x] = 0
    model_load_shadow_colors(mem)
    lv = min(mem[LEVEL + mem[CURRENT_PLAYER]], 6)
    mem[0xB9] = mem[0x07AE + rd(0xBDB9 + lv)]
    gy = rd(0xBDC0 + lv)
    for x in range(3, -1, -1):
        mem[0xB5 + x] = mem[0x07AE + gy]
    for x in range(0x13, -1, -1):
        mem[0x80 + x] = rd(0xBB6F + x)
    last = model_set_release_timers(mem, 0)
    mem[0xD01E] = last


def model_new_board_init(mem):
    model_copy(mem, 0x0800, 0x0C00)
    model_draw_lives(mem)
    p = mem[CURRENT_PLAYER]
    y = mem[LEVEL + p]
    if y == 0 and mem[0x14] & 0x80:
        model_set_release_timers(mem, 0)
    elif (y + 1) & 0xFF:                                     # Level 255: `iny / bne` falls through and the timers are not set
        model_set_release_timers(mem, (y + 1) & 0xFF)
    model_clear_player_counters(mem, mem[CURRENT_PLAYER])


def model_new_game_init(mem):
    mem[0x2C] = mem[0x2D] = 3
    mem[LEVEL] = mem[0x31] = mem[0x1B]
    model_clear_player_counters(mem, 1)
    model_new_board_init(mem)


def model_advance_level(mem):
    model_new_board_init(mem)
    p = mem[CURRENT_PLAYER]
    mem[0x2C + p] = (mem[0x2C + p] + 1) & 0xFF
    mem[LEVEL + p] = (mem[LEVEL + p] + 1) & 0xFF
    model_draw_level_indicator(mem)
    model_draw_ready_screen(mem)
    mem[0x26] = mem[0x27] = 0
    mem[0x24] = 2
    mem[0x25] = 0x40


def model_draw_ready_screen(mem):
    model_draw_all_in_place(mem)
    p = mem[CURRENT_PLAYER]
    mem[0x2C + p] = (mem[0x2C + p] - 1) & 0xFF
    model_draw_lives(mem)


def model_level_complete_step(mem):
    s = mem[0x27]
    if s == 0:
        for k in range(8):
            mem[0xD200 + k] = 0
        model_draw_all_in_place(mem)
        mem[0x28] = 0x40
        mem[0x27] += 1
    elif s == 1:
        if mem[0x28]:
            mem[0x28] -= 1
            return
        for x in range(4):
            mem[0xD000 + x] = 0
        mem[COLOR0] = 0x0C
        mem[0x29] = 7
        mem[0x28] = 0x10
        mem[0x27] += 1
    elif s == 2:
        if mem[0x28]:
            mem[0x28] -= 1
            return
        mem[0x29] -= 1
        if mem[0x29] == 0:
            mem[0x27] += 1
            return
        mem[COLOR0] = 0x0C if mem[0x29] & 1 else 0x86
        mem[0x28] = 0x10
    elif s == 3:
        model_init_board(mem)
        mem[0x27] += 1
    else:
        model_advance_level(mem)


def setup_game(m, rng, entities=True):
    for a in range(0x100):
        m.mem[a] = rng.randrange(256)
    m.mem[CURRENT_PLAYER] = rng.randrange(2)
    m.mem[LEVEL] = rng.choice([0, 1, 5, 6, 9, 10, 17, 18, 40, rng.randrange(256)])
    m.mem[LEVEL + 1] = rng.choice([0, 1, 5, 6, 9, 10, 17, 18, 40, rng.randrange(256)])
    m.mem[0x2C] = rng.choice([0, 1, 2, 3, 4, 255])
    m.mem[0x2D] = rng.choice([0, 1, 2, 3, 4, 255])
    m.mem[0x14] = rng.randrange(256)
    if entities:
        M3.setup_entities(m, rng)
        for g in range(4):
            m.mem[GHOST_STATE + g] = rng.choice(M3.STATES)
        m.mem[0x89], m.mem[0x8E] = rng.randrange(256), rng.randrange(256)
        m.mem[0xAE] = rng.randrange(2)
    for p in range(0x0800, 0x0C00):
        m.mem[p] = rng.randrange(256)
    for p in range(0x0C00, 0x1800):
        m.mem[p] = rng.randrange(256)
    for p in range(0x2300, 0x2800):
        m.mem[p] = rng.randrange(256)


def check_group(name, call, model, n, seed, setup=None):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for i in range(n):
        m = A.fresh(base)
        setup_game(m, rng)
        if setup:
            setup(m, rng, i)
        mem = bytearray(m.mem)
        call(m, i)
        model(mem, i)
        d = diff(m, mem)
        if d:
            bad.append((i, [hex(k) for k in d[:4]]))
    return n, bad


def check_draw_level_indicator(n=3000):
    return check_group("draw_level_indicator", lambda m, i: m.call(0xAC93), lambda mem, i: model_draw_level_indicator(mem), n, 93, setup=lambda m, rng, i: m.mem.__setitem__(LEVEL + m.mem[CURRENT_PLAYER], i % 24 if i < 48 else rng.randrange(256)))


def check_draw_lives(n=1500):
    return check_group("draw_lives", lambda m, i: m.call(0xAD15), lambda mem, i: model_draw_lives(mem), n, 94)


def check_draw_all(n=2500):
    return check_group("draw_all_in_place", lambda m, i: m.call(0xAD49), lambda mem, i: model_draw_all_in_place(mem), n, 95)


def check_labels(n=3000):
    def call(m, i):
        m.call([0xAD5E, 0xAD69, 0xAD87, 0xAD9F][i % 4])

    def model(mem, i):
        [model_clear_ready_text, model_blink_player_label, lambda mm: model_draw_label(mm, 2), lambda mm: model_draw_label(mm, 1)][i % 4](mem)
    return check_group("labels", call, model, n, 96)


def check_colours_copies(n=800):
    calls = [(0xB113, lambda mem: model_load_shadow_colors(mem)), (0xB11F, lambda mem: model_copy(mem, 0x0800, 0x0C00)), (0xB13D, lambda mem: model_copy(mem, 0x0C00, 0x1000)),
             (0xB15B, lambda mem: model_copy(mem, 0x0C00, 0x1400)), (0xB0F1, lambda mem: model_clear_player_memory(mem)), (0xB55A, lambda mem: model_show_power_pellets(mem)),
             (0xB54F, lambda mem: model_blink_power_pellets(mem))]
    return check_group("copies", lambda m, i: m.call(calls[i % 7][0]), lambda mem, i: calls[i % 7][1](mem), n, 97, setup=lambda m, rng, i: m.mem.__setitem__(0x14, rng.choice([0, 8, 1, 0x10, 0x18, rng.randrange(256)])))


def check_siren(n=6000):
    def setup(m, rng, i):
        m.mem[0xE0] = rng.choice([0, 1])
        m.mem[0xDF] = rng.choice([0, 1, 2])
        m.mem[0xDE] = rng.choice([0x28, 0x27, 0x3F, 0x40, 0x41, 0x22, 0x20, rng.randrange(256)])
        m.mem[0x9C] = rng.choice([2, 3, 4, 5, 2, 3])                   # the real values (a step of 0 with DE = 0 would loop for ever in the ROM)
    return check_group("siren", lambda m, i: m.call(0xB508), lambda mem, i: model_siren(mem), n, 98, setup=setup)


def check_init_and_levels(n=300):
    out = []
    for name, addr, model in (("init_board", 0xADAF, model_init_board), ("new_game_init", 0xADF1, model_new_game_init), ("new_board_init", 0xAE02, model_new_board_init), ("advance_level", 0xAC75, model_advance_level),
                              ("draw_ready_screen", 0xAD0E, model_draw_ready_screen)):
        out.append((name,) + check_group(name, lambda m, i, a=addr: m.call(a), lambda mem, i, f=model: f(mem), n, 99 + addr))
    return out


def check_level_complete(n=4000):
    return check_group("level_complete_step", lambda m, i: m.call(0xAC18), lambda mem, i: model_level_complete_step(mem), n, 100,
                       setup=lambda m, rng, i: (m.mem.__setitem__(0x27, rng.choice([0, 1, 2, 3, 4, 5, 9])), m.mem.__setitem__(0x28, rng.choice([0, 0, 1, 5])), m.mem.__setitem__(0x29, rng.choice([1, 2, 3, 7]))))


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_death_sequence(mem):
    s = mem[0xED]
    if s == 1:
        if mem[0xEE] != 0:
            model_toggle_leg_phase(mem)
            for x in (3, 2, 1, 0):
                M3.model_step_and_draw(mem, x, mem[ENTITY_DIR + x])
            mem[0xEE] = (mem[0xEE] - 1) & 0xFF
            return
        mem[0xED] += 1
        s = mem[0xED]
    if s == 2:
        for x in range(4):
            mem[0xD000 + x] = 0
        mem[0xF0] = mem[0xEF] = 0x35
        for k in range(8):
            mem[0xD200 + k] = 0
        mem[0xF1] = mem[0xEB] = 0
        mem[0xEA] = (mem[0xEA] + 1) & 0xFF
        mem[0xEC] = 7
        mem[0xED] = 3
        s = 3
    if s == 4:
        mem[0xD201] = 0xA8
        mem[0xD200] = mem[0xF0]
        mem[0xF0] = (mem[0xF0] - 8) & 0xFF
        mem[0xF1] = (mem[0xF1] - 1) & 0xFF
        if mem[0xF1] != 0:
            return
        if mem[0xEF] == 0x6D:
            mem[0xED] = (mem[0xED] + 1) & 0xFF
            return
        mem[0xEF] = (mem[0xEF] + 4) & 0xFF
        mem[0xF0] = mem[0xEF]
        mem[0xED] = 3
        return
    if s == 5:
        mem[0xD201] = 0xA8
        mem[0xD200] = mem[0xEF]
        mem[0xEF] = (mem[0xEF] - 8) & 0xFF
        if mem[0xEF] == 0x25:
            for k in range(8):
                mem[0xD200 + k] = 0
            mem[0xF1] = 0x80
            mem[0xED] = (mem[0xED] + 1) & 0xFF
        return
    if s == 6:
        if mem[0xF1] == 0:
            mem[0x24] = (mem[0x24] + 1) & 0xFF
        else:
            mem[0xF1] -= 1
        return
    mem[0xD201] = 0xA8                                       # state 3 and every other value ($AE92)
    mem[0xD200] = mem[0xF0]
    mem[0xF0] = (mem[0xF0] + 8) & 0xFF
    mem[0xF1] = (mem[0xF1] + 1) & 0xFF
    if mem[0xF1] == 4:
        mem[0xED] = 4


def model_death_animation(mem):
    if mem[0xEA] == 0:
        return
    base = 0x2300 | mem[0x89]
    mem[0x3E], mem[0x3F] = mem[0x89], 0x23
    advance = True
    if mem[0xEC] != 0:
        mem[0xEC] = (mem[0xEC] - 1) & 0xFF
        advance = bool(mem[0xEC] & 0x80)                     # `dec / bpl`: a negative result goes on to the next picture
    if advance:
        if mem[0xEB] == 0x0F:
            for y in range(16):
                mem[base + y] = 0
            mem[0xEA] = 0
            return
        mem[0xEB] = (mem[0xEB] + 1) & 0xFF
        mem[0xEC] = 7
    eb = mem[0xEB]
    if eb == 0:
        for x in range(9, -1, -1):
            mem[base + 3 + x] = rd(0xBB38 + x)
    elif eb == 0x0F:
        for x in range(16):
            mem[base + x] = rd(0xBC07 + x)
    else:
        x = (eb - 1) & 0xFF
        y = (mem[0x0600 + x] - 1) & 0xFF
        mem[base + y] = rd(0xBB57 + x)


def check_death_sequence(n=12000, seed=101):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for i in range(n):
        m = A.fresh(base)
        setup_game(m, rng)
        m.mem[0xED] = rng.choice([0, 1, 1, 2, 3, 4, 5, 6, 7, 0xFF])
        m.mem[0xEE] = rng.choice([0, 1, 0x60, rng.randrange(256)])
        m.mem[0xEF] = rng.choice([0x35, 0x6D, 0x69, 0x2D, 0x25, 0x2D, rng.randrange(256)])
        m.mem[0xF0] = rng.choice([0x35, 0x6D, rng.randrange(256)])
        m.mem[0xF1] = rng.choice([0, 1, 3, 0x80, rng.randrange(256)])
        mem = bytearray(m.mem)
        m.call(0xAE3D)
        model_death_sequence(mem)
        d = diff(m, mem)
        if d:
            bad.append((hex(mem[0xED]), [hex(k) for k in d[:4]]))
    m = A.fresh(base)                                         # a whole death, frame after frame
    for a in range(0x100):
        m.mem[a] = 0
    m.mem[0xED], m.mem[0xEE] = 1, 0x60
    m.mem[ENTITY_DIR:ENTITY_DIR + 4] = bytes([1, 2, 4, 8])
    mem = bytearray(m.mem)
    for f in range(900):
        m.call(0xAE3D)
        model_death_sequence(mem)
        if diff(m, mem):
            bad.append(("frame", f))
            break
    return n + 900, bad


def check_death_animation(n=12000, seed=102):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for i in range(n):
        m = A.fresh(base)
        setup_game(m, rng)
        m.mem[0xEA] = rng.choice([0, 1, 1, 1])
        m.mem[0xEB] = rng.choice([0, 1, 5, 13, 14, 15, rng.randrange(256)])
        m.mem[0xEC] = rng.choice([0, 1, 2, 7, 0x80, 0x81, rng.randrange(256)])
        m.mem[0x89] = rng.choice([0x64, rng.randrange(256)])
        mem = bytearray(m.mem)
        m.call(0xAEF7)
        model_death_animation(mem)
        d = diff(m, mem)
        if d:
            bad.append((hex(mem[0xEB]), [hex(k) for k in d[:4]]))
    m = A.fresh(base)                                         # a whole animation
    m.mem[0xEA], m.mem[0xEB], m.mem[0xEC], m.mem[0x89] = 1, 0, 7, 0x64
    mem = bytearray(m.mem)
    for f in range(160):
        m.call(0xAEF7)
        model_death_animation(mem)
        if diff(m, mem):
            bad.append(("frame", f))
            break
    return n + 160, bad


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def report():
    L = []
    P = L.append
    P("Fifth set of algorithm models against the ROM executed in tools/cpu6502.py (tools/algorithm_models5.py, OV-58); whole memory (zero page, $0200-$9FFF, $D000-$D7FF) compared after every call")
    P("")
    R = []
    n, bad, r = check_compare_high_score()
    P("compare_high_score: %d calls (both score cells, equal / lower / higher at every digit): %d differences (%d replaced)" % (n, len(bad), r))
    R.append(("compare_high_score", bad))
    n, bad, k = check_clip()
    P("clip_entity / clip_entities: %d calls (entities at the tunnel ends, wrapping right and left, Pac-Man's MazePtr, the sprite image masked): %d differences (%d masked)" % (n, len(bad), k))
    R.append(("clip", bad))
    n, bad = check_bonus_sound()
    P("bonus_sound / toggle_leg_phase: %d calls (every step of the fruit sound and 300 frames in a row): %d differences" % (n, len(bad)))
    R.append(("bonus_sound", bad))
    for nm, f in (("draw_level_indicator", check_draw_level_indicator), ("draw_lives", check_draw_lives), ("draw_all_in_place", check_draw_all), ("labels (clear text, blink, 1UP / 2UP)", check_labels),
                  ("load_shadow_colors / copies / clear_player_memory / power pellets", check_colours_copies), ("siren", check_siren), ("level_complete_step", check_level_complete)):
        n, bad = f()
        P("%s: %d calls (random state): %d differences" % (nm, n, len(bad)))
        R.append((nm, bad))
    for nm, f in (("death_sequence", check_death_sequence), ("death_animation", check_death_animation)):
        n, bad = f()
        P("%s: %d calls (every state 0-7 and beyond, and a whole death frame by frame): %d differences" % (nm, n, len(bad)))
        R.append((nm, bad))
    for nm, n, bad in check_init_and_levels():
        P("%s: %d calls (random state, every Level clamp, both players): %d differences" % (nm, n, len(bad)))
        R.append((nm, bad))
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
