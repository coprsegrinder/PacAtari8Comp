"""Stage 58, the proof step: the transition rules of tools/analyze_states.py against EVERY behaviour of the code, by the abstract search of tools/absint6502.py.

For a chosen set of followed state variables (a SLICE) the search starts at the key loop after `Start` (every followed variable 0, GameState 1), lets the vertical-blank handler enter between instructions of the main
loop (never two within 100 main-loop instructions; the real spacing is thousands), treats everything else (the other variables, the hardware, the joystick, the random counter, the positions, the timers) as unknown, and
collects every store to a followed variable with its writing instruction, the old and the new value.  Because every branch on something unknown is taken both ways, the result contains everything the code can do, for any
contents of the unknown memory; a store or a value that does not appear cannot happen.
Result per slice: the values each followed variable can take, and the triples (variable, writer, old, new).  A triple that no rule allows would be a transition the rules miss; a store of an unknown value would be
imprecision of the slice; the proof needs both counts to be 0 in every slice.
Slices (the ghost-0 slice G0 leaves out DeathAnimActive, PacFrozen and CountdownActive: the full set of 12 flow variables with ghost 0 did not finish in 4 h / 60 million states): R = the flow variables (GameState, IntroRequest, PlayStarted, StartTuneActive, WaitState, DeathState, DeathAnimActive, CountdownActive, LevelComplete, LevelEndStep, PacFrozen, EatPause);
G0..G3 = R + one ghost; TP, TU, PA, BV, BS = TwoPlayers, TurnSwitchState, Paused, BonusVisible, BonusScoreShown alone; F = FrightenPhase alone.  CurrentPlayer is followed in every slice (it is an index).
Usage: python -I tools/prove_state_rules.py --slice NAME     (runs one slice, keeps the result in a scratch file)
       python -I tools/prove_state_rules.py --combine [--write analysis/evidence-state-proof-summary.txt]   (reads the scratch files, writes the evidence)
"""
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import absint6502 as AB  # noqa: E402
import analyze_states as S  # noqa: E402

ROOT = os.path.dirname(HERE)
SUMMARY = os.path.join(ROOT, "analysis", "evidence-state-proof-summary.txt")
SCRATCH = os.path.join(ROOT, "analysis", "raw-logs")
ADDR = {n: a for a, n, s, d in S.STATES}
R_NAMES = ["GameState", "IntroRequest", "PlayStarted", "StartTuneActive", "WaitState", "DeathState", "DeathAnimActive", "CountdownActive", "LevelComplete", "LevelEndStep", "PacFrozen", "EatPause"]
SLICES = collections.OrderedDict([
    ("R", [ADDR[n] for n in R_NAMES]),
    ("TP", [ADDR["TwoPlayers"]]), ("TU", [ADDR["TurnSwitchState"]]), ("PA", [ADDR["Paused"]]), ("BV", [ADDR["BonusVisible"]]), ("BS", [ADDR["BonusScoreShown"]]),
    ("F", [ADDR["FrightenPhase"]]),
    ("G0", [ADDR[n] for n in ("GameState", "IntroRequest", "PlayStarted", "StartTuneActive", "WaitState", "DeathState", "LevelComplete", "LevelEndStep", "EatPause")] + [0xCE]),
 ("G1", [ADDR[n] for n in R_NAMES] + [0xCF]), ("G2", [ADDR[n] for n in R_NAMES] + [0xD0]), ("G3", [ADDR[n] for n in R_NAMES] + [0xD1]),
])
# finer ghost-0 slices: they follow the variables that the ghost-0 slice G0 leaves out (the full set of the 12 flow variables with ghost 0 did not finish in 4 h / 60 million states); each is sound alone (what is not followed is unknown), a finer slice can only have fewer stores than a coarser one
_G0 = list(SLICES["G0"])
CHECK_SLICES = collections.OrderedDict([
    ("G0c", _G0 + [ADDR["CountdownActive"]]),
    ("G0d", _G0 + [ADDR["DeathAnimActive"], ADDR["PacFrozen"]]),
])
SPACING = 100


