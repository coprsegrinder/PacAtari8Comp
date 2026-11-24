"""Stage 87 (behavioural equivalence): the C port and the ROM compared not only by the state they end in (stage 86, tools/check_c_vs_rom.py) but by HOW they behave on the same inputs:
  1. frame classes     the class of every frame (docs/38 section 4: title, countdown, level end, eaten pause, play, ...) chosen by the C from its state equals the one the ROM's dispatcher chooses, in sequence;
  2. state transitions every change of the 20 state variables of docs/34 (screen, start, turn, level end, pause, death, eaten pause, frightened phase, bonus, the four ghosts) from one frame to the next is the same in
                       the C and in the ROM, and is a chain of the 68 rules of docs/34 (tools/analyze_states.py RULES, pc-free: the C has no program counter) or a clear of a bulk range; which rules were seen;
  3. execution paths   how many times each routine of the vertical-blank handler runs.  The ROM side counts the executions of each routine's entry address inside the handler (`$A5FD`, so the idle passes of the
                       main program that the harness runs do not count); the C side is the call count of the C function that carries the routine's address in its header comment (gcc --coverage, gcov);
                       both over the same replays.  Only routines that the static call tree (tools/comm_map.py) reaches from the handler and from no other context are compared.
  4. outputs           the original's outputs are the memory-mapped display, the player-missile pages, the shadows and the ordered chip writes (docs/42: 2,303,680 stores, none outside the classified regions); they are
                       part of the whole-state comparison of stage 86, repeated here frame by frame.
Usage: python -I tools/check_behaviour.py REPLAY [REPLAY ...] [--exe PACMAN_A8] [--counts-out FILE]    (writes the ROM-side counts, adds to the sums with --append)
       python -I tools/check_behaviour.py --paths COUNTS_JSON GCOV_DIR     (compares the ROM's routine counts with the C's function counts)"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_collide as AC  # noqa: E402
import analyze_states as S  # noqa: E402
import check_app as CA  # noqa: E402
import check_app_board as CAB  # noqa: E402
import check_c_vs_rom as X  # noqa: E402
import check_ghost as CG  # noqa: E402
import core_app as APP  # noqa: E402
import core_world as W  # noqa: E402
import cpu6502 as C  # noqa: E402
import make_replay as MR  # noqa: E402
import vecfmt as V  # noqa: E402

ROOT = os.path.dirname(HERE)
VBI = 0xA5FD


# ---------------------------------------------------------------------------------------------- the rules
def edges():
    """var -> {old: {new}}: one step of any rule (pc-free) or of a bulk clear, over the domain of the variable"""
    out = {}
    for a, name, size, desc in S.STATES:
        dom = S.DOMAIN[name]
        e = defaultdict(set)
        for rule in S.RULES:
            if rule[0] != name:
                continue
            _, froms, to, _, _ = rule
            for old in (froms if froms is not None else dom):
                if callable(to):
                    new = set(to(old))
                elif to == "+1":
                    new = {old + 1}
                else:
                    new = {to}
                e[old] |= new
        for _, lo, hi, _ in S.BULK_CLEARS:
            if lo <= a <= hi:
                for old in dom:
                    e[old].add(0)
        out[name] = e
    return out


def reachable(e, old, new, limit=6):
    if old == new:
        return True
    seen, front = {old}, {old}
    for _ in range(limit):
        front = {n for o in front for n in e.get(o, ()) if n not in seen}
        if new in front:
            return True
        seen |= front
        if not front:
            return False
    return False


def rule_hits():
    return Counter()


# ---------------------------------------------------------------------------------------------- the ROM side
def entries_of_interest():
    """the routine entry addresses (from the headers of the C port) that only the vertical-blank handler reaches"""
    import comm_map as CM
    ctx = CM.context_pcs()
    only = ctx["vbi"] - ctx["key"] - ctx["newgame"] - ctx["dli1"] - ctx["dli2"]
    named = c_functions()
    return {addr: name for name, addr in named.items() if addr in only}, named


def bodies(entries):
    """entry address -> the instruction addresses of the routine's own body (callees not included)"""
    import comm_map as CM
    return {e: set(CM.F[e].body) for e in entries if e in CM.F}


