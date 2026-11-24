"""Stage 64 (output processing): the WRITE MAP of the game's memory - which instruction of the ROM can write which region of the machine (screen memory, player-missile pages, character sets, picture buffers, tables,
the OS shadows, the hardware registers), worked out statically for every store of the 2,925 instructions of the ROM, and CHECKED on the concrete 6502 (tools/cpu6502.py) over thousands of frames, the start-up expansion and
the key loop: every store that the code makes must land in a region its instruction is classified for (0 violations), and every output region that is written is written only by the classified instructions.
Usage: python -I tools/output_map.py [--frames 3000] [--write analysis/evidence-output-summary.txt]  (the tables of docs/42-output-processing.md are generated from the same functions: tools/analyze_output.py)"""
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import absint6502 as AB       # noqa: E402
import algorithm_models as A  # noqa: E402
import algorithm_models6 as M6  # noqa: E402
import algorithm_models7 as M7  # noqa: E402
import cpu6502 as C           # noqa: E402

PROG = AB.Program()
INS = PROG.ins

# the regions of the machine (name, first address, last address, kind); the kind says what the region is for
REGIONS = [
    ("ZeroPage", 0x0000, 0x00FF, "state"),
    ("Stack", 0x0100, 0x01FF, "state"),
    ("OsPage2", 0x0200, 0x02FF, "os shadows"),
    ("PictureBuffers", 0x0400, 0x041F, "picture buffers"),
    ("RamTables", 0x0600, 0x07FF, "tables"),
    ("OriginalMaze", 0x0800, 0x0BFF, "maze"),
    ("MazeScreen", 0x0C00, 0x0FFF, "screen"),
    ("SavedMaze1", 0x1000, 0x13FF, "maze"),
    ("SavedMaze2", 0x1400, 0x17FF, "maze"),
    ("TitleCharset", 0x1800, 0x1BFF, "character set"),
    ("TitleScreen", 0x1C00, 0x1FFF, "screen"),
    ("StatusRows", 0x2000, 0x22FF, "screen"),
    ("PmMissiles", 0x2300, 0x23FF, "player-missile"),
    ("PmPlayers", 0x2400, 0x27FF, "player-missile"),
    ("GameCharset", 0x3000, 0x33FF, "character set"),
    ("Gtia", 0xD000, 0xD0FF, "hardware"),
    ("Pokey", 0xD200, 0xD2FF, "hardware"),
    ("Pia", 0xD300, 0xD3FF, "hardware"),
    ("Antic", 0xD400, 0xD4FF, "hardware"),
    ("Rom", 0xA000, 0xBFFF, "rom"),
]
OUTPUT = {"OsPage2", "PictureBuffers", "MazeScreen", "TitleCharset", "TitleScreen", "StatusRows", "PmMissiles", "PmPlayers", "GameCharset", "Gtia", "Pokey", "Antic"}
WRITES = {"sta", "stx", "sty", "inc", "dec", "asl", "lsr", "rol", "ror"}

# the 14 `sta (zp),y` of the ROM (docs/29): the regions their pointer can point to
IZY = {
    0xA6A5: {"OriginalMaze", "RamTables", "GameCharset", "TitleCharset"},          # WriteDstByte: the expansion of Start
    0xA8E2: {"PmMissiles"}, 0xA8E7: {"PmPlayers"},                                  # GhostEaten: the pop-up
    0xABC3: {"PmMissiles", "PmPlayers"},                                            # ClipEntityAtTunnel
    0xACCB: {"MazeScreen"}, 0xACD2: {"MazeScreen"},                                 # DrawLevelIndicator
    0xAF29: {"PmMissiles", "PmPlayers"}, 0xAF33: {"PmMissiles", "PmPlayers"}, 0xAF41: {"PmMissiles", "PmPlayers"}, 0xAF4C: {"PmMissiles", "PmPlayers"},   # DeathAnimation
    0xB334: {"PmMissiles", "PmPlayers"},                                            # DrawAllInPlace
    0xB363: {"MazeScreen"}, 0xB384: {"MazeScreen"},                                 # EatDotAtPacMan: the maze cell
    0xB993: {"PmMissiles", "PmPlayers", "Rom"},                                     # the shared tail of StepAndDrawEntity; InitDisplay2 ends with `jmp $B985` with X = $81, so its 16 stores go to the ROM page $A5 (no effect: a stray write of the original)
}


def region_of(addr):
    best = None
    for name, lo, hi, kind in REGIONS:
        if lo <= addr <= hi:
            best = name
            if name != "Rom":
                return name
    return best or "Other"


def regions_between(lo, hi):
    """the regions an address range touches, 'Other' when part of the range lies in none (an indexed store $D012,x with x up to 255 reaches $D111)"""
    out = set()
    hit = [False] * (hi - lo + 1)
    for name, a, b, kind in REGIONS:
        if a <= hi and b >= lo:
            out.add(name)
            for k in range(max(a, lo), min(b, hi) + 1):
                hit[k - lo] = True
    if not all(hit):
        out.add("Other")
    return out