def tracked_of(name):
    t = list(SLICES[name] if name in SLICES else CHECK_SLICES[name])
    if 0x2B not in t:
        t.append(0x2B)
    return t


def initial(tracked):
    """the state when the key loop of Start begins: every state variable 0 except GameState = 1 (`Start` cleared the zero page and counted the state up)"""
    return tuple(1 if a == 0x19 else 0 for a in tracked)


def run_slice(name, deadline=None, limit=60_000_000):
    prog = AB.Program()
    tracked = tracked_of(name)
    m = AB.Machine(prog, tracked)
    t = time.time()
    reach, events, nkeys = m.main_thread(initial(tracked), limit=limit, spacing=SPACING, deadline=deadline, progress=True)
    return {"name": name, "tracked": tracked, "reach": sorted(reach, key=lambda T: tuple(-1 if v is None else v for v in T)), "events": sorted(events, key=lambda e: tuple(-1 if v is None else v for v in e)),
            "keys": nkeys, "vbi_runs": len(m.vbi_cache), "havoc": m.havoc_count, "seconds": time.time() - t}


def save(res):
    os.makedirs(SCRATCH, exist_ok=True)
    with open(os.path.join(SCRATCH, "proof-slice-%s.json" % res["name"]), "w") as fh:
        json.dump(res, fh)


def load(name):
    with open(os.path.join(SCRATCH, "proof-slice-%s.json" % name)) as fh:
        d = json.load(fh)
    d["reach"] = [tuple(T) for T in d["reach"]]
    d["events"] = [tuple(e) for e in d["events"]]
    return d


def rule_pairs_by_site():
    by = collections.defaultdict(set)
    for rl in S.RULES:
        for pc in rl[3]:
            by[(rl[0], pc)] |= S.rule_pair_set(rl)
    return by


def flow_events():
    """the stores of the slice R, which follows every flow variable together: a store of such a variable that another slice sees but R does not is an imprecision of that slice (it did not follow a variable that rules the store out)"""
    try:
        return {(a, pc, o, n) for a, pc, o, n in load("R")["events"]}
    except OSError:
        return set()


def classify(res):
    """-> (extras, unknowns, race, imprecise): extras = no rule, not a race, not excluded by R; race = pairs of S.RACE_ONLY; imprecise = stores that R rules out"""
    by = rule_pairs_by_site()
    flow = flow_events()
    flow_vars = {ADDR[n] for n in R_NAMES}
    extras, unknowns, race, imprecise = [], [], [], []
    for a, pc, old, new in res["events"]:
        name = S.ADDR[a][0]
        if old is None or new is None:
            unknowns.append((name, a, pc, old, new))
            continue
        if old == new:
            continue
        al = by.get((name, pc), set())
        bulk = any(pc == cpc and lo <= a <= hi for cpc, lo, hi, t in S.BULK_CLEARS) or pc in S.BOOT_PCS
        if (old, new) in al or (bulk and new == 0):
            continue
        ro = S.RACE_ONLY.get((name, pc))
        if ro and ro[0](old) == new:
            race.append((name, a, pc, old, new))
        elif a in flow_vars and (a, pc, old, new) not in flow and res["name"] != "R":
            imprecise.append((name, a, pc, old, new))
        else:
            extras.append((name, a, pc, old, new))
    return extras, unknowns, race, imprecise


def check(res):
    """-> (extras, unknowns): the stores (variable, address, pc, old, new) the search found that no rule allows (race-only and R-excluded ones not counted), and those with an unknown value"""
    extras, unknowns, race, imprecise = classify(res)
    return extras, unknowns