def asm_labels():
    """routine label -> address of its first instruction, from src/asm/pacman.s"""
    with open(os.path.join(ROOT, "src", "asm", "pacman.s"), encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out = {}
    for i, l in enumerate(lines):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$", l)
        if m:
            for j in range(i + 1, min(i + 6, len(lines))):
                mm = re.search(r";\s*([0-9A-F]{4})\s+[0-9A-F]{2}", lines[j])
                if mm:
                    out[m.group(1)] = int(mm.group(1), 16)
                    break
    return out


def c_routines():
    """[(C function, routine name, address)] for every declaration whose comment reads `Name $ADDR`"""
    out = []
    pat = re.compile(r"([a-z_0-9]+)\s*\([^;{}]*\)\s*;\s*/\*\s*([A-Za-z0-9_]+)\s+\$([0-9A-F]{4})")
    for dp, _, fs in os.walk(os.path.join(ROOT, "src", "c")):
        for f in sorted(fs):
            if f.endswith(".h"):
                with open(os.path.join(dp, f), encoding="utf-8") as fh:
                    for line in fh:
                        m = pat.search(line)
                        if m:
                            out.append((m.group(1), m.group(2), int(m.group(3), 16)))
    return out


def c_functions():
    """C function name -> the ROM routine address given in the comment after its declaration in src/c headers"""
    out = {}
    pat = re.compile(r"\b([a-z_0-9]+)\s*\([^;{}]*\)\s*;\s*/\*[^*]*?\$([0-9A-F]{4})")
    for dp, _, fs in os.walk(os.path.join(ROOT, "src", "c")):
        for f in fs:
            if f.endswith(".h"):
                with open(os.path.join(dp, f), encoding="utf-8") as fh:
                    for line in fh:
                        m = pat.search(line)
                        if m:
                            out.setdefault(m.group(1), int(m.group(2), 16))
    return out


class Counting:
    """counts the entries of each routine inside the vertical-blank handler: the first instruction executed after control came from OUTSIDE the routine's own body (a call, a jump, a branch or the routine before
    falling in; a loop back to its own first instruction is not an entry)"""

    def __init__(self, entries):
        self.entries = set(entries)
        self.body = bodies(entries)
        self.counts = Counter()
        self.by_source = Counter()                       # (callee entry, entry of the routine the previous instruction belongs to) -> entries
        import comm_map as CM
        self.owner = {}
        for e in sorted(CM.F):
            for a in CM.F[e].body:
                self.owner.setdefault(a, e)
        self._call = C.Machine.call
        self._step = C.Machine.step

    def __enter__(self):
        me = self

        def call(m, addr, *a, **k):
            if addr != VBI:
                return me._call(m, addr, *a, **k)
            prev = [None]

            def step(mm):
                pc = mm.pc
                if pc in me.entries and (prev[0] is None or prev[0] not in me.body.get(pc, ())):
                    me.counts[pc] += 1
                    me.by_source[(pc, me.owner.get(prev[0], 0))] += 1
                prev[0] = pc
                return me._step(mm)
            C.Machine.step = step
            try:
                return me._call(m, addr, *a, **k)
            finally:
                C.Machine.step = me._step
        C.Machine.call = call
        return self

    def __exit__(self, *e):
        C.Machine.call = self._call
        C.Machine.step = self._step


def var_values(mem):
    out = {}
    for a, name, size, desc in S.STATES:
        out[name] = tuple(mem[a + k] for k in range(size))
    return out


def run_one(path, exe, ed, counting, rules_seen, E):
    with open(path, "rb") as fh:
        rp = MR.read_replay(fh.read())
    fr = rp["frames"]
    states = os.path.join(ROOT, "build", "c87", os.path.basename(path) + ".states")
    os.makedirs(os.path.dirname(states), exist_ok=True)
    r = subprocess.run([exe, "run", os.path.relpath(path, ROOT), "--states", os.path.relpath(states, ROOT)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("the C shell failed: " + r.stdout)
    cs = X.read_states(states, len(fr))
    p = X.ReplayInputs(AC.rom_charset())
    p.set(fr[0])
    rom = CA.RomApp(rp["start_clock"])
    res = {"frames": 0, "class diffs": [], "transition diffs": [], "no rule": [], "state diffs": [], "classes": Counter(), "transitions": 0, "changes": Counter()}
    c_prev = None
    rom_prev = var_values(rom.m.mem)
    try:
        for i, f in enumerate(fr):
            p.set(f)
            wrom = W.World().load(rom.m.mem)
            coll = p.collisions(wrom)
            cls_rom = APP.frame_class(wrom)
            with counting:
                rom.frame(p, coll)
            wa = W.World().load(rom.m.mem)
            wa.pokey = list(CAB.LOG)
            p.frame_done(wa)
            st, log, rr = cs[i]
            wc = V.unpack_state(st)
            wc.pokey = log
            d = CAB.diffs(rom.m, wc, CG.SCRATCH)
            if len(rom.m.random_reads) != rr:
                d.append("random")
            if d:
                res["state diffs"].append((i, d[:3]))
            if c_prev is not None:                              # the class the C chooses from its own state before the frame
                cls_c = APP.frame_class(c_prev)
                if cls_c != cls_rom:
                    res["class diffs"].append((i, cls_rom, cls_c))
            res["classes"][cls_rom] += 1
            rom_now = var_values(rom.m.mem)
            c_mem = bytearray(65536)
            wc.store(c_mem)
            c_now = var_values(c_mem)
            for name in rom_now:
                if rom_now[name] != c_now[name]:
                    res["transition diffs"].append((i, name, rom_now[name], c_now[name]))
                a_old = rom_prev[name]
                for k, (o, n) in enumerate(zip(a_old, c_now[name])):
                    if o != n:
                        res["transitions"] += 1
                        res["changes"][name] += 1
                        if not reachable(E[name], o, n):
                            res["no rule"].append((i, name, k, o, n))
                        for ri, rule in enumerate(S.RULES):
                            if rule[0] == name and (rule[1] is None or o in rule[1]) and (rule[2] == n or (callable(rule[2]) and n in rule[2](o)) or (rule[2] == "+1" and n == o + 1)):
                                rules_seen[ri] += 1
            rom_prev = rom_now
            c_prev = wc
            res["frames"] += 1
    finally:
        C.Machine.wr = CAB._orig
        C.Machine.rd = __import__("check_play")._orig_rd
    return res


def gcov_counts(gcov_dir):
    """function name -> total execution count over the objects of a gcc --coverage build"""
    out = Counter()
    gcov_dir = os.path.abspath(gcov_dir)
    for dp, _, fs in os.walk(gcov_dir):
        for f in fs:
            if f.endswith(".gcda"):
                obj = os.path.join(dp, f[:-5] + ".obj")
                if not os.path.exists(obj):
                    obj = os.path.join(dp, f[:-5] + ".o")
                r = subprocess.run(["gcov", "--json-format", "--stdout", obj], cwd=gcov_dir, capture_output=True, text=True)
                for line in r.stdout.splitlines():
                    line = line.strip()
                    if not line.startswith("{"):
                        continue
                    for fl in json.loads(line)["files"]:
                        for fn in fl["functions"]:
                            out[fn["name"]] += fn["execution_count"]
    return out


PATHS_SRC = {}


def c_call_sites(gcov_dir, callees):
    """(callee C function, calling C function) -> how many times the call line ran, from the gcov line counts of a coverage build"""
    out = Counter()
    seen = {}
    gcov_dir = os.path.abspath(gcov_dir)
    for dp, _, fs in os.walk(gcov_dir):
        for f in fs:
            if not f.endswith(".gcda"):
                continue
            obj = os.path.join(dp, f[:-5] + ".obj")
            r = subprocess.run(["gcov", "--json-format", "--stdout", obj], cwd=gcov_dir, capture_output=True, text=True)
            for line in r.stdout.splitlines():
                if not line.startswith("{"):
                    continue
                for fl in json.loads(line)["files"]:
                    path = os.path.normpath(fl["file"])
                    if os.sep + "src" + os.sep + "c" + os.sep not in path:
                        continue
                    with open(path, encoding="utf-8") as fh:
                        src = fh.read().splitlines()
                    funcs = sorted((x["start_line"], x["name"]) for x in fl["functions"])
                    for ln in fl["lines"]:
                        t = src[ln["line_number"] - 1]
                        for cal in callees:
                            if re.search(r"\b" + cal + r"\(", t) and not re.match(r"^[A-Za-z_][\w \*]*\b" + cal + r"\(", t):
                                owner = [n for st, n in funcs if st <= ln["line_number"]]
                                seen[(path, ln["line_number"], cal)] = (owner[-1] if owner else "?", ln["count"])      # a line is one call site, however often gcov lists it
    for (path, line, cal), (owner, count) in seen.items():
        out[(cal, owner)] += count
    return out


def paths(counts_json, gcov_dir):
    with open(counts_json, encoding="utf-8") as fh:
        data = json.load(fh)
    rom = {int(k): v for k, v in data["counts"].items()}
    PATHS_SRC.clear()
    PATHS_SRC.update({tuple(int(x) for x in k.split(",")): v for k, v in data["by_source"].items()})
    ed, named = entries_of_interest()
    c = gcov_counts(gcov_dir)
    same, diff = 0, []
    for addr, name in sorted(ed.items()):
        r, k = rom.get(addr, 0), c.get(name, 0)
        if r == k:
            same += 1
        else:
            diff.append((name, addr, r, k))
    return ed, rom, c, same, diff


def main():
    a = sys.argv[1:]
    if a and a[0] == "--paths":
        ed, rom, c, same, diff = paths(a[1], a[2])
        print("routines compared:", len(ed), "equal call counts:", same, "different:", len(diff))
        for name, addr, r, k in diff:
            print("  $%04X %-28s ROM %d  C %d" % (addr, name, r, k))
        named = c_functions()
        by_addr = {}
        for n, ad in named.items():
            by_addr.setdefault(ad, n)
        sites = c_call_sites(a[2], [n for n, _, _, _ in diff] + ["draw_all_in_place", "ref_junction_exits", "title_menu", "copyright_wait"])
        print("who calls them (ROM: the routine the previous instruction belongs to, named by the C function that carries its address; C: the calling function):")
        for name, addr, r, k in diff:
            rs = sorted(((by_addr.get(o, "$%04X" % o), v) for (e, o), v in PATHS_SRC.items() if e == addr), key=lambda x: -x[1])
            cs = sorted(((cl, v) for (cn, cl), v in sites.items() if cn == name), key=lambda x: -x[1])
            print("  %s  ROM %s" % (name, ", ".join("%s %d" % x for x in rs[:8])))
            print("  %s  C   %s" % (" " * len(name), ", ".join("%s %d" % x for x in cs[:8])))
        name_addr = {n: ad for n, ad in named.items()}

        def rom_from(callee, owner):
            return PATHS_SRC.get((name_addr[callee], name_addr[owner]), 0)

        def c_from(callee, owners):
            return sum(v for (cn, cl), v in sites.items() if cn == callee and cl in owners)
        GHOST = ["ghost_start_route", "ghost_chase", "ghost_patrol_travel", "ghost_go_to_corner", "ghost_patrol"]
        checks = [
            ("junction_lookup called by GhostBehaviour = by the five C ghost functions that split it", rom_from("junction_lookup", "ghost_behaviour"), c_from("junction_lookup", GHOST)),
            ("junction_lookup called by EyesAndHousePerFrame", rom_from("junction_lookup", "eyes_and_house_per_frame"), c_from("junction_lookup", ["eyes_and_house_per_frame"])),
            ("junction_lookup called by MovePacMan = ref_junction_exits called by move_pacman (the C has the Pac-Man version as a pure function)", rom_from("junction_lookup", "move_pacman"), c_from("ref_junction_exits", ["move_pacman"])),
            ("step_entity called by GhostBehaviour = by the C ghost functions that split it", rom_from("step_entity", "ghost_behaviour"), c_from("step_entity", GHOST + ["read_patrol_route"])),
            ("step_entity called by DeathSequence", rom_from("step_entity", "death_sequence"), c_from("step_entity", ["death_sequence"])),
            ("step_entity called by HouseBobStep", rom_from("step_entity", "house_bob_step"), c_from("step_entity", ["house_bob_step"])),
            ("step_entity called by HouseLeaveStep (set_dir_step in the C)", rom_from("step_entity", "house_leave_step"), c_from("step_entity", ["set_dir_step"])),
            ("step_entity called by EyesAndHousePerFrame", rom_from("step_entity", "eyes_and_house_per_frame"), c_from("step_entity", ["eyes_and_house_per_frame"])),
            ("DrawReadyScreen entered in all = the C's draw_ready_screen calls + the same three steps written inline in start_tune_step (tune step $28)", sum(v for (e, o), v in PATHS_SRC.items() if e == name_addr["draw_ready_screen"]),
             sum(v for (cn, cl), v in sites.items() if cn == "draw_ready_screen") + c_from("draw_all_in_place", ["start_tune_step"])),
            ("the ROM routine at $A70D serves the copyright wait AND the title menu = the C dispatcher's copyright_wait + title_menu calls", rom_from("copyright_wait", "frame_dispatch"), c_from("title_menu", ["frame_dispatch"]) + c_from("copyright_wait", ["frame_dispatch"])),
        ]
        ok = 0
        print("explanations, checked by number:")
        for text, r, c in checks:
            ok += 1 if r == c else 0
            print("  %s  ROM %d  C %d  %s" % ("OK  " if r == c else "FAIL", r, c, text))
        extra = rom_from("step_entity", "draw_all_in_place")
        print("  left over: StepEntity called by DrawAllInPlace %d times in the ROM, never in the C (its drawing is done inside draw_all_in_place); total difference of step_entity %d  %s" % (
            extra, [r for n, ad, r, k in diff if n == "step_entity"][0] - [k for n, ad, r, k in diff if n == "step_entity"][0], "OK" if extra == [r - k for n, ad, r, k in diff if n == "step_entity"][0] else "FAIL"))
        print("  %d of %d explanations hold" % (ok, len(checks)))
        return
    exe = os.path.join(ROOT, "build", "c82-gcc-Release", "shell", "pacman_a8.exe")
    out = None
    reps = []
    i = 0
    while i < len(a):
        if a[i] == "--exe":
            exe = os.path.abspath(a[i + 1])
            i += 2
        elif a[i] == "--counts-out":
            out = a[i + 1]
            i += 2
        else:
            reps.append(a[i])
            i += 1
    ed, named = entries_of_interest()
    E = edges()
    counting = Counting(ed.keys())
    rules_seen = Counter()
    tot = {"frames": 0, "transitions": 0, "classes": Counter(), "changes": Counter()}
    bad = 0
    for path in reps:
        res = run_one(path, exe, ed, counting, rules_seen, E)
        tot["frames"] += res["frames"]
        tot["transitions"] += res["transitions"]
        tot["classes"].update(res["classes"])
        tot["changes"].update(res["changes"])
        flag = res["class diffs"] or res["transition diffs"] or res["no rule"] or res["state diffs"]
        bad += 1 if flag else 0
        print("%s: %d frames, %d state-variable changes, class differences %d, transition differences %d, changes with no chain of rules %d, whole-state differences %d" % (
            os.path.basename(path), res["frames"], res["transitions"], len(res["class diffs"]), len(res["transition diffs"]), len(res["no rule"]), len(res["state diffs"])), flush=True)
        for k in ("class diffs", "transition diffs", "no rule", "state diffs"):
            for x in res[k][:3]:
                print("    ", k, x)
    print("TOTAL: %d frames, %d changes of state variables, %d of %d rules seen, classes: %s" % (tot["frames"], tot["transitions"], len([r for r in rules_seen if rules_seen[r]]), len(S.RULES),
          ", ".join("%s %d" % kv for kv in sorted(tot["classes"].items()))), flush=True)
    print("changes by variable: " + ", ".join("%s %d" % kv for kv in sorted(tot["changes"].items())))
    unseen = [S.RULES[i][4] for i in range(len(S.RULES)) if not rules_seen[i]]
    print("rules not seen (%d): %s" % (len(unseen), "; ".join(u[:60] for u in unseen)))
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"counts": {str(k): v for k, v in counting.counts.items()}, "by_source": {"%d,%d" % k: v for k, v in counting.by_source.items()}}, fh)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
