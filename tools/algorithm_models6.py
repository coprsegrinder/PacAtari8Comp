"""OV-58, sixth set: the display (display-list interrupts, display list set-up, title score clearing) and the key loop of `Start`, run against models (method: tools/algorithm_models2.py).

  set_display_list      SetDisplayList $A6B5
  init_display2         InitDisplay2 $A610 (the stray copy into the ROM at its end has no effect)
  title_clear           TitleClearScores1P $A632 / TitleClearScores2P $A64E
  dli1, dli2            DliHandler1 $A573 / DliHandler2 $A5CE (run with an interrupt frame, they end with RTI)
  key_loop              one pass of the key loop $A4BA-$A571 (colours, pause key, joystick button, START / SELECT / OPTION with the debounce) and the restart at $A477
The loop waits for the vertical blank (the debounce counter $45, the jiffy clock, the console switches): the run of the ROM code simulates what the interrupt and the user do at exactly those points
(the hooks are listed in `run_key_loop`); the model takes the same inputs.
Usage: python -I tools/algorithm_models6.py [--write analysis/evidence-algorithms6-summary.txt]
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models2 as M2  # noqa: E402
import algorithm_models3 as M3  # noqa: E402
import algorithm_models5 as M5  # noqa: E402

ROOT = A.ROOT
rd = A.rd
diff = M2.diff
CP = A.CURRENT_PLAYER


def call_interrupt(m, addr, limit=100000):
    """enter a handler as the CPU does for an interrupt: push PCH, PCL, P; the RTI of the handler returns to the sentinel"""
    s = m.SENTINEL
    m.push(s >> 8)
    m.push(s & 0xFF)
    m.push(m.p(0))
    m.pc = addr
    n = 0
    while m.pc != s:
        m.step()
        n += 1
        if n > limit:
            raise RuntimeError("interrupt handler did not return")
    return n


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_set_display_list(mem, x, y):
    mem[0x0230] = mem[0xD402] = x
    mem[0x0231] = mem[0xD403] = 0xBF
    mem[0x0200] = y
    mem[0x0201] = 0xA5


def model_init_display2(mem):
    for x in range(8):
        mem[0xD000 + x] = 0
        mem[0xD200 + x] = 0
    model_set_display_list(mem, 0x81, 0xCE)
    for y in range(4):
        mem[0x02C4 + y] = rd(0xBBEA + y)
    mem[0x3F] = (0x24 + 0x81) & 0xFF                         # the tail $B985: the 16-byte copy goes to $A5xx, in the ROM, and is ignored


def model_title_clear(mem, players):
    if players == 1:
        for x in range(6, -1, -1):
            mem[0x2020 + x] = mem[0x2047 + x] = mem[0x202A + x] = 0
    else:
        for x in range(6, -1, -1):
            mem[0x202A + x] = mem[0x2047 + x] = 0
        M5.model_draw_label(mem, 2)
        mem[0x204B] = mem[0x204C] = 0x10
    M5.model_draw_label(mem, 1)                              # $A642: shared by both
    mem[0x202E] = mem[0x202F] = 0x10


def dli_clear(mem, x):
    """$A5BF: `sta COLPM0,x / dex / bpl`: the loop ends when X becomes negative, so a start value of $80 or more writes one byte only"""
    k = x & 0xFF
    while True:
        mem[0xD012 + k] = 0
        k = (k - 1) & 0xFF
        if k & 0x80:
            break
    mem[0xD019] = 0


def model_dli1(mem):
    x = mem[0x18]
    if x == 0:
        mem[0xD40A] = mem[0xD409] = 0x30
    elif x == 1:
        a = (mem[0xA0] ^ mem[0x4F]) & mem[0x4E]
        mem[0xD40A] = mem[0xD017] = a
        mem[0xD018] = mem[0x5E]
        if mem[0x5E] == 0:                                   # `bne` on the colour just loaded into X: a black band falls into the clearing loop of $A5BC with X = $FF
            dli_clear(mem, 0xFF)
    elif x == 2:
        mem[0xD40A] = mem[0xD017] = mem[0x5F]
        if mem[0x5F] == 0:
            dli_clear(mem, 1)
    elif x == 3:
        mem[0xD40A] = mem[0xD019] = mem[0x60]
        mem[0xD016] = mem[0x61]
        if mem[0x61] == 0:
            dli_clear(mem, 0xFF)
    else:
        dli_clear(mem, x - 1)
    mem[0x18] = (mem[0x18] + 1) & 0xFF


def model_dli2(mem):
    x = mem[0x18]
    if x == 0:
        mem[0xD40A] = mem[0x5E]
        mem[0xD409] = 0x18
        mem[0xD018] = mem[0x5E]
        mem[0xD017] = mem[0x5F]
    else:
        mem[0xD40A] = mem[0xD409] = rd(0xBDD1 + x)
    mem[0x18] = (mem[0x18] + 1) & 0xFF


def prepare(base, rng):
    m = A.fresh(base)
    for a in range(0x100):
        m.mem[a] = rng.randrange(256)
    for k in range(0x2000, 0x2100):
        m.mem[k] = rng.randrange(256)
    return m


def check_simple(n=2500):
    base = A.started_machine()
    rng = random.Random(110)
    bad = {}
    for i in range(n):
        which = i % 6
        m = prepare(base, rng)
        m.mem[0x18] = rng.randrange(8)
        for a in (0x5E, 0x5F, 0x60, 0x61):
            if rng.random() < 0.3:
                m.mem[a] = 0                                 # a black band: the branches that fall through
        m.mem[0x3C], m.mem[0x3D] = rng.randrange(256), 0x08 + rng.randrange(8)          # the pointer of the stray copy: RAM, not hardware
        mem = bytearray(m.mem)
        if which == 0:
            x, y = rng.randrange(256), rng.randrange(256)
            m.call(0xA6B5, x=x, y=y)
            model_set_display_list(mem, x, y)
        elif which == 1:
            m.call(0xA610)
            model_init_display2(mem)
        elif which == 2:
            m.call(0xA632)
            model_title_clear(mem, 1)
        elif which == 3:
            m.call(0xA64E)
            model_title_clear(mem, 2)
        elif which == 4:
            call_interrupt(m, 0xA573)
            model_dli1(mem)
        else:
            call_interrupt(m, 0xA5CE)
            model_dli2(mem)
        d = diff(m, mem)
        if d:
            bad.setdefault(which, []).append([hex(k) for k in d[:4]])
    return n, bad


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def model_restart(mem):
    """$A477: after START (zero page $20-$3F cleared, stack reset, the tables copied, the title or the first board set up)"""
    for x in range(0x20, 0x40):
        mem[x] = 0
    for k in range(8):
        mem[0xD200 + k] = 0
    M5.model_copy(mem, 0x0800, 0x0C00)
    M5.model_copy(mem, 0x0C00, 0x1000)
    M5.model_copy(mem, 0x0C00, 0x1400)
    if mem[0x19] != 0:
        return
    mem[0x14] = (mem[0x14] + 1) & 0xFF                       # the wait for the next jiffy
    model_set_display_list(mem, 0xA3, 0x73)
    mem[0x026F] = 0x11
    M5.model_init_board(mem)
    M5.model_new_game_init(mem)
    model_title_clear(mem, 2 if mem[0x1A] else 1)
    mem[0x1C] = 2


def model_key_pass(mem, bounce=None):
    """one pass of the key loop from $A4BA to the next arrival at $A4BA; returns a word about the way taken"""
    for x in range(3, -1, -1):
        mem[0x5E + x] = (rd(0xBBEE + x) ^ mem[0x4F]) & mem[0x4E]
    path = "loop"
    start = False
    if mem[0x19] == 0:
        if mem[0x02F1] == 0 and mem[0x02FC] == 0x21:
            mem[0x9B] = 0 if mem[0x9B] else 1
            mem[0x02FC] = 0xFF
        if mem[0x20] != 0:
            if mem[0x1E] == 0:
                mem[0x19] = mem[0x4D] = 4
                return "demo-end"
            check_buttons = True
        else:
            check_buttons = False
    else:
        check_buttons = True
    if check_buttons:
        mem[0x02FC] = 0xFF
        if mem[0x0284] == 0 or mem[0x0285] == 0:
            start = True
    if not start:
        c = mem[0xD01F]
        if c == 7:
            return "idle"
        if bounce is not None:                               # the switch bounced during the debounce: the new value is read afresh ($A504)
            mem[0x46] = c
            mem[0x45] = 0
            c = bounce
            if c == 7:
                mem[0xD01F] = 7
                return "bounce-idle"
        mem[0x46] = c
        mem[0x45] = 0
        mem[0xD01F] = 7                                      # the user releases the switch
        if c == 6:
            start = True
        elif mem[0x19] < 3:
            mem[0x19] = mem[0x4D] = 3
            return "switch-early"
        elif c == 3:
            sl = mem[0x1B]
            if sl < 2:
                mem[0x1B] += 1
            elif sl == 0x0C:
                mem[0x1B] = 0
            else:
                mem[0x1B] += 2
            mem[0x19] = mem[0x4D] = 3
            return "option"
        elif c == 5:
            mem[0x1A] = 0 if mem[0x1A] else 1
            mem[0x19] = mem[0x4D] = 3
            return "select"
        else:
            return "ignored"
    mem[0x20] = 0
    mem[0x19] = 0
    mem[0x1C] = 1
    model_restart(mem)
    return "start"


def run_key_loop(m, bounce=None, spins=0, limit=2000000):
    """the ROM from $A4BA to the next arrival there, with the hooks for the interrupt and the user: `spins` waits of every kind go round once more before the event happens,
    `bounce` (a value) is the console value after the first read of the debounce $A511 (a switch that bounces)"""
    m.pc = 0xA4BA
    n = 0
    seen = {}
    while True:
        pc = m.pc
        if n > 0 and pc == 0xA4BA:
            return n
        if pc in (0xA514, 0xA51C, 0xA493):
            seen[pc] = seen.get(pc, 0) + 1
        if pc == 0xA511 and bounce is not None and 0xA511 not in seen:
            seen[0xA511] = 1
            m.mem[0xD01F] = bounce
        if pc == 0xA514 and seen[pc] > spins:
            m.mem[0x45] = 0                                  # the vertical-blank interrupt counts the debounce counter down
        elif pc == 0xA51C and seen[pc] > spins:
            m.mem[0xD01F] = 7                                # the switch is released
        elif pc == 0xA493 and seen[pc] > spins:
            m.mem[0x14] = (m.mem[0x14] + 1) & 0xFF           # a jiffy passes
        m.step()
        n += 1
        if n > limit:
            raise RuntimeError("key loop does not come back")


def check_key_loop(n=5000, seed=111):
    base = A.started_machine()
    rng = random.Random(seed)
    bad, ways = [], {}
    for i in range(n):
        m = prepare(base, rng)
        m.mem[0x19] = rng.choice([0, 0, 1, 2, 3, 4, 5])
        m.mem[0x1A] = rng.randrange(2)
        m.mem[0x1B] = rng.choice([0, 1, 2, 4, 6, 8, 10, 12, 3, 13])
        m.mem[0x1E] = rng.choice([0, 0, 5])
        m.mem[0x20] = rng.choice([0, 0, 1])
        m.mem[0x9B] = rng.randrange(2)
        m.mem[0x1C] = rng.randrange(4)
        m.mem[0x02F1] = rng.choice([0, 0, 1])
        m.mem[0x02FC] = rng.choice([0x21, 0x21, 0xFF, 0x00, 0x1C])
        m.mem[0x0284] = rng.choice([1, 1, 1, 0])
        m.mem[0x0285] = rng.choice([1, 1, 1, 0])
        m.mem[0xD01F] = rng.choice([7, 6, 5, 3, 4, 2, 1, 0, 6, 5, 3])
        m.mem[0x3C], m.mem[0x3D] = rng.randrange(256), 0x08 + rng.randrange(8)
        for k in range(0x0800, 0x0C00):
            m.mem[k] = rng.randrange(256)
        for k in range(0x1000, 0x1800):
            m.mem[k] = rng.randrange(256)
        mem = bytearray(m.mem)
        bounce = None
        if rng.random() < 0.2 and m.mem[0xD01F] != 7:
            bounce = rng.choice([c for c in range(8) if (c | m.mem[0xD01F]) != m.mem[0xD01F]] or [7])
        run_key_loop(m, bounce=bounce, spins=rng.choice([0, 0, 1]))
        way = model_key_pass(mem, bounce)
        ways[way] = ways.get(way, 0) + 1
        d = diff(m, mem)
        if d:
            bad.append((way, [hex(k) for k in d[:4]]))
    return n, bad, ways


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def report():
    L = []
    P = L.append
    P("Sixth set of algorithm models against the ROM executed in tools/cpu6502.py (tools/algorithm_models6.py, OV-58); whole memory (zero page, $0200-$9FFF, $D000-$D7FF) compared after every call")
    P("")
    R = []
    n, bad = check_simple()
    names = ["set_display_list", "init_display2", "title_clear_1p", "title_clear_2p", "dli1", "dli2"]
    P("display routines: %d calls over %s (random zero page and every DLI band number): %d differences" % (n, ", ".join(names), sum(len(v) for v in bad.values())))
    R.append(("display", [t for v in bad.values() for t in v]))
    n, bad, ways = check_key_loop()
    P("key_loop: %d passes (every title state 0-5, CONSOL 7 / 6 / 5 / 3 and others, space bar, joystick buttons, demo timer, the restart with the first board; the ways taken: %s): %d differences" % (n, ", ".join("%s %d" % kv for kv in sorted(ways.items())), len(bad)))
    R.append(("key_loop", bad))
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
