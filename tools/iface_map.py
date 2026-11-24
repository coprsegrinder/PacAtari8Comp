"""Stage 67 (external interface): WHAT THE GAME TAKES FROM THE OUTSIDE AND GIVES TO IT, closed and checked.

Static: every instruction of the ROM (2,925, tools/absint6502.py) whose operand lies outside the game's own memory is classified as an input read, an output write or a control transfer: the OS page 2, the OS page 3
(the CIO and SIO control blocks), the hardware ($D000-$D7FF), the OS zero-page variables the game shares with the OS, the OS ROM.  The reads come to 35 instructions on 14 declared inputs and one read-back of the game's own colour shadows; there is no indirect jump,
no BRK, no OS call but two (SETVBV, XITVBV), no access to page 3, to the PIA or to the serial data register.

Dynamic, on the concrete 6502 (tools/cpu6502.py), for the vertical-blank handler (the frame in every mode: game, play, title, level end, death, eaten pause), the two display-list interrupt handlers and a pass of the key loop:
  READS      every read of an external address (page 2, page 3, hardware, OS ROM) is made by an instruction of the static read list, from an address of that instruction's range, and the address is a declared input
             (or the colour shadows the game reads back);
  CLOSURE    the same random game state is run twice; in the second run EVERY external cell that is not a declared input (page 2 and page 3 except the inputs, the hardware registers, the OS ROM) holds other random
             values.  The game RAM, the ordered writes to the outside, the RANDOM values read and the OS calls are the same: the outside does not reach the game except through the declared inputs;
  SENSITIVITY each declared input is changed, alone, in the second run: it changes the result in some runs (the list is not too long: every input is live) and the table says how often.
Usage: python -I tools/iface_map.py [--trials 600] [--write analysis/evidence-iface-summary.txt]"""
import os
import random
import sys
import zlib
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import algorithm_models as A  # noqa: E402
import algorithm_models6 as M6  # noqa: E402
import algorithm_models7 as M7  # noqa: E402
import analyze_io as IO  # noqa: E402
import check_play as CPL  # noqa: E402
import check_sound as CSO  # noqa: E402
import cpu6502 as C  # noqa: E402
import output_map as O  # noqa: E402

INS = O.INS
RANDOM = 0xD20A

# the declared inputs: (name, first address, last address, device, who samples it, what it is)
INPUTS = [
    ("STICK0-1", 0x0278, 0x0279, "OS page 2", "MovePacMan `$B1A1` (`lda STICK0,x`)", "the joystick of the player on turn: 4 direction bits, 0 = pressed, `$0F` = none"),
    ("STRIG0", 0x0284, 0x0284, "OS page 2", "key loop, `$A4FA`", "the trigger of port 1, 0 = pressed: starts a game"),
    ("STRIG1", 0x0285, 0x0285, "OS page 2", "key loop, `$A4FF`", "the trigger of port 2, 0 = pressed: starts a game"),
    ("KEYDEL", 0x02F1, 0x02F1, "OS page 2", "key loop, `$A4CC`", "the OS key-debounce delay: the pause key is accepted only at 0"),
    ("CH", 0x02FC, 0x02FC, "OS page 2", "key loop, `$A4D1`", "the last key code of the OS keyboard handler (`$FF` none, `$21` the space bar)"),
    ("CONSOL", 0xD01F, 0xD01F, "GTIA", "key loop, `$A504 $A511 $A51C`", "the console keys START, SELECT, OPTION, 0 = pressed"),
    ("M2PF", 0xD002, 0xD002, "GTIA (read)", "FrameDispatch `$A938`", "collision of missile 2 with playfield colour 1: the bonus item is touched"),
    ("M1PL", 0xD009, 0xD009, "GTIA (read)", "FrameDispatch `$A857`", "collision of missile 1 with the players: which ghost Pac-Man touches"),
    ("M2PL", 0xD00A, 0xD00A, "GTIA (read)", "FrameDispatch `$A85C`", "collision of missile 2 with the players (the second half of the contact test)"),
    ("RANDOM", 0xD20A, 0xD20A, "POKEY", "`$B859`, `$B9E1`, `$B9F4`", "the polynomial counter: a different byte at every read"),
    ("RTCLOK2", 0x0014, 0x0014, "OS zero page", "15 instructions (every timer of the game)", "the low byte of the OS jiffy clock, one more at every frame"),
    ("DRKMSK", 0x004E, 0x004E, "OS zero page", "key loop `$A4C1`, first display-list handler `$A58C`", "the attract-mode darkening mask (ANDed into the colours put on the screen)"),
    ("COLRSH", 0x004F, 0x004F, "OS zero page", "key loop `$A4BF`, first display-list handler `$A58A`", "the attract-mode colour shift (EORed into the colours)"),
    ("POKMSK", 0x0010, 0x0010, "OS zero page", "Start `$A44D` (once)", "the OS copy of the POKEY interrupt enable: the game ORs in the keyboard bit and writes it back"),
]
# a read-back of the game's own output: the player colour shadows of the pop-up (GhostEatenPause `$B09D`)
READBACK = ("PCOLR0-3", 0x02C0, 0x02C3, "OS page 2", "GhostEatenPause `$B09D` (`lda PCOLR0,x`)", "the game reads back the player colour shadows it wrote (state kept in the OS page)")
DECLARED = [(n, lo, hi) for n, lo, hi, *_ in INPUTS] + [(READBACK[0], READBACK[1], READBACK[2])]
DECLARED_ADDRS = {a for n, lo, hi in DECLARED for a in range(lo, hi + 1)}
HW_COLLISION = range(0xD000, 0xD010)           # read as the GTIA collision registers: a separate input array (the same addresses are the HPOS write registers)
KEEP_EXTERNAL_RAM = {RANDOM}
POKEY_SERIAL = (0xD20D, 0xD20C)                # SEROUT / SERIN, SKRES: the serial bus


