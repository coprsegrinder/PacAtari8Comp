"""Stage 61 (startup): does the game depend on anything the power-on state does not give it?  The whole RAM is filled with random bytes (a different fill per seed), the OS-owned inputs get their documented values (docs/33), and
the ROM runs in tools/cpu6502.py exactly as the OS leaves it: the cartridge RUN entry `Start` ($A386), then the key loop with the vertical-blank handler entering at random places (as in tools/check_ov60_race.py), the
display-list interrupt handlers, the title, a START press and a game with a joystick that changes direction.  Every data read of an address that no earlier write (by the game, or the OS-owned inputs listed in OS_INPUTS) has set is
recorded ('read before write').  Result needed: none in game RAM, and the same game state for every fill of RAM.
Usage: python -I tools/startup_poison.py [seeds] [frames]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpu6502 as C  # noqa: E402
import algorithm_models as A  # noqa: E402
import algorithm_models6 as M6  # noqa: E402

# what the OS (and the player) put in memory before the cartridge runs and while it runs: docs/33-input-output.md
OS_INPUTS = {0x10: 0xC0, 0x14: 0x00, 0x4D: 0x00, 0x4E: 0xFE, 0x4F: 0x00,          # POKMSK, RTCLOK2, ATRACT, DRKMSK, COLRSH
             0x0278: 0x0F, 0x0279: 0x0F, 0x0284: 0x01, 0x0285: 0x01,               # STICK0/1, STRIG0/1
             0x02F1: 0x00, 0x02FC: 0xFF}                                           # keyboard shadow, CH
HARDWARE = range(0xD000, 0xD800)                                                   # CONSOL, collision registers, RANDOM, ... are inputs (docs/33)


class Poisoned(C.Machine):
    def __init__(self, rom, written):
        super().__init__(rom)
        self.written = written
        self.rbw = {}                                                              # address -> pc of the first read before a write

    def step(self):
        self.cur = self.pc
        super().step()

    def rd(self, a):
        a &= 0xFFFF
        if not self.written[a] and a < 0xA000:
            self.rbw.setdefault(a, set()).add((self.cur, self.cur in (0xB332, 0xB991) and self.mem[0x3F] >= 0xA0))     # (the reading instruction, was the destination pointer in ROM)
        return super().rd(a)

    def wr(self, a, v):
        a &= 0xFFFF
        if a < 0xA000:
            self.written[a] = 1
        super().wr(a, v)


def run(seed, frames, sched_seed=7, fill="random"):
    rng = random.Random(seed)
    written = bytearray(65536)
    m = Poisoned(A.ROM, written)
    for a in range(0, 0xA000):
        m.mem[a] = rng.randrange(256) if fill == "random" else 0
    for a, v in OS_INPUTS.items():
        m.mem[a] = v
        written[a] = 1
    for a in HARDWARE:
        written[a] = 1
        m.mem[a] = 0
    m.mem[0xD01F] = 0x07                                                           # CONSOL: no console key
    for a in range(0x100, 0x200):                                                  # the stack page: pushes and pulls are not data reads of the game
        written[a] = 1
    m.s = 0xFF
    m.i = 0
    m.d = 0
    sched = random.Random(sched_seed)                                              # the same schedule of interrupts and inputs for every fill
    m.pc = 0xA386
    started = False
    n_frames = 0
    state = {"start_frame": None}
    stick = 0x0F
    while n_frames < frames:
        burst = sched.randrange(300, 3000)
        for _ in range(burst):
            if m.pc >= 0xC000:                                                     # an OS entry (SETVBV): returns at once
                m.os_calls.append(m.pc)
                lo, hi = m.pull(), m.pull()
                m.pc = (((hi << 8) | lo) + 1) & 0xFFFF
                continue
            m.step()
        if 0xE45C not in m.os_calls:
            continue                                                               # SETVBV not called yet: no vertical blank (the OS would not call the handler)
        n_frames += 1
        m.mem[0x14] = (m.mem[0x14] + 1) & 0xFF                                     # the OS vertical blank counts the clock
        # the inputs of this frame
        if n_frames == 480:
            m.mem[0x0284] = 0                                                      # STRIG0 pressed: START the game
        if n_frames == 486:
            m.mem[0x0284] = 1
        if n_frames > 500 and n_frames % 40 == 0:
            stick = sched.choice([0x0E, 0x0D, 0x0B, 0x07, 0x0F])
        m.mem[0x0278] = stick
        m.random = [sched.randrange(256) for _ in range(40)]
        keep = (m.a, m.x, m.y, m.s, m.p(), m.pc)
        # the display-list interrupts of the screen (the handler is the one in VDSLST), then the deferred vertical-blank handler
        for _ in range(5 if m.mem[0x0200] | m.mem[0x0201] << 8 in (0xA573, 0xA5CE) else 0):
            M6.call_interrupt(m, m.mem[0x0200] | m.mem[0x0201] << 8)
        m.call(0xA5FD)
        m.a, m.x, m.y, m.s = keep[0], keep[1], keep[2], keep[3]
        m.set_p(keep[4])
        m.pc = keep[5]
        if state["start_frame"] is None and m.mem[0x19] == 0:
            state["start_frame"] = n_frames
    return m, state


def classify(runs):
    """-> {category: {address: set of reading pcs}}"""
    import analyze_stack as AS
    rom, F, owner = AS.load()
    out = {}
    for m, st in runs:
        for a, items in m.rbw.items():
            for pc, rom_dst in items:
                name = F[owner[pc]].name
                out.setdefault((name, rom_dst), {}).setdefault(a, set()).add(pc)
    return out


def ranges(addrs):
    addrs = sorted(addrs)
    out = []
    for a in addrs:
        if out and a == out[-1][1] + 1:
            out[-1][1] = a
        else:
            out.append([a, a])
    return out


def compare(zero, rnd):
    """addresses written by the game in the zero-fill run whose final value differs from a random-fill run"""
    diffs = set()
    for a in range(0, 0xA000):
        if 0x100 <= a < 0x200:
            continue
        if zero.written[a] and any(zero.mem[a] != r.mem[a] for r in rnd):
            diffs.add(a)
    return diffs


def main():
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    frames = int(sys.argv[2]) if len(sys.argv) > 2 else 900
    zero, zst = run(0, frames, fill="zero")
    runs = [run(s, frames) for s in range(1, seeds + 1)]
    print("frames", frames, "game started at frame", zst["start_frame"], [st["start_frame"] for m, st in runs])
    cl = classify(runs)
    print("read before write (routine, destination in ROM): ranges")
    for (name, rd), d in sorted(cl.items()):
        print("  %-24s %-5s %s   pcs %s" % (name, rd, " ".join("$%04X-$%04X" % tuple(r) if r[0] != r[1] else "$%04X" % r[0] for r in ranges(d)), " ".join("$%04X" % p for p in sorted({p for v in d.values() for p in v}))))
    diffs = compare(zero, [m for m, _ in runs])
    print("addresses written by the game that differ from the zero fill:", " ".join("$%04X-$%04X" % tuple(r) if r[0] != r[1] else "$%04X" % r[0] for r in ranges(diffs)))


if __name__ == "__main__":
    main()
