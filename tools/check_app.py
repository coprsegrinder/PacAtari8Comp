"""Stage 78d: the whole program in port form (tools/core_app.py) against the ROM from power-on, frame by frame.  The ROM runs on the concrete 6502 as the real machine runs it: `Start` from the RUN address with the RAM
cleared and the OS values in place, then every frame the OS's clock tick, the inputs of the frame (the stick, trigger, console, keyboard shadows, the collision registers, RANDOM), the deferred vertical-blank handler `$A5FD`
entering between two instructions of the main program (the registers are kept as an interrupt keeps them) and the main program for the rest of the frame (a fixed budget of instructions: it ends in a wait or in idle passes).
The port runs the same inputs; after every frame the whole state is compared: the zero page (except the declared scratch bytes), the maze and its three copies, the title screen, the status rows, the shadows, the
player-missile pages, the positions, the picture buffers, the ordered chip writes, the RANDOM count, and where the main program is (a pass, the debounce, the release, the clock wait) with its accumulator.
Usage: python -I tools/check_app.py [--frames N] [--seed S] [--write analysis/evidence-app-summary.txt]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import analyze_collide as AC  # noqa: E402
import check_app_board as CAB  # noqa: E402
import check_app_frame as CAF  # noqa: E402
import check_ghost as CG  # noqa: E402
import check_play as CPL  # noqa: E402
import core_app as APP  # noqa: E402
import core_draw as D  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402
import platform_iface as PI  # noqa: E402

ROOT = A.ROOT
CHUNK = 800                         # instructions of the main program between two looks for a settled state
MAX_CHUNKS = 400
NO_KEY = 0xFF


class GameScript(PI.GtiaCollisions):
    """the inputs of a session: a stick that changes direction now and then, console keys at given frames, a trigger, the clock counting frames, RANDOM from a list given for each frame, the collision registers computed
    from the World as the GTIA computes them (tools/gtia_collisions.py: docs/50)"""

    def __init__(self, seed, charset, keys=None, triggers=None, stick_period=(8, 40), sticks=None, keyboard=None):
        super().__init__(lambda w: D.scene(w, charset))
        self.rng = random.Random(seed)
        self.keys = keys or {}                 # frame -> console value ($06 START, $05 SELECT, $03 OPTION) held that frame
        self.triggers = triggers or {}         # frame -> STRIG0 value
        self.keyboard = keyboard or {}         # frame -> a key code the OS stores in CH ($21 = the space bar); the OS then holds the keyboard for three frames (KEYDEL)
        self.t = 0
        self.cur = 0x0F
        self.until = 0
        self.stick_period = stick_period
        self.choices = sticks or [0x0E, 0x0D, 0x0B, 0x07, 0x0F, 0x0A, 0x06, 0x09, 0x05]
        self.queue = []

    def begin_frame(self):
        if self.t >= self.until:
            self.cur = self.rng.choice(self.choices)
            self.until = self.t + self.rng.randrange(*self.stick_period)
        self.queue = [self.rng.randrange(256) for _ in range(64)]
        self.given = list(self.queue)
        self.taken = []

    def stick(self, port):
        return self.cur if port == 0 else 0x0F

    def trigger(self, port):
        return self.triggers.get(self.t, 1) if port == 0 else 1

    def console(self):
        return self.keys.get(self.t, 7)

    def key(self):
        return self.keyboard.get(self.t, 0xFF)

    def key_delay(self):
        for back in (1, 2, 3):
            if (self.t - back) in self.keyboard:
                return 4 - back
        return 0

    def clock(self):
        return self.t & 0xFF

    def attract(self):
        return 0xFF, 0x00

    def random(self):
        v = self.queue.pop(0)
        self.taken.append(v)
        return v


class RomApp:
    """the ROM on the concrete 6502"""

    def __init__(self, clock=0):
        self.m = m = C.Machine(A.ROM)
        m.mem[0x10] = 0xC0                       # POKMSK
        m.mem[0x14] = clock & 0xFF               # RTCLOK2
        m.mem[0x5E], m.mem[0x5F] = 0x42, 0x9C    # DliColors, left by the OS
        for k in range(4):
            m.mem[0x0278 + k] = 0x0F
        m.mem[0x0284] = m.mem[0x0285] = 1
        m.mem[0x02FC] = 0xFF
        m.mem[0xD01F] = 7
        m.s = 0xFF
        m.i = 0
        m.d = 0
        m.pc = 0xA386
        n = 0
        C.Machine.wr = CAB._wr                   # the chip writes of Start are logged too
        C.Machine.rd = CPL._rd
        del CAB.LOG[:]
        while m.pc != 0xA4BA:                    # Start, the restart clear and the copies, to the first pass of the main program
            if m.pc >= 0xC000:
                m.os_calls.append(m.pc)
                lo, hi = m.pull(), m.pull()
                m.pc = (((hi << 8) | lo) + 1) & 0xFFFF
                continue
            m.step()
            n += 1
            assert n < 3000000
        self.hw = [0] * 16

    def frame(self, p, collisions):
        m = self.m
        m.mem[0x14] = p.clock() & 0xFF
        m.mem[0x0278], m.mem[0x0279] = p.stick(0) & 0xFF, p.stick(1) & 0xFF
        m.mem[0x0284], m.mem[0x0285] = p.trigger(0) & 0xFF, p.trigger(1) & 0xFF
        k = p.key() & 0xFF
        if k != NO_KEY:
            m.mem[0x02FC] = k
        m.mem[0x02F1] = p.key_delay() & 0xFF
        m.mem[0x4E], m.mem[0x4F] = p.attract()
        m.mem[0xD01F] = p.console() & 0xFF
        m.hw = list(collisions)
        m.random = list(p.given)
        m.random_reads = []
        del CAB.LOG[:]
        keep = (m.a, m.x, m.y, m.s, m.p(), m.pc)
        m.call(0xA5FD)                           # the deferred vertical-blank handler, entering between two instructions of the main program
        m.a, m.x, m.y, m.s = keep[0], keep[1], keep[2], keep[3]
        m.set_p(keep[4])
        m.pc = keep[5]
        # the main program for the rest of the frame.  It is given as much time as it needs to reach a wait or to idle (the restart's copies alone take more than a frame of the real machine: the model of core_app.key_loop
        # runs the program to its next wait; the frames in between see only the handler's own state): chunks of instructions until two chunk ends show the same zero page, shadows and screen memory
        last = None
        for _ in range(MAX_CHUNKS):
            for _ in range(CHUNK):
                if m.pc >= 0xC000:
                    lo, hi = m.pull(), m.pull()
                    m.pc = (((hi << 8) | lo) + 1) & 0xFFFF
                    continue
                m.step()
            snap = (bytes(m.mem[0:0x100]), bytes(m.mem[0x200:0x300]), bytes(m.mem[0x0C00:0x1800]))
            if snap == last and (0xA4BA <= m.pc <= 0xA572 or 0xA493 <= m.pc <= 0xA495):      # unchanged, and in the main program's own loop or the clock wait (not in the middle of a copy that happens to copy equal bytes)
                break
            last = snap
        else:
            raise RuntimeError("the main program of the ROM did not settle")

    def phase(self):
        m = self.m
        pc = m.pc
        if 0xA493 <= pc <= 0xA495:
            return ("clock_wait", 0, m.a)
        if 0xA511 <= pc <= 0xA517:
            return ("debounce", m.a, 0)
        if 0xA51C <= pc <= 0xA520:
            return ("release", m.a, 0)
        return ("top", 0, 0)


def diffs(rom, app, rnd_used):
    d = CAB.diffs(rom.m, app.w, CG.SCRATCH)
    if len(rom.m.random_reads) != rnd_used:
        d.append("random %d != %d" % (len(rom.m.random_reads), rnd_used))
    if rom.phase() != app.kl.state():
        d.append("main program %s != %s" % (rom.phase(), app.kl.state()))
    return d


def compare_start(clock=0):
    """Start and the restart clear, from power-on: the state at the first pass of the main program"""
    rom = RomApp(clock)
    p = GameScript(0, AC.rom_charset())
    app = APP.App(p, clock=clock)
    # the chip-write log of the restart clear (the sound registers cleared) is in both
    return CAB.diffs(rom.m, app.w, CG.SCRATCH)


def run_game(seed, frames, keys=None, triggers=None, clock=0, stop=None, sticks=None, charset=None, on_frame=None, keyboard=None, before_frame=None):
    """the port and the ROM side by side for `frames` frames; returns (the first (frame, differences) or None, the classes of the frames, the port App)"""
    cs = charset or AC.rom_charset()
    p = GameScript(seed, cs, keys, triggers, sticks=sticks, keyboard=keyboard)
    rom = RomApp(clock)
    p.t = clock
    app = APP.App(p, clock=clock)
    p.t = clock
    classes = []
    first = None
    try:
        for f in range(frames):
            p.begin_frame()
            if before_frame:
                before_frame(f, app, rom)
            cls = APP.frame_class(app.w)
            coll = p.collisions(app.w)
            rom.frame(p, coll)
            used = app.frame()
            p.t = clock + f + 1
            classes.append(cls)
            d = diffs(rom, app, used)
            if d:
                first = (f, d[:5])
                break
            if on_frame:
                on_frame(f, app, rom)
            if stop and stop(app):
                break
    finally:
        C.Machine.wr = CAB._orig
        C.Machine.rd = CPL._orig_rd
    return first, classes, app


def runs(classes):
    out = []
    for c in classes:
        if out and out[-1][0] == c:
            out[-1][1] += 1
        else:
            out.append([c, 1])
    return out


def main():
    a = sys.argv
    frames = int(a[a.index("--frames") + 1]) if "--frames" in a else 1500
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 1
    print("start:", compare_start())
    first, classes, app = run_game(seed, frames, keys={k: 6 for k in range(480, 486)})
    print("frames run:", len(classes), "first difference:", first)
    for c, n in runs(classes)[:40]:
        print("  %-22s %d" % (c, n))
    return 1 if first else 0


if __name__ == "__main__":
    sys.exit(main())