def external_class(a):
    if 0x0200 <= a <= 0x02FF:
        return "OsPage2"
    if 0x0300 <= a <= 0x03FF:
        return "OsPage3"
    if 0xD000 <= a <= 0xD7FF:
        return {0xD0: "Gtia", 0xD2: "Pokey", 0xD3: "Pia", 0xD4: "Antic"}.get(a >> 8, "HwOther")
    if a >= 0xC000:
        return "OsRom"
    return None


def static_ranges(op, mode):
    return (op, op + 255) if mode in ("abx", "aby") else (op, op) if mode in ("abs", "zp") else None


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def static_report():
    """-> dict of the static facts of the ROM's interface"""
    sites = IO.sites()
    reads = [s for s in sites if "r" in s["dir"]]
    writes = [s for s in sites if "w" in s["dir"]]
    ctl_out = []
    ind = brk = 0
    rti = []
    cpu_flags = []
    refs = {k: [0, 0] for k in ("page3", "pia", "serial", "osrom")}          # [absolute operand, indexed window] per area the game must not use
    areas = {"page3": lambda lo, hi: lo <= 0x03FF and hi >= 0x0300, "pia": lambda lo, hi: lo <= 0xD3FF and hi >= 0xD300, "serial": lambda lo, hi: any(lo <= x <= hi for x in POKEY_SERIAL),
             "osrom": lambda lo, hi: hi >= 0xC000 and (lo < 0xD000 or lo >= 0xD800 or hi >= 0xD800) and not (0xD000 <= lo and hi < 0xD800)}
    for pc, (ln, m, mode, op) in INS.items():
        if m == "brk":
            brk += 1
        if m == "rti":
            rti.append(pc)
        if m in ("sei", "cli", "php", "plp", "sed", "cld"):
            cpu_flags.append((pc, m))
        if mode == "ind":
            ind += 1
        if isinstance(op, int) and m in ("jsr", "jmp") and not (0xA000 <= op < 0xC000):
            ctl_out.append((pc, m, op))
        if isinstance(op, int) and mode in ("abs", "abx", "aby") and m not in ("jsr", "jmp"):
            lo, hi = static_ranges(op, mode)
            for k, f in areas.items():
                if f(lo, hi):
                    refs[k][0 if mode == "abs" else 1] += 1
    return {"instructions": len(INS), "sites": sites, "reads": reads, "writes": writes, "control_out": sorted(ctl_out), "indirect_jumps": ind, "brk": brk, "rti": sorted(rti), "cpu_flags": sorted(cpu_flags),
            "refs": refs}


