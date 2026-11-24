"""Stage 60 (behaviour correlation): what the code is (static), what the game does (live) and what a model says (executable), tied together per behaviour, per algorithm and per routine - and checked mechanically.

Sources (nothing is re-measured here): the 81 routines of tools/analyze_functions.py; the 22 algorithms of tools/analyze_constants.py; the live coverage (analysis/evidence-coverage-summary.txt), the register audit
(analysis/evidence-registers-summary.txt) and the model coverage (analysis/evidence-model-coverage-summary.txt); the register docs/OPEN-VERIFICATION.md; the files of the repository.  The BEHAVIOURS table below is the one
curated part: for each observable behaviour of the game, the routines that implement it, the chapter that states the rule, the register entries that hold the live measurement, the harness sessions and the tests.
Mechanical checks (tests/test_correlation.py): every routine belongs to a behaviour; every behaviour has code, a chapter, live evidence (register entry C-nn, closed) and an executable check (a test file); every file and
every register entry named exists; no verification item is open except OV-71 (the routine-path comparison of the key loop), OV-72 (machines and compilers the port was not tried on), OV-75 and OV-76 (what stage J could not test, one unexplained window capture); OV-02, the port, closed in stage 87; every algorithm is carried by a behaviour.
Usage: python -I tools/analyze_correlation.py [--doc docs/36-behaviour-correlation.md]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_constants as AC  # noqa: E402
import analyze_stack as AS  # noqa: E402

ROOT = os.path.dirname(HERE)

# (id, behaviour, algorithms, chapters, register entries, harness sessions, tests)
BEHAVIOURS = [
    ("B01", "Start-up: the tables, the maze and the character sets are expanded; the key loop starts", ["A01"], ["12", "21"], ["C-01", "C-59", "C-60"], ["pregame", "fullgame"], ["test_streams", "test_nibble_map", "test_algorithms", "test_start_gameover"]),
    ("B02", "Title, game start, one / two players, start level, game over, high score, return to the title", ["A02"], ["21", "19"], ["C-02", "C-03", "C-07", "C-44", "C-52"], ["pregame", "gameover", "inputs"], ["test_start_gameover", "test_pregame", "test_title_text"]),
    ("B03", "The frame: one deferred vertical-blank call runs the game; every slower action is paced by the jiffy clock", ["A03"], ["24", "17", "18", "20"], ["C-45", "C-60", "C-67"], ["fullgame", "speed"], ["test_timer_budgets", "test_relationships", "test_hw"]),
    ("B04", "The picture: display-list interrupts and colour bands, the colours of the maze, items, ghosts and labels", ["A04"], ["15", "06"], ["C-50", "C-51", "C-52", "C-67"], ["colors", "titleicons", "itemshots"], ["test_sight_colors", "test_overlap_shots", "test_text_shots", "test_hw"]),
    ("B05", "Pac-Man's movement: joystick, cornering, sub-cells, the tunnel wrap", ["A05"], ["20", "16"], ["C-46", "C-62", "C-60"], ["tunnel_bot", "fullgame"], ["test_tunnel_clip", "test_algorithms_more"]),
    ("B06", "Dots and power pellets, the dot count", ["A06"], ["20", "12"], ["C-56", "C-60", "C-48"], ["fullgame", "frightened_cases"], ["test_algorithms2", "test_structures"]),
    ("B07", "Score, the extra life, the high score digits", ["A07"], ["12", "19"], ["C-23", "C-31", "C-32", "C-59"], ["extra_life", "extra_life2", "p2win"], ["test_algorithms", "test_ghost_score"]),
    ("B08", "Speed by level: the pacing tables of Pac-Man and of the ghosts", ["A08"], ["14", "18"], ["C-45", "C-59"], ["levels", "speed"], ["test_levels", "test_algorithms"]),
    ("B09", "Ghost steering: lattice points, junction exits, target steering, the random choice", ["A09", "A10"], ["13", "18"], ["C-59", "C-60", "C-55"], ["steering", "patrol"], ["test_algorithms", "test_ghost_transitions"]),
    ("B10", "Ghost behaviour: start route, patrol, corner, chase, the sight test and the forced chase", ["A11", "A12"], ["13", "17", "15"], ["C-45", "C-60", "C-64"], ["patrol", "sight", "sight_states", "transitions", "forcechase"], ["test_ghost_states", "test_ghost_transitions", "test_ghost_sweep_model", "test_timer_budgets"]),
    ("B11", "The ghost house: waiting, bobbing, release timers, leaving", ["A13"], ["18", "14"], ["C-45", "C-48", "C-56"], ["house_frightened", "fullgame"], ["test_frightened_house", "test_algorithms_more"]),
    ("B12", "The frightened period: reversal, countdown, flashing, the order of the ghosts", ["A14"], ["14", "18", "17"], ["C-48", "C-45", "C-64"], ["frightened_cases", "house_frightened"], ["test_frightened_cases", "test_frightened_house"]),
    ("B13", "A ghost is eaten: pop-up score, the pause with its sweep, the eyes' way home and the re-entry", ["A15", "A16"], ["12", "18", "22"], ["C-48", "C-58", "C-50"], ["eaten_dir", "door_up", "catch"], ["test_ghost_score", "test_door_up", "test_frightened_cases"]),
    ("B14", "Contact, death and the death animation", ["A17"], ["20", "22"], ["C-05", "C-34", "C-60"], ["death", "afterdeath"], ["test_death"]),
    ("B15", "Turns, lives and two players: the READY! screen, saved mazes, the switch of turn", ["A18"], ["19"], ["C-47", "C-52", "C-64"], ["player2", "player2_lives", "player1_survives", "p2win"], ["test_two_players"]),
    ("B16", "Level complete and the next board, the level indicator", ["A19"], ["14", "20"], ["C-56", "C-50", "C-60"], ["levels", "forcechase"], ["test_levels", "test_algorithms_more"]),
    ("B17", "The bonus item: when it appears, what it is worth, its score picture", ["A20"], ["14", "15"], ["C-35", "C-36", "C-37", "C-50"], ["itemshots", "sound_bot"], ["test_item_shots"]),
    ("B18", "Drawing the entities: the ghost frames, the overlap rule, the tunnel clip", ["A21"], ["16", "20"], ["C-46", "C-51", "C-50"], ["tunnel_clip", "catch"], ["test_ghost_frames", "test_overlap_shots", "test_tunnel_clip"]),
    ("B19", "Sound: every sound the ROM can make, its pitch, level and waveform", ["A22"], ["22"], ["C-08", "C-09", "C-10", "C-13", "C-22", "C-33", "C-34", "C-43"], ["sound_bot", "fullgame"], ["test_sound", "test_full_waveform", "test_mixer", "test_pokey_noise", "test_pokey_timers", "test_hp"]),
    ("B20", "The inputs and outputs and the contact with the OS: joystick, triggers, console, keyboard, chips", ["A02", "A04"], ["33", "35"], ["C-63", "C-67", "C-68"], ["inputs", "inputs1", "realkey", "pause"], ["test_io", "test_hw", "test_realkey"]),
    ("B21", "The memory: the stack, the six data pointers, the structures", ["A01", "A08"], ["28", "29", "30"], ["C-54", "C-55", "C-56"], ["fullgame", "death", "levels"], ["test_stack", "test_pointers", "test_structures", "test_locals"]),
    ("B22", "The pause key", ["A02"], ["21", "32"], ["C-61", "C-68"], ["pause", "realkey"], ["test_tracing", "test_realkey"]),
    ("B23", "The state machines: the 20 state variables and their 68 transition rules", ["A03", "A11", "A18"], ["34", "17", "18"], ["C-64", "C-65", "C-66"], ["fullgame", "frightened_cases"], ["test_states", "test_absint"]),
    ("B24", "The code itself: every instruction run, every routine entered, the register and memory contracts", [], ["32", "23", "27"], ["C-61", "C-62", "C-60"], ["fullgame", "ov59_tunnel", "ov59_row6", "two_keys"], ["test_tracing", "test_functions", "test_algorithms_more"]),
]


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return fh.read()


def register():
    """-> dict id -> (status line text); C entries and OV entries"""
    txt = read("docs/OPEN-VERIFICATION.md")
    out = {}
    for ln in txt.splitlines():
        m = re.match(r"^\| ((?:C|OV)-[0-9a-z]+) \| (.*)$", ln)
        if m:
            out[m.group(1)] = ln
    return out


def ov_status(reg):
    """-> {id: 'OPEN' | 'PARTIAL' | 'CLOSED'}"""
    res = {}
    for k, ln in reg.items():
        if not k.startswith("OV-"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        st = "CLOSED" if ("*(closed" in ln or any(c.startswith("CLOSED") for c in cells)) else ("PARTIAL" if any(c.startswith("PARTIAL") for c in cells) else ("OPEN" if any(c == "OPEN" for c in cells) else "?"))
        res[k] = st
    return res


def coverage_data():
    never = {}
    txt = read("analysis/evidence-coverage-summary.txt")
    for m in re.finditer(r"^  (\w+)\s+(\d+) of\s+(\d+):", txt, re.M):
        never[m.group(1)] = int(m.group(2))
    head = re.search(r"(\d+) of (\d+) instructions executed", txt)
    return never, head.groups() if head else None


def register_calls():
    txt = read("analysis/evidence-registers-summary.txt")
    calls = {}
    for m in re.finditer(r"^(\w+)\s+(\d+) ", txt, re.M):
        calls[m.group(1)] = int(m.group(2))
    return calls


def routines():
    rom, F, owner = AS.load()
    return {F[e].name: len(F[e].body) for e in F}, len(rom.ins)


def build():
    nroutine, ntotal = routines()
    r_alg = AC.routine_algorithm()
    for r, a in AC.EXTRA_ROUTINES.items():
        r_alg.setdefault(r, [])
        if a not in r_alg[r]:
            r_alg[r].append(a)
    algs = {a[0]: a for a in AC.ALGORITHMS}
    never, head = coverage_data()
    calls = register_calls()
    reg = register()
    ovs = ov_status(reg)
    problems = []
    alg_beh = {}
    for b in BEHAVIOURS:
        for a in b[2]:
            alg_beh.setdefault(a, []).append(b[0])
    # routines -> behaviours (through the algorithms); B24 carries the code itself (every routine)
    rb = {}
    for r in nroutine:
        rb[r] = sorted({bid for a in r_alg.get(r, []) for bid in alg_beh.get(a, [])})
    for r, bs in rb.items():
        if not bs:
            problems.append("routine %s belongs to no behaviour" % r)
    for a in algs:
        if a not in alg_beh:
            problems.append("algorithm %s carried by no behaviour" % a)
    for b in BEHAVIOURS:
        bid, name, al, ch, cs, hs, ts = b
        if not al and bid != "B24":
            problems.append("%s has no algorithm" % bid)
        for c in ch:
            fn = [f for f in os.listdir(os.path.join(ROOT, "docs")) if f.startswith(c + "-")]
            if not fn:
                problems.append("%s: chapter %s missing" % (bid, c))
        for c in cs:
            if c not in reg:
                problems.append("%s: register entry %s missing" % (bid, c))
        for h in hs:
            if not os.path.isfile(os.path.join(ROOT, "tools", "altirra_%s.cmd" % h)):
                problems.append("%s: harness altirra_%s.cmd missing" % (bid, h))
        for t in ts:
            if not os.path.isfile(os.path.join(ROOT, "tests", t + ".py")):
                problems.append("%s: test %s missing" % (bid, t))
        if not ts or not cs or not hs:
            problems.append("%s lacks live evidence or an executable check" % bid)
    open_items = sorted(k for k, v in ovs.items() if v != "CLOSED")
    if open_items != ["OV-71", "OV-72", "OV-75", "OV-76"]:
        problems.append("open verification items: %s (expected only OV-71, OV-72, OV-75 and OV-76)" % open_items)
    return {"ntotal": ntotal, "nroutine": nroutine, "r_alg": r_alg, "algs": algs, "never": never, "head": head, "calls": calls, "reg": reg, "ovs": ovs, "problems": problems, "rb": rb, "alg_beh": alg_beh, "open": open_items}


def doc_lines():
    D = build()
    L = []
    P = L.append
    nr = D["nroutine"]
    tot_ins = D["ntotal"]
    ncs = len([k for k in D["reg"] if k.startswith("C-")])
    nov = len([k for k in D["ovs"]])
    nclosed = len([k for k, v in D["ovs"].items() if v == "CLOSED"])
    P("# 36 - Behaviour Correlation (stage 60)")
    P("")
    P("GENERATED by `python -I tools/analyze_correlation.py --doc docs/36-behaviour-correlation.md` from the routines (`23`), the algorithms (`31`), the evidence summaries of the coverage, register and model audits and the register `OPEN-VERIFICATION.md`; the curated part is the `BEHAVIOURS` table of the tool. Tests: `tests/test_correlation.py`.")
    P("")
    P("## 1. The result")
    P("")
    P("- The behaviour of the game is cut into **%d behaviours** (section 2). Each has its **code** (routines through the algorithms of `31`), its **rule** (the chapter), its **live measurement** (register entries C-nn, closed, with the harness sessions of the real game in Altirra) and an **executable check** (test files, and the ROM run against models in `tools/cpu6502.py`)." % len(BEHAVIOURS))
    P("- **Every one of the %d routines belongs to at least one behaviour**, every one of the 22 algorithms is carried by one, and every file and register entry named below exists (checked by `tests/test_correlation.py`)." % len(nr))
    P("- **Static = live = model, instruction by instruction**: %s of the %d instructions of the ROM were executed by the live sessions (the %s never executed are dead code of the original, `32`), and all %d were executed by the model comparisons, the whole memory compared after every call (`31` section 5)." % (D["head"][0] if D["head"] else "?", tot_ins, str(tot_ins - int(D["head"][0])), tot_ins))
    P("- The register holds %d verification items (OV-nn): **%d closed, %d open: %s** - the C port against the original was tested in stages 86-87 (`52`, `53`: OV-02 and OV-70 closed); the open ones are the routine-path comparison of the key loop (OV-71) and the machines and compilers the port was not tried on (OV-72)." % (nov, nclosed, len(D["open"]), ", ".join(D["open"])))
    P("- Limits that apply to every row (owner's decision, `OPEN-VERIFICATION.md` OV-01, OV-42b, OV-49): all live measurements are Altirra 4.40 (NTSC and PAL, OS-B, the PAL OS and the built-in OS were also run); real hardware was not tested. The sessions run with the test aids of their harnesses (`04`), named in each harness; a claim holds for the game's own logic with those aids.")
    P("- Problems found by the mechanical check: **%d**%s" % (len(D["problems"]), "" if not D["problems"] else ": " + "; ".join(D["problems"])))
    P("")
    P("## 2. The behaviours")
    P("")
    P("| ID | Behaviour | Algorithms | Routines | Chapters | Live measurement (register) | Harness sessions | Tests |")
    P("|---|---|---|---|---|---|---|---|")
    for bid, name, al, ch, cs, hs, ts in BEHAVIOURS:
        rs = sorted([r for r, bs in D["rb"].items() if bid in bs]) if bid != "B24" else []
        P("| %s | %s | %s | %s | %s | %s | %s | %s |" % (bid, name, ", ".join(al) or "all", ("%d" % len(rs)) if rs else "all %d" % len(nr), ", ".join(ch), ", ".join(cs), ", ".join("`%s`" % h for h in hs), ", ".join("`%s`" % t for t in ts)))
    P("")
    P("## 3. The algorithms")
    P("")
    P("| ID | Algorithm | Routines | Behaviours | Status |")
    P("|---|---|---|---|---|")
    for aid, name, rs, rule, tables, evidence, status in AC.ALGORITHMS:
        P("| %s | %s | %d | %s | %s |" % (aid, name, len(rs), ", ".join(D["alg_beh"].get(aid, [])), status.split(" (")[0]))
    P("")
    P("## 4. The routines")
    P("")
    P("Per routine: its instructions, the instructions of it that the live sessions never executed (`32`), the completed calls in the 12 harnesses of the register audit (`32`; `-` = not called there, but entered in the coverage audit), the algorithms that contain it and the behaviours that carry it.")
    P("")
    P("| Routine | Instr. | Never run live | Calls (register audit) | Algorithms | Behaviours |")
    P("|---|---|---|---|---|---|")
    for r in sorted(nr):
        nv = D["never"].get(r, 0)
        P("| `%s` | %d | %s | %s | %s | %s |" % (r, nr[r], nv if nv else "0", D["calls"].get(r, "-"), ", ".join(sorted(D["r_alg"].get(r, []))), ", ".join(D["rb"][r])))
    P("")
    P("## 5. What is not correlated")
    P("")
    P("- **The port, in part.** OV-02 closed in stage 87: the C port equals the ROM frame by frame (`52`, `53`); what is not covered is OV-71 (routine call counts only for the vertical-blank handler, not for the key loop, the new-game sequence and the display-list interrupts), OV-72 (macOS, MSVC, 32-bit, big-endian, ARM; `54`) and the limits of `53` section 6 (samples of up to 12,000 frames, one board change at most).")
    P("- **The five instructions never executed live** are dead code of the original (`32`, OV-59, C-62): they were run by the model comparisons only.")
    P("- **Real hardware**, **a human playing every situation**: documented limits (`OPEN-VERIFICATION.md`).")
    P("")
    P("## 6. How to repeat")
    P("")
    P("`python -I tools/analyze_correlation.py --doc docs/36-behaviour-correlation.md` regenerates this chapter and prints the problems found; `python -I -m unittest discover -s tests -p test_correlation.py` fails on any problem or if the chapter is out of date.")
    return L, D


def main():
    L, D = doc_lines()
    if "--doc" in sys.argv:
        o = sys.argv[sys.argv.index("--doc") + 1]
        with open(os.path.join(ROOT, o), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(L) + "\n")
        print("wrote", o)
    print("problems:", len(D["problems"]))
    for p in D["problems"]:
        print("  ", p)


if __name__ == "__main__":
    main()