def report(results):
    L = []
    P = L.append
    P("Proof of the transition rules by abstract search (tools/prove_state_rules.py, tools/absint6502.py): the key loop after Start with the vertical-blank handler entering between its instructions (never two within %d), all memory that is not followed unknown" % SPACING)
    P("")
    tot_extra = tot_unknown = tot_race = 0
    for r in results:
        extras, unknowns, race, imprecise = classify(r)
        tot_extra += len(extras)
        tot_unknown += len(unknowns)
        tot_race += len(race)
        P("slice %s: followed %s; %d states of the main loop, %d runs of the vertical-blank handler (%.0f s); combinations of followed values reached: %d; stores seen: %d; stores of an unknown value: %d; stores that no rule allows: %d; race-only stores (RACE_ONLY of tools/analyze_states.py): %d; stores that slice R rules out (imprecision of this slice): %d; stores through an unknown index: %d" %
          (r["name"], " ".join("$%02X" % a for a in r["tracked"]), r["keys"], r["vbi_runs"], r["seconds"], len(r["reach"]), len(r["events"]), len(unknowns), len(extras), len(race), len(imprecise), r["havoc"]))
        for e in imprecise[:5]:
            P("  IMPRECISION OF THE SLICE (R has no such store): %s $%02X store at $%04X %02X -> %02X" % (e[0], e[1], e[2], e[3], e[4]))
        for e in extras[:20]:
            P("  NOT ALLOWED: %s $%02X store at $%04X %02X -> %02X" % (e[0], e[1], e[2], e[3], e[4]))
        for u in unknowns[:20]:
            P("  UNKNOWN VALUE: %s store at $%04X old %s new %s" % (u[0], u[2], "?" if u[3] is None else "%02X" % u[3], "?" if u[4] is None else "%02X" % u[4]))
    P("")
    P("totals over %d slices: stores that no rule allows: %d; stores of an unknown value: %d; race-only stores: %d" % (len(results), tot_extra, tot_unknown, tot_race))
    P("")
    P("values each variable can take (the union over the slices that follow it):")
    vals = collections.defaultdict(set)
    for r in results:
        for T in r["reach"]:
            for a, v in zip(r["tracked"], T):
                vals[S.ADDR[a][0]].add(v)
    for a, n, s, d in S.STATES:
        vs = [v for v in vals[n] if v is not None]
        if not vs:
            P("  %s: (not followed)" % n)
        elif n == "FrightenPhase":
            P("  %s: %d values, %02X..%02X" % (n, len(vs), min(vs), max(vs)))
        else:
            P("  %s: %s%s" % (n, " ".join("%02X" % v for v in sorted(vs)), "  + unknown" if None in vals[n] else ""))
    P("")
    P("the stores found (PROOF variable writer old new; one line per distinct triple with known values, over all slices):")
    seen = set()
    for r in results:
        for a, pc, old, new in r["events"]:
            if old is None or new is None or old == new:
                continue
            key = (S.ADDR[a][0], pc, old, new)
            if key not in seen:
                seen.add(key)
                P("PROOF %s %04X %02X %02X" % key)
    return L


def main():
    args = sys.argv[1:]
    if "--slice" in args:
        name = args[args.index("--slice") + 1]
        res = run_slice(name, limit=int(args[args.index("--limit") + 1]) if "--limit" in args else 60_000_000)
        save(res)
        extras, unknowns = check(res)
        print("slice %s: %d states, %d followed combinations, %d stores, %d not allowed, %d unknown, %.0f s" % (name, res["keys"], len(res["reach"]), len(res["events"]), len(extras), len(unknowns), res["seconds"]))
        for e in extras[:20]:
            print("  NOT ALLOWED", e[0], hex(e[2]), "%02X->%02X" % (e[3], e[4]))
        for u in unknowns[:10]:
            print("  UNKNOWN", u[0], hex(u[2]), u[3], u[4])
        return
    results, missing = [], []
    for n in list(SLICES) + [c for c in CHECK_SLICES if os.path.exists(os.path.join(SCRATCH, "proof-slice-%s.json" % c))]:
        if os.path.exists(os.path.join(SCRATCH, "proof-slice-%s.json" % n)):
            results.append(load(n))
        else:
            missing.append(n)
    L = report(results)
    L.insert(1, "slices not finished (no result yet, so nothing is claimed for them): %s" % (", ".join(missing) if missing else "none"))
    txt = "\n".join(L) + "\n"
    if "--write" in args:
        out = args[args.index("--write") + 1]
        with open(os.path.join(ROOT, out), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", out)
    print("\n".join(L[:20]))


if __name__ == "__main__":
    main()