def read_site_table(st):
    """-> {pc: (op, mode, lo, hi, routine, mnemonic)} of the static read sites"""
    out = {}
    for s in st["reads"]:
        lo, hi = static_ranges(s["op"], s["mode"]) if s["mode"] in ("abs", "abx", "aby", "zp") else (s["op"], s["op"] + 255 if s["mode"] == "zpx" else s["op"])
        out[s["pc"]] = (s["op"], s["mode"], lo, hi, s["routine"], s["m"])
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
class Probe:
    """patches the concrete machine: reads of external addresses recorded (pc, address), the collision registers read from a separate input array, every write to the outside logged in order"""

    def __init__(self):
        self.reads = Counter()
        self.cls = Counter()                       # accesses by area, reads and writes
        self.orig = (C.Machine.rd, C.Machine.wr, C.Machine.step)

    def install(self):
        orig_rd, orig_wr, orig_step = self.orig
        probe = self

        def rd(m, a):
            a &= 0xFFFF
            if a == RANDOM:
                probe.reads[(m.cur, a)] += 1
                probe.cls[("r", "Pokey")] += 1
                return orig_rd(m, a)
            if 0xD000 <= a <= 0xD00F:
                v = m.hw[a & 15]
            else:
                v = orig_rd(m, a)
            if external_class(a) or a in (0x10, 0x14, 0x4D, 0x4E, 0x4F):
                probe.reads[(m.cur, a)] += 1
                probe.cls[("r", external_class(a) or "OsZeroPage")] += 1
                if a in POKEY_SERIAL:
                    probe.cls[("r", "SerialData")] += 1
            return v

        def wr(m, a, v):
            a &= 0xFFFF
            if external_class(a) or a in (0x10, 0x14, 0x4D, 0x4E, 0x4F):
                m.xlog.append((a, v & 0xFF))
                probe.cls[("w", external_class(a) or "OsZeroPage")] += 1
                if a in POKEY_SERIAL:
                    probe.cls[("w", "SerialData")] += 1
            orig_wr(m, a, v)

        def step(m):
            m.cur = m.pc
            return orig_step(m)

        C.Machine.rd, C.Machine.wr, C.Machine.step = rd, wr, step

    def remove(self):
        C.Machine.rd, C.Machine.wr, C.Machine.step = self.orig


KINDS = ("vbi-game", "vbi-play", "vbi-title", "vbi-levelend", "vbi-death", "vbi-eaten", "dli-game", "dli-title", "keyloop", "frame-play")


def declared_inputs_random(m, rng):
    m.mem[0x0278] = rng.choice([0x0F, 0x0F, 0x0E, 0x0D, 0x0B, 0x07, 0x0A, 0x06, rng.randrange(256)])
    m.mem[0x0279] = rng.choice([0x0F, 0x0E, 0x0B, rng.randrange(256)])
    m.mem[0x0284] = rng.choice([1, 1, 0, rng.randrange(256)])
    m.mem[0x0285] = rng.choice([1, 1, 0, rng.randrange(256)])
    m.mem[0x02F1] = rng.choice([0, 0, 0, 1, 3, rng.randrange(256)])
    m.mem[0x02FC] = rng.choice([0xFF, 0xFF, 0x21, 0x21, rng.randrange(256)])
    m.mem[0xD01F] = rng.choice([7, 7, 7, 6, 5, 3, 0, rng.randrange(256)])
    m.mem[0x4E] = rng.choice([0xFF, 0xFF, 0xFE, 0xF0, rng.randrange(256)])
    m.mem[0x4F] = rng.choice([0, 0, 0, 0x40, rng.randrange(256)])
    m.mem[0x10] = rng.randrange(256)
    for k in range(4):
        m.mem[0x02C0 + k] = rng.choice([0xDC, 0x44, rng.randrange(256)])
    m.hw = [rng.choice([0, 0xFF, 0x0F, rng.randrange(256)]) for _ in range(16)]
    m.hw[2] = rng.choice([0, 0, 2, 3, rng.randrange(256)])
    m.hw[9] = rng.choice([0, 0x0F, 1, 2, 4, rng.randrange(256)])
    m.hw[10] = rng.choice([0, 0x0F, 1, 2, 4, rng.randrange(256)])