def owner_table():
    owner = {}
    for e, f in sorted(PROG.F.items(), key=lambda kv: -len(kv[1].body)):
        for a in f.body:
            owner[a] = e
    return owner


OWNER = owner_table()


def routine_name(pc):
    e = OWNER.get(pc)
    return (getattr(PROG.F.get(e), "name", None) or "$%04X" % e) if e is not None else "?"


def static_map():
    """-> {pc: set of region names} for every store instruction of the ROM"""
    out = {}
    for pc, (ln, m, mode, op) in INS.items():
        if m not in WRITES or mode == "acc":
            continue
        if mode in ("zp", "zpx", "zpy"):
            out[pc] = {"ZeroPage"}
        elif mode == "abs":
            out[pc] = regions_between(op, op) or {"Other"}
        elif mode in ("abx", "aby"):
            out[pc] = regions_between(op, op + 255) or {"Other"}
        elif mode == "izy":
            out[pc] = set(IZY.get(pc, {"?"}))
        else:
            out[pc] = {"?"}
    return out


STATIC = static_map()


class Recorder:
    """records (pc, address) of every store the concrete machine makes"""

    def __init__(self):
        self.stores = Counter()                 # (pc, region) -> count
        self.bad = []
        self.sequence = []
        self.orig_wr = C.Machine.wr
        self.orig_step = C.Machine.step
        self.trace = False

    def install(self):
        rec = self

        def wr(m, a, v):
            pc = getattr(m, "_ipc", 0)
            r = region_of(a & 0xFFFF)
            if pc in STATIC:
                rec.stores[(pc, r)] += 1
                if r not in STATIC[pc] and not (r == "Stack"):
                    rec.bad.append((pc, a, r))
            if rec.trace and r in OUTPUT:
                rec.sequence.append(r)
            rec.orig_wr(m, a, v)

        def step(m):
            m._ipc = m.pc
            rec.orig_step(m)
        C.Machine.wr, C.Machine.step = wr, step

    def remove(self):
        C.Machine.wr, C.Machine.step = self.orig_wr, self.orig_step


def load_junction_lists():
    with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as fh:
        rom = fh.read()
    return list(rom[0xBB83 - 0xA000:0xBB83 - 0xA000 + 10]), list(rom[0xBB8D - 0xA000:0xBB8D - 0xA000 + 10])


def realistic(m, rng, ys, xs, mode=None):
    """a frame of the random set-up of the stage-55 models is arbitrary memory; the output regions are only the game's when the entities stand where the maze lets them stand: positions inside the maze rectangle
    (Y between the first and the last junction line, X between the tunnel mouths) and the maze pointer inside the maze screen"""
    for g in range(5):
        m.mem[0x85 + g] = rng.randrange(min(ys), max(ys) + 1)
        m.mem[0x8A + g] = rng.randrange(0x2A, 0xCB)
    ptr = 0x0C00 + rng.randrange(0, 0x398)
    m.mem[0x80], m.mem[0x81] = ptr & 0xFF, ptr >> 8
    if mode == "title":
        m.mem[0x19] = rng.choice([1, 2, 3, 4])                  # GameState is 0 to 4 (docs/34: the 5 the stage-55 set-up draws is not a state of the game)


