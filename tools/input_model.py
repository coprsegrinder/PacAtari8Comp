"""Stage 63 (input processing): the joystick path of `MovePacMan` (`$B182-$B1C4`, then the dispatch on the direction) as an executable model, and its exhaustive comparison with the real code on the concrete 6502.

State (zero page): `zp_2A` = the directions open at Pac-Man's cell (JunctionLookup, bit 0 up, 1 down, 2 left, 3 right), `zp_AC` = the WANTED direction (the last direction the stick asked for: it stays when the stick is released),
`PacDirection` ($93) = the direction Pac-Man goes, `ATRACT` ($4D) = the OS attract timer (the stick value is written into it: a non-zero value resets it), `zp_A8` = the CORNER flag (set when Pac-Man changes between a horizontal and a vertical direction).
Directions: 1 up, 2 down, 4 left, 8 right.  `STICK0,x` (x = the player on turn) is the OS shadow of the PIA port: bit 0 up, 1 down, 2 left, 3 right, 0 = pressed.
Usage: python -I tools/input_model.py [--exhaustive]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

UP, DOWN, LEFT, RIGHT = 1, 2, 4, 8
NAMES = {0: "none", 1: "up", 2: "down", 4: "left", 8: "right"}


def popcount4(v):
    return bin(v & 0x0F).count("1")


def steer(stick, open_dirs, direction, wanted, atract, corner=0):
    """one frame of the input path from `$B183` to `$B1C4`: -> (wanted, direction, atract, corner)"""
    # the buffered turn ($B183-$B19D): the wanted direction is taken as soon as it is open
    if wanted & open_dirs:
        if wanted != direction:
            both = wanted | direction
            if (both & 0x03) and (both & 0x0C):                    # one vertical and one horizontal bit: a corner (also for the odd multi-bit values)
                corner = both
        direction = wanted
    # the stick ($B19F-$B1C2)
    pressed = (stick ^ 0x0F) & 0xFF
    if pressed != 0 and popcount4(pressed) != 2:                  # nothing pressed: nothing changes; exactly two directions (a diagonal or two opposite): refused
        atract = pressed
        wanted = pressed
        if pressed & open_dirs:                                   # the new direction is open now: taken at once (this is how a reversal works)
            direction = pressed
    return wanted, direction, atract, corner


def motion(direction, open_dirs):
    """what the code does with the direction ($B1C4-$B1E0): 'up' 'down' 'left' 'right' (the case is entered; it moves unless the frame is skipped by `zp_A7`), 'blocked' (the direction is not open: Pac-Man stands, `$B2AA`),
    'none' (open in some bit but not one of the four directions: no movement, `$B2CE`)"""
    if not (direction & open_dirs):
        return "blocked"
    return {1: "up", 2: "down", 4: "left", 8: "right"}.get(direction, "none")


# the pc each case of the real code is entered at
CASES = {0xB1E3: "up", 0xB211: "down", 0xB23F: "right", 0xB271: "left", 0xB2AA: "blocked", 0xB2CE: "none"}


def run_code(m, stick, open_dirs, direction, wanted, atract=0x55, player=0):
    """run the real code on a concrete machine from `$B182` (just after `JunctionLookup`) to the case it enters; -> (wanted, direction, atract, corner, case)"""
    m.mem[0x2B] = player
    m.mem[0x0278 + player] = stick
    m.mem[0x2A] = open_dirs
    m.mem[0x93] = direction
    m.mem[0xAC] = wanted
    m.mem[0x4D] = atract
    m.mem[0xA8] = 0
    m.pc = 0xB182
    m.s = 0xF0
    n = 0
    while m.pc not in CASES:
        m.step()
        n += 1
        if n > 400:
            raise RuntimeError("the segment did not end")
    return m.mem[0xAC], m.mem[0x93], m.mem[0x4D], m.mem[0xA8], CASES[m.pc]


def check(sticks=range(16), dirs=range(16), players=(0,), atract=0x55, verbose=False):
    """the exhaustive comparison: every stick value x open set x direction x wanted direction; -> (cases, mismatches, first mismatches)"""
    import algorithm_models as A
    base = A.started_machine()
    m = A.fresh(base)
    bad = []
    n = 0
    for pl in players:
        for stick in sticks:
            for o in dirs:
                for d in dirs:
                    for w in dirs:
                        got = run_code(m, stick, o, d, w, atract, pl)
                        w2, d2, a2, c2 = steer(stick, o, d, w, atract)
                        want = (w2, d2, a2, c2, motion(d2, o))
                        n += 1
                        if got != want:
                            bad.append(((stick, o, d, w), got, want))
    return n, len(bad), bad[:5]


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# the contact test ($A84D-$A883): the collision registers M1PL and M2PL ($D009, $D00A) are read for each ghost in turn
def contact(m1pl, m2pl, pac_y, ghost_y, states):
    """-> ('none', None) | ('eaten', g) | ('death', g): ghost g (0 to 3, in this order, the first that qualifies) touches Pac-Man when its bit is set in BOTH registers (the two missiles that make Pac-Man's body overlap the ghost's player), it is within 4 lines
    of Pac-Man vertically, and its state has bit 6 clear (not the eyes); a ghost with bit 7 set (frightened) is eaten, any other kills Pac-Man"""
    for g in range(4):
        bit = 1 << g
        if states[g] & 0x40:
            continue
        if not (m1pl & bit) or not (m2pl & bit):
            continue
        if abs(pac_y - ghost_y[g]) >= 5:
            continue
        return ("eaten", g) if states[g] & 0x80 else ("death", g)
    return ("none", None)


CONTACT_STOPS = {0xA886: "eaten", 0xA923: "death", 0xA936: "none"}


def run_contact(m, m1pl, m2pl, pac_y, ghost_y, states):
    for g in range(4):
        m.mem[0xCE + g] = states[g]
        m.mem[0x85 + g] = ghost_y[g]
    m.mem[0x89] = pac_y
    m.mem[0xD009] = m1pl
    m.mem[0xD00A] = m2pl
    m.pc = 0xA84D
    m.s = 0xF0
    n = 0
    while True:
        if m.pc in CONTACT_STOPS:
            # $A87C is `jmp $A936` of the loop's end: the first stop reached is what the frame goes on with
            kind = CONTACT_STOPS[m.pc]
            return (kind, m.x if kind != "none" else None)
        m.step()
        n += 1
        if n > 600:
            raise RuntimeError("the contact test did not end")


def check_contacts(full=True, sample=None, seed=1):
    """the real code against `contact`: M1PL x M2PL (16 x 16, the four bits that matter) x the state classes of the four ghosts (bits 7 and 6) x near / far in Y for each ghost; sample: only that many random cases"""
    import random
    import algorithm_models as A
    m = A.fresh(A.started_machine())
    classes = (0x00, 0x80, 0x40, 0xC0)
    rng = random.Random(seed)
    bad, n = [], 0

    def one(m1, m2, st, near):
        pac_y = 128
        gy = [pac_y + (rng.choice([-4, -2, 0, 3, 4]) if nr else rng.choice([-120, -6, -5, 5, 6, 90])) for nr in near]
        got = run_contact(m, m1, m2, pac_y, gy, st)
        want = contact(m1, m2, pac_y, gy, st)
        return got, want, (m1, m2, st, gy)
    if full:
        import itertools
        for m1 in range(16):
            for m2 in range(16):
                for st in itertools.product(classes, repeat=4):
                    for near in itertools.product((True, False), repeat=4):
                        got, want, case = one(m1, m2, list(st), near)
                        n += 1
                        if got != want:
                            bad.append((case, got, want))
    else:
        for _ in range(sample or 5000):
            m1, m2 = rng.randrange(16), rng.randrange(16)
            st = [rng.choice(classes) | rng.choice([0, 1, 2, 4, 8, 0x10, 0x20, 0x02]) for _ in range(4)]
            near = [rng.random() < 0.6 for _ in range(4)]
            got, want, case = one(m1, m2, st, near)
            n += 1
            if got != want:
                bad.append((case, got, want))
    return n, len(bad), bad[:5]


if __name__ == "__main__":
    if "--exhaustive" in sys.argv:
        n, nb, first = check()
        print("joystick, exhaustive: %d cases, %d mismatches" % (n, nb), first)
        n, nb, first = check_contacts(full=True)
        print("contact test, exhaustive over M1PL x M2PL x ghost state classes x near/far: %d cases, %d mismatches" % (n, nb), first)
    else:
        print(steer(0x0B, 0x0C, RIGHT, 0, 0))