def make_frame_play(base, rng):
    """a random state of the running game on the lattice (ghosts in every state, the eaten pause, the death states: tools/check_play.py): the frame body $A82C"""
    rnds = [rng.randrange(256) for _ in range(12)]
    m = A.fresh(base, list(rnds))
    CSO.sound_setup(m, rng)
    CPL.play_pre(m, rng)
    m.hw = [m.mem[0xD000 + k] for k in range(16)]
    for k in range(4):
        m.mem[0x02C0 + k] = rng.choice([0xDC, 0x44, rng.randrange(256)])        # $DC marks the ghost whose pop-up is shown: the game reads it back (GhostEatenPause $B09D)
    for a_, v in ((0x0284, 1), (0x0285, 1), (0x02F1, 0), (0x02FC, 0xFF), (0xD01F, 7)):
        m.mem[a_] = v
    m.xlog = []
    m.cur = 0
    return m


def make_trial(kind, base, rng, ys, xs):
    if kind == "frame-play":
        return make_frame_play(base, rng)
    m = M6.prepare(base, rng)
    mode = {"vbi-game": "game", "vbi-title": "title"}.get(kind, "play")
    M7.frame_setup(m, rng, mode)
    O.realistic(m, rng, ys, xs, mode)
    if kind == "vbi-levelend":
        m.mem[0x26], m.mem[0x27], m.mem[0x28], m.mem[0x29] = 1, rng.randrange(5), rng.choice([0, 0, 1, 5]), rng.randrange(1, 9)
    elif kind == "vbi-death":
        m.mem[0xED] = rng.choice([1, 2, 3, 4, 5, 6])
        m.mem[0xEE] = rng.choice([0, 1, 2, 5, 0x30, 0x60])
        for a_ in (0xEF, 0xF0, 0xF1):
            m.mem[a_] = rng.randrange(14)
    elif kind == "vbi-eaten":
        m.mem[0xE5] = 1
        m.mem[0xE8], m.mem[0xE9] = rng.randrange(4), rng.randrange(5)
        m.mem[0xE6], m.mem[0xE7] = rng.choice([0, 1, 2]), rng.randrange(0x40, 0x90)
    elif kind.startswith("dli"):
        m.mem[0x18] = rng.randrange(5)
        for a_ in (0x5E, 0x5F, 0x60, 0x61, 0xA0):
            m.mem[a_] = rng.randrange(256)
    elif kind == "keyloop":
        m.mem[0x19] = rng.choice([0, 0, 1, 2, 3, 4])
        m.mem[0x46] = rng.choice([0, 1, 2, 3, 4, rng.randrange(256)])
    declared_inputs_random(m, rng)
    m.random = [rng.randrange(256) for _ in range(12)]
    m.xlog = []
    m.cur = 0
    return m


def go(m, kind):
    """run the entry; -> (steps or an exception name)"""
    try:
        if kind.startswith("vbi"):
            return m.call(0xA5FD)
        if kind == "frame-play":
            return m.call(0xA82C)
        if kind == "dli-game":
            return M6.call_interrupt(m, 0xA573)
        if kind == "dli-title":
            return M6.call_interrupt(m, 0xA5CE)
        m.pc = 0xA4BA                                      # one pass of the key loop: until it is back at its head
        n = 0
        m.step()
        while m.pc != 0xA4BA:
            m.step()
            n += 1
            if n > 40000:
                return "waiting:%04X" % m.pc                  # the loop waits for an input to change ($A511 CONSOL released, $A493 the clock): the state at 40,000 steps is compared
        return n
    except Exception as e:                                 # a random state the game does not reach (a maze pointer outside the maze ...): both runs must end the same way
        return "exc:" + type(e).__name__


def poison(m, rng, keep):
    """every external cell that is not a declared input gets another random value"""
    for a in list(range(0x0200, 0x0400)) + list(range(0xC000, 0x10000)) + list(range(0xD000, 0xD800)):
        if a in keep or a == RANDOM or 0xA000 <= a < 0xC000:
            continue
        m.mem[a] = rng.randrange(256)