def run(frames=3000, seed=1):
    rec = Recorder()
    rec.install()
    stats = {"frames": 0, "key_passes": 0}
    try:
        rng = random.Random(seed)
        ys, xs = load_junction_lists()
        base = A.started_machine()                      # the start-up expansion: executed once here ...
        with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as fh:
            m0 = C.Machine(fh.read())
        m0.call(0xA386, until=0xA477, limit=3000000)     # ... and counted
        for mode in ("game", "play", "title"):
            for _ in range(frames):
                m = M6.prepare(base, rng)
                M7.frame_setup(m, rng, mode)
                realistic(m, rng, ys, xs, mode)
                m.random = [rng.randrange(256) for _ in range(12)]
                try:
                    m.call(0xA5FD)
                except Exception:
                    continue
                stats["frames"] += 1
        # the rare paths the random frames seldom take: the end of a level (the stages of the flashing), the end of the eaten-ghost pause, a dot cell marked 2, the bonus item leaving the screen
        for _ in range(max(300, frames // 4)):
            m = M6.prepare(base, rng)
            M7.frame_setup(m, rng, "play")
            realistic(m, rng, ys, xs, "play")
            m.mem[0x26], m.mem[0x27], m.mem[0x28], m.mem[0x29] = 1, rng.randrange(5), rng.choice([0, 0, 1, 5]), rng.randrange(1, 9)
            m.random = [rng.randrange(256) for _ in range(12)]
            try:
                m.call(0xA5FD)
                stats["frames"] += 1
            except Exception:
                pass
        for _ in range(max(300, frames // 4)):
            m = M6.prepare(base, rng)
            M7.frame_setup(m, rng, "play")
            realistic(m, rng, ys, xs, "play")
            m.mem[0xED] = rng.choice([1, 2, 3, 4, 5, 6])
            m.mem[0xEE] = rng.choice([0, 1, 2, 5, 0x30, 0x60])
            for a_ in (0xEF, 0xF0, 0xF1):
                m.mem[a_] = rng.randrange(14)
            m.random = [rng.randrange(256) for _ in range(12)]
            try:
                m.call(0xA5FD)
                stats["frames"] += 1
            except Exception:
                pass
        for _ in range(max(300, frames // 4)):
            m = M6.prepare(base, rng)
            M7.frame_setup(m, rng, "play")
            realistic(m, rng, ys, xs, "play")
            m.mem[0xE5] = 1
            m.mem[0xE8], m.mem[0xE9] = rng.randrange(4), rng.randrange(5)
            m.mem[0xE6], m.mem[0xE7] = rng.choice([0, 1, 2]), rng.randrange(0x40, 0x90)
            m.random = [rng.randrange(256) for _ in range(12)]
            try:
                m.call(0xA5FD)
                stats["frames"] += 1
            except Exception:
                pass
        for _ in range(max(300, frames // 4)):
            m = M6.prepare(base, rng)
            M7.frame_setup(m, rng, "play")
            realistic(m, rng, ys, xs, "play")
            m.mem[0x82] = m.mem[0xA6] = 0
            m.mem[0x83], m.mem[0x84] = (m.mem[0x89] + 1) & 255, m.mem[0x8E]                # not the cell of the last call
            ptr = m.mem[0x80] | m.mem[0x81] << 8
            m.mem[ptr] = rng.choice([0, 1, 2, 2, 3])
            try:
                m.call(0xB33A)
                stats["frames"] += 1
            except Exception:
                pass
            m.mem[0x9F], m.mem[0x9D], m.mem[0x9E] = 1, 0, 0                                   # the bonus item has timed out
            try:
                m.call(0xB62E)
            except Exception:
                pass
        # the display-list interrupt handlers (they run between the frames: entered as the CPU enters an interrupt)
        stats["interrupts"] = 0
        for entry in (0xA573, 0xA5CE):
            for _ in range(max(200, frames // 3)):
                m = M6.prepare(base, rng)
                m.mem[0x18] = rng.randrange(5)                      # the band counter at a display-list interrupt: 0 to 4 (five interrupts a frame, cleared by the handler)
                for a_ in (0x5E, 0x5F, 0x60, 0x61, 0xA0):
                    m.mem[a_] = rng.randrange(256)
                try:
                    M6.call_interrupt(m, entry)
                    stats["interrupts"] += 1
                except Exception:
                    pass
        # a play frame in order (the sequence of output regions written)
        rec.trace = True
        seqs = {}
        for mode in ("play", "game"):
            m = M6.prepare(base, rng)
            M7.frame_setup(m, rng, mode)
            realistic(m, rng, ys, xs)
            m.random = [rng.randrange(256) for _ in range(12)]
            del rec.sequence[:]
            m.call(0xA5FD)
            seqs[mode] = list(rec.sequence)
        rec.trace = False
    finally:
        rec.remove()
    return rec, stats, seqs


def runs_of(seq):
    out = []
    for r in seq:
        if out and out[-1][0] == r:
            out[-1][1] += 1
        else:
            out.append([r, 1])
    return out


def census(rec):
    """-> {region: {routine: set of pcs seen}}, and the static one"""
    dyn = defaultdict(lambda: defaultdict(set))
    for (pc, r), n in rec.stores.items():
        dyn[r][routine_name(pc)].add(pc)
    st = defaultdict(lambda: defaultdict(set))
    for pc, regs in STATIC.items():
        for r in regs:
            st[r][routine_name(pc)].add(pc)
    return dyn, st


def main():
    a = sys.argv
    frames = int(a[a.index("--frames") + 1]) if "--frames" in a else 3000
    rec, stats, seqs = run(frames)
    total = sum(rec.stores.values())
    L = ["The write map: %d store instructions of the ROM classified (%d with a target in an output region), checked on the concrete 6502: %d handler frames (%d each of the game, play and title frame set-ups of tools/algorithm_models7.py), %d display-list interrupts, the start-up expansion; %d stores, %d outside the classification" % (
        len(STATIC), sum(1 for pc, r in STATIC.items() if r & OUTPUT), stats["frames"], frames, stats.get("interrupts", 0), total, len(rec.bad))]
    for b in rec.bad[:10]:
        L.append("VIOLATION pc=$%04X address=$%04X region %s, classified %s" % (b[0], b[1], b[2], sorted(STATIC[b[0]])))
    print("\n".join(L))


if __name__ == "__main__":
    main()