def snapshot(m, res):
    ram = bytearray(m.mem[0:0x4000])
    for a in range(0x0200, 0x0400):
        ram[a] = 0                                         # page 2 and 3: the cells are inputs (changed on purpose) or undeclared (poisoned); what the game writes there is in the ordered write log
    for a in (0x10, 0x14, 0x4D, 0x4E, 0x4F):
        ram[a] = 0                                         # the OS zero-page variables: the same
    return (res, bytes(ram), tuple(m.xlog), tuple(m.random_reads), tuple(m.os_calls))


def run(trials=600, seed=67):
    base = A.started_machine()
    ys, xs = O.load_junction_lists()
    st = static_report()
    sites = read_site_table(st)
    probe = Probe()
    probe.install()
    out = {"kinds": {}, "reads": Counter(), "bad_reads": [], "closure_bad": [], "sens": defaultdict(Counter), "sens_trials": Counter(), "unfinished": 0, "exceptions": 0}
    try:
        for kind in KINDS:
            rng = random.Random(seed * 100 + KINDS.index(kind))
            n = ok = 0
            for _ in range(trials):
                seed_t = rng.randrange(1 << 30)
                # run A
                m_a = make_trial(kind, base, random.Random(seed_t), ys, xs)
                before = Counter(probe.reads)
                res_a = go(m_a, kind)
                for k, v in probe.reads.items():
                    out["reads"][k] += v - before.get(k, 0)
                # run B: the same state, every undeclared external cell poisoned
                m_b = make_trial(kind, base, random.Random(seed_t), ys, xs)
                prng = random.Random(seed_t ^ 0x5A5A)
                poison(m_b, prng, DECLARED_ADDRS)
                res_b = go(m_b, kind)
                n += 1
                if isinstance(res_a, str) and res_a.startswith("waiting"):
                    out["unfinished"] += 1
                if isinstance(res_a, str) and res_a.startswith("exc"):
                    out["exceptions"] += 1
                else:
                    ok += 1
                sa, sb = snapshot(m_a, res_a), snapshot(m_b, res_b)
                if sa != sb:
                    out["closure_bad"].append((kind, seed_t, [i for i in range(len(sa)) if sa[i] != sb[i]]))
                # sensitivity: one declared input changed in run C
                for name, lo, hi in DECLARED:
                    m_c = make_trial(kind, base, random.Random(seed_t), ys, xs)
                    crng = random.Random(seed_t ^ (zlib.crc32(name.encode()) & 0xFFFF))
                    if name == "RANDOM":
                        m_c.random = [crng.randrange(256) for _ in range(12)]
                    elif lo >= 0xD000 and hi < 0xD010:
                        m_c.hw[lo & 15] = (m_c.hw[lo & 15] ^ crng.randrange(1, 256)) & 0xFF
                    else:
                        for a in range(lo, hi + 1):
                            m_c.mem[a] = (m_c.mem[a] ^ crng.randrange(1, 256)) & 0xFF
                    res_c = go(m_c, kind)
                    out["sens_trials"][(kind, name)] += 1
                    if snapshot(m_c, res_c) != sa:
                        out["sens"][name][kind] += 1
            out["kinds"][kind] = (n, ok)
    finally:
        probe.remove()
    # every dynamic read against the static list
    for (pc, a), n in sorted(out["reads"].items()):
        if n == 0:
            continue
        if pc not in sites and a not in (0x10, 0x14, 0x4D, 0x4E, 0x4F):
            out["bad_reads"].append((pc, a, "read by an instruction that is not a static read site"))
            continue
        if pc in sites:
            _, _, lo, hi, _, _ = sites[pc]
            if not lo <= a <= hi:
                out["bad_reads"].append((pc, a, "outside the instruction's static range $%04X-$%04X" % (lo, hi)))
        if a not in DECLARED_ADDRS and a not in HW_COLLISION and a != RANDOM and a not in (0x10, 0x14, 0x4D, 0x4E, 0x4F):
            out["bad_reads"].append((pc, a, "not a declared input"))
    out["static"] = st
    out["cls"] = dict(probe.cls)
    return out


def summary_lines(res):
    st = res["static"]
    L = ["External interface of the ROM (tools/iface_map.py, stage 67): static classification of the %d instructions, and the concrete 6502 run on the frame, the display-list handlers and a pass of the key loop" % st["instructions"], ""]
    L.append("static: %d instructions touch an input or an output register (%d reads, %d writes); control transfers outside the cartridge: %d (%s); indirect jumps: %d; BRK: %d; RTI: %d (%s); absolute references to page 3 (the CIO and SIO control blocks): %d, to the PIA: %d, to the serial data registers: %d, to the OS ROM data: %d; indexed instructions whose 256-byte window reaches these areas: %d, %d, %d, %d (small indexes into page 2 and the chip registers; the run below touched none of the areas)"
             % (len(st["sites"]), len(st["reads"]), len(st["writes"]), len(st["control_out"]), ", ".join("%s $%04X -> $%04X" % (m, pc, op) for pc, m, op in st["control_out"]), st["indirect_jumps"], st["brk"], len(st["rti"]),
                ", ".join("$%04X" % p for p in st["rti"]), st["refs"]["page3"][0], st["refs"]["pia"][0], st["refs"]["serial"][0], st["refs"]["osrom"][0], st["refs"]["page3"][1], st["refs"]["pia"][1], st["refs"]["serial"][1], st["refs"]["osrom"][1]))
    cl = res["cls"]
    L.append("accesses outside the game's memory, by area (reads / writes): %s; page 3, the PIA, the serial data registers, the OS ROM data and the other hardware: %d"
             % (", ".join("%s %d / %d" % (k, cl.get(("r", k), 0), cl.get(("w", k), 0)) for k in ("OsZeroPage", "OsPage2", "Gtia", "Pokey", "Antic")),
                sum(v for (rw, k), v in cl.items() if k in ("OsPage3", "Pia", "SerialData", "OsRom", "HwOther"))))
    ndyn = sum(1 for k, v in res["reads"].items() if v)
    tot = sum(res["reads"].values())
    L.append("reads: %d distinct (instruction, address) pairs read %d times from outside the game's memory: %d outside the static list or the declared inputs" % (ndyn, tot, len(res["bad_reads"])))
    for b in res["bad_reads"][:5]:
        L.append("  $%04X reads $%04X: %s" % b)
    nt = sum(n for n, ok in res["kinds"].values())
    L.append("closure: %d random game states (%s), each run twice with every undeclared external cell (page 2 and 3, the hardware, the OS ROM: up to 11,000 cells) holding other random values the second time: %d differences in the RAM, the ordered writes to the outside, the RANDOM reads or the OS calls"
             % (nt, ", ".join("%s %d" % (k, v[0]) for k, v in res["kinds"].items()), len(res["closure_bad"])))
    for b in res["closure_bad"][:5]:
        L.append("  %s" % (b,))
    L.append("(%d runs of the key loop were still in a wait for an input (CONSOL released, the clock) after 40,000 steps and were compared there; %d ended in an exception, the same in both runs)" % (res["unfinished"], res["exceptions"]))
    L.append("")
    L.append("sensitivity: runs (of %d per entry kind) in which changing this one input alone changed the result" % (nt // len(KINDS)))
    hdr = "input".ljust(10) + "".join(k.replace("vbi-", "v:").replace("dli-", "d:").rjust(12) for k in KINDS)
    L.append(hdr)
    for name, lo, hi in DECLARED:
        L.append(name.ljust(10) + "".join(("%d" % res["sens"][name].get(k, 0)).rjust(12) for k in KINDS))
    dead = [name for name, lo, hi in DECLARED if not res["sens"][name] and name not in ("POKMSK",)]
    L.append("inputs no run was sensitive to: %s; POKMSK is read only by Start (`$A44D`), which these entries do not run (the power-on state is `37`)" % (", ".join(dead) if dead else "none"))
    return L


def main():
    n = 600
    if "--trials" in sys.argv:
        n = int(sys.argv[sys.argv.index("--trials") + 1])
    res = run(n)
    txt = "\n".join(summary_lines(res)) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if res["bad_reads"] or res["closure_bad"] else 0


if __name__ == "__main__":
    sys.exit(main())
