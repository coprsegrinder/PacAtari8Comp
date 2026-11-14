"""A whole session of the game, checked against models of the code: the first board start (start tune), game over (high-score comparison, 30 s countdown), the return to the title screen,
and keys pressed during the countdown. Checks the log of tools\\altirra_fullgame.cmd (docs/21).
Code (docs/21): $A4A9.. (main loop, new game), $A7C8/$A7D3/$A7FE/$A800 (start of play: READY!, the 64-step tune every 4th frame, ghosts at step $28, clear READY!), $AAEF/$AB26 (game over: GAME OVER text,
score vs high score, digit by digit), $A78C (zp_1E counts down every 8th frame), $A4ED/$A4F1 (zp_1E = 0 -> zp_19 := 4), $A6CC (title states), $A4F5/$A504-$A559 (STRIG0/STRIG1/START/SELECT/OPTION).
Usage: python -I tools/analyze_fullgame_log.py <log> [--summary-file out]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

TUNE1 = [S.rd(0xBC50 + i) for i in range(64)]
TUNE2 = [S.rd(0xBC90 + i) for i in range(64)]
KV = re.compile(r"(\w+)=(\S+)")


def kv(line):
    d = {}
    for k, v in KV.findall(line):
        d[k] = v
    return d


def hx(s):
    return [int(s[i:i + 2], 16) for i in range(0, len(s), 2)]


def parse_fr(line):
    d = kv(line)
    o = {}
    for k, v in d.items():
        if k in ("sl", "s1", "s2", "hi"):
            o[k] = hx(v)
        elif k in ("lives", "lv", "in", "px"):
            o[k] = [int(x) for x in v.split(",")]
        elif k in ("c", "gs"):
            o[k] = [int(x.replace("$", ""), 16) for x in v.split(",")]
        elif k == "ch":
            o[k] = int(v.replace("$", ""), 16)
        else:
            o[k] = int(v)
    return o


def model_ab26(score, hi):
    """Sub_AB26: digit by digit from the left; at the first difference, if the score digit is greater the rest is copied; if smaller nothing."""
    hi = list(hi)
    for i in range(6):
        if score[i] == hi[i]:
            continue
        if score[i] > hi[i]:
            hi[i:] = score[i:]
            return hi, "copy"
        return hi, "less"
    return hi, "equal"


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    verbose = "--verbose" in sys.argv
    out = []

    def P(*a):
        s = " ".join(str(x) for x in a)
        out.append(s)
        print(s)

    frs, evs, sndw, textw, hsw = [], [], [], [], []
    for line in open(path, errors="replace"):
        line = line.rstrip("\n")
        if line.startswith("FR "):
            if not line.rstrip().endswith(tuple("0123456789")) or "py=" not in line:
                continue                                   # the last line is cut off when the process is stopped
            frs.append(parse_fr(line))
        elif line.startswith("SNDW"):
            m = re.match(r"SNDW pc=\$(\w+) f=(\d+)$", line)
            if not m:
                continue                                   # cut-off last line
            sndw.append((int(m.group(2)), int(m.group(1), 16)))
        elif line.startswith("TEXTW"):
            m = re.match(r"TEXTW pc=\$(\w+) f=(\d+)$", line)
            if not m:
                continue                                   # cut-off last line
            textw.append((int(m.group(2)), int(m.group(1), 16)))
        elif line.startswith("HSW"):
            m = re.match(r"HSW pc=\$(\w+) f=(\d+)$", line)
            if not m:
                continue                                   # cut-off last line
            hsw.append((int(m.group(2)), int(m.group(1), 16)))
        elif re.match(r"[A-Z_0-9]+ ", line) and not line.startswith("FR"):
            name = line.split()[0]
            d = kv(line)
            f = int(d["f"]) if "f" in d else None
            evs.append((name, f, d, line))
    # frames: the log has one FR per frame at the VBI; some frames may repeat after .restart - keep the order
    byf = {}
    for r in frs:
        byf.setdefault(r["f"], r)
    fnums = sorted(byf)
    P("Frames in the log: %d (f=%d .. %d); events: %d" % (len(frs), fnums[0], fnums[-1], len(evs)))
    # RTCLOK2 (low byte of the frame counter in the OS) from the TUNE events: rt = (f + off) mod 256
    tunes = [(f, int(d["x"]), int(d["rt"])) for (n, f, d, _) in evs if n == "TUNE"]
    offs = collections.Counter(((rt - f) & 255) for (f, x, rt) in tunes)
    P("RTCLOK2 - frame offsets seen at the tune steps (mod 256):", dict(offs))
    ok_off = len(offs) == 1
    off = list(offs)[0] if offs else 0
    rt_of = lambda f: (f + off) & 255

    # ---------------------------------------------------------------- games
    new = [(f, d) for (n, f, d, _) in evs if n == "NEWGAME"]
    P("\n== Games started: %d (NEWGAME events at frames %s)" % (len(new), [f for f, _ in new]))
    ev_by_name = collections.defaultdict(list)
    for (n, f, d, l) in evs:
        ev_by_name[n].append((f, d))
    allfail = []

    def first_after(name, f0, f1=10 ** 9):
        for (f, d) in ev_by_name[name]:
            if f0 <= f < f1:
                return f, d
        return None, None

    # ---------------------------------------------------------------- start of a board
    P("\n== First board start (NEWGAME -> start of play), per game")
    start_rows = []
    model_total = model_bad = 0
    for gi, (f0, d0) in enumerate(new):
        f1 = new[gi + 1][0] if gi + 1 < len(new) else 10 ** 9
        r_f, _ = first_after("RESTART", f0, f1)
        ib, _ = first_after("MAIN_INITBOARD", f0, f1)
        adf, _ = first_after("MAIN_ADF1", f0, f1)
        a632, _ = first_after("SUB_A632", f0, min(f1, f0 + 12))
        a64e, _ = first_after("SUB_A64E", f0, min(f1, f0 + 12))
        md, _ = first_after("MAIN_DONE", f0, f1)
        rd_f, _ = first_after("READY_DRAW", f0, f1)
        li, _ = first_after("LEVEL_INDICATOR", f0, f1)
        ad0e, _ = first_after("TUNE_AD0E", f0, f1)
        td, _ = first_after("TUNE_DONE", f0, f1)
        sp, _ = first_after("START_PLAY", f0, f1)
        cr, _ = first_after("CLEAR_READY", f0, f1)
        tn = [(f, int(d["x"]), int(d["a1"].replace("$", ""), 16), int(d["a2"].replace("$", ""), 16), int(d["rt"])) for (n, f, d, _) in evs if n == "TUNE" and f0 <= f < f1 and (td is None or f <= td)]
        steps_ok = [t[1] for t in tn] == list(range(64)) and len(tn) == 64
        gaps = [tn[i + 1][0] - tn[i][0] for i in range(len(tn) - 1)]
        gaps_ok = bool(gaps) and all(g == 4 for g in gaps)
        rt_ok = all(t[4] % 4 == 0 for t in tn)
        regs_ok = all(t[2] == TUNE1[t[1]] and t[3] == TUNE2[t[1]] for t in tn)
        pcs = collections.Counter(pc for (f, pc) in sndw if f0 <= f <= (sp or f1))
        tw = collections.Counter(pc for (f, pc) in textw if f0 <= f <= (cr or f1))
        lives_before = byf[ad0e]["lives"] if ad0e in byf else None
        lives_after = byf[ad0e + 1]["lives"] if (ad0e or 0) + 1 in byf else None
        order = [x for x in (r_f, ib, adf, md, rd_f, li, ad0e, td, sp, cr) if x is not None]
        order_ok = order == sorted(order) and len(order) == 10 or (len(order) == 10 and order == sorted(order))
        lvs = byf[sp + 1]["lv"] if sp and sp + 1 in byf else None
        row = dict(lvs=lvs, sl=int(byf[f0]["z1b"]) if f0 in byf else None, g=gi + 1, f0=f0, r=r_f, rd=rd_f, t0=tn[0][0] if tn else None, ad0e=ad0e, td=td, sp=sp, cr=cr, steps_ok=steps_ok, gaps_ok=gaps_ok, rt_ok=rt_ok, regs_ok=regs_ok, pcs=pcs, tw=tw,
                   lives=(lives_before, lives_after), order_ok=order_ok, a632=a632, a64e=a64e, z1a=int(d0["z1a"]))
        start_rows.append(row)
        # frame-by-frame model of zp_1C / zp_22 / zp_A3 / zp_21 from READY_DRAW to START_PLAY
        if rd_f and sp:
            z22, z21, a3 = 0, 0, 0
            for f in range(rd_f, sp + 3):
                if f not in byf:
                    continue
                r = byf[f]
                model_total += 1
                exp = (z22, a3, z21)
                got = (r["z22"], r["a3"], r["z21"])
                if f > rd_f and exp != got:
                    model_bad += 1
                    allfail.append(("start-model", gi + 1, f, exp, got))
                # state after this frame's $A78C
                if f == rd_f:
                    z22 += 1                      # LA7C8 (zp_1C = 2): zp_22++ , ATRACT 0, zp_1C := 0, DrawLevelIndicator
                elif z22 and z21 == 0 and rt_of(f) % 4 == 0:
                    if a3 == 0x40:
                        z21 += 1
                    else:
                        a3 += 1
    interrupted = [r for r in start_rows if None in (r["r"], r["rd"], r["t0"], r["ad0e"], r["td"], r["sp"])]
    start_rows = [r for r in start_rows if r not in interrupted]
    for r in interrupted:
        P("game %d: NEWGAME f=%d  start INTERRUPTED (a new game was started or the log ended before the tune finished; seen: RESTART %s, READY %s, tune start %s, tune done %s, start of play %s) - not checked"
          % (r["g"], r["f0"], r["r"], r["rd"], r["t0"], r["td"], r["sp"]))
    for r in start_rows:
        P("game %d: NEWGAME f=%d  RESTART +%s  READY drawn +%s  first tune step +%s  ghosts/Pac-Man drawn (step $28) +%s  tune done +%s  start of play +%s  READY cleared +%s  | 1P/2P z1a=%d scores cleared by %s | StartLevel %s, level counters at start of play %s"
          % (r["g"], r["f0"], r["r"] - r["f0"], r["rd"] - r["f0"], r["t0"] - r["f0"], r["ad0e"] - r["f0"], r["td"] - r["f0"], r["sp"] - r["f0"], (r["cr"] or 0) - r["f0"], r["z1a"],
             "Sub_A64E" if r["a64e"] else "Sub_A632", r["sl"], r["lvs"]))
        P("        tune: 64 steps in order %s, every 4th frame %s, RTCLOK2 mod 4 = 0 %s, AUDF1/AUDF2 equal the ROM tables %s;  lives at step $28: %s -> %s;  sound writes %s;  READY-row writes %s"
          % (r["steps_ok"], r["gaps_ok"], r["rt_ok"], r["regs_ok"], r["lives"][0], r["lives"][1], {"%04X" % k: v for k, v in sorted(r["pcs"].items())}, {"%04X" % k: v for k, v in sorted(r["tw"].items())}))
    P("Frame-by-frame model of zp_22, zp_A3, zp_21 from the READY! frame to the start of play: %d frames, %d mismatches" % (model_total, model_bad))
    for g in start_rows:
        if not (g["steps_ok"] and g["gaps_ok"] and g["rt_ok"] and g["regs_ok"] and g["order_ok"]):
            allfail.append(("start", g["g"]))
    # what the start durations are
    dts = collections.Counter((r["sp"] - r["rd"]) for r in start_rows)
    P("READY! drawn -> start of play (frames), per game:", dict(dts), "; first tune step after READY! (frames):", dict(collections.Counter(r["t0"] - r["rd"] for r in start_rows)))

    # ---------------------------------------------------------------- high score
    P("\n== High-score comparison (Sub_AB26), every call")
    ent = [(f, d) for (f, d) in ev_by_name["HS_ENTRY"]]
    ret_eq = {f: d for (f, d) in ev_by_name["HS_RET_EQUAL"]}
    rets = sorted([(f, "eq", d) for (f, d) in ev_by_name["HS_RET_EQUAL"]] + [(f, "ret", d) for (f, d) in ev_by_name["HS_RET"]], key=lambda t: t[0])
    cp = [(f, d) for (f, d) in ev_by_name["HS_COPY"]]
    # pair entries with the next return (in log order)
    order = [(n, f, d) for (n, f, d, _) in evs if n in ("HS_ENTRY", "HS_RET", "HS_RET_EQUAL", "HS_COPY")]
    calls, cur = [], None
    for (n, f, d) in order:
        if n == "HS_ENTRY":
            cur = dict(f=f, x=int(d["x"]), s=hx(d["s"]), hi=hx(d["hi"]), copied=0)
        elif n == "HS_COPY" and cur:
            cur["copied"] += 1
        elif n in ("HS_RET", "HS_RET_EQUAL") and cur:
            cur["after"] = hx(d["hi"])
            cur["eq_ret"] = n == "HS_RET_EQUAL"
            calls.append(cur)
            cur = None
    cases = collections.Counter()
    bad = 0
    for c in calls:
        exp, case = model_ab26(c["s"], c["hi"])
        got_case = "equal" if c["eq_ret"] else ("copy" if c["copied"] else "less")
        cases[(c["x"], got_case)] += 1
        if exp != c["after"] or case != got_case or (case == "copy" and c["copied"] != 6 - next(i for i in range(6) if c["s"][i] != c["hi"][i])):
            bad += 1
            allfail.append(("hs", c))
    P("Calls: %d  (X=$2A player 1, X=$47 player 2); model (digit by digit, copy from the first greater digit) matched in %d of %d (result of the compare and the new high score)" % (len(calls), len(calls) - bad, len(calls)))
    P("Cases (X, result):", {"%s:%s" % ("P1" if k[0] == 42 else "P2", k[1]): v for k, v in sorted(cases.items())})
    P("Order of the two calls at each game over (player 1 then player 2, same frame or the next):", collections.Counter((a["x"], b["x"], b["f"] - a["f"]) for a, b in zip(calls[::2], calls[1::2])))
    for c in calls:
        # the bytes are screen codes: $10-$19 are the digits 0-9 and $00 is blank (so $12 $15 $12 $10 is 2520, not 1215)
        dec = lambda b: "".join("" if v == 0 else str(v - 0x10) for v in b) or "-"
        P("  f=%d %s score=%s [%s] high %s [%s] -> %s [%s] (%d digits copied)" % (c["f"], "P1" if c["x"] == 42 else "P2", "".join("%02X" % x for x in c["s"]), dec(c["s"]), "".join("%02X" % x for x in c["hi"]), dec(c["hi"]), "".join("%02X" % x for x in c["after"]), dec(c["after"]), c["copied"]))
    # the high score only ever changes by Sub_AB26 (writes at $2039-$203E), never decreases
    hs_pcs = collections.Counter(pc for (f, pc) in hsw if f > 100)
    P("Writes to the high-score bytes $2039-$203E after the first 100 frames, by program counter:", {"%04X" % k: v for k, v in sorted(hs_pcs.items())})
    seq = [tuple(byf[f]["hi"]) for f in fnums]
    mono = all(a <= b for a, b in zip(seq, seq[1:]))
    chg = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    P("High score over all %d frames: never decreases %s; changes %d times" % (len(seq), mono, chg))
    if not mono:
        allfail.append(("hs-monotonic",))

    # ---------------------------------------------------------------- game over and countdown
    P("\n== Game over, countdown, return to the title")
    go_all = [(f, d) for (f, d) in ev_by_name["GAME_OVER_TEXT"]]
    go = [f for (f, d) in go_all if d["z23"] == "0"]
    P("GAME OVER text drawn at frames (final, z23 = 0):", go, "; drawn while the other player still plays (z23 <> 0, no score compare):", [f for (f, d) in go_all if d["z23"] != "0"])
    cd_total = cd_bad = 0
    cd_rows = []
    for gi, fgo in enumerate(go):
        # countdown: frames with z19 = 0 and z20 = 1 after the game-over frame
        fr = []
        for f in fnums:
            if f > fgo:
                if byf[f]["z20"] == 1 and byf[f]["z19"] == 0 and (not fr or f == fr[-1] + 1):
                    fr.append(f)
                elif fr:
                    break
        # the state in the frame after the game over
        nxt = byf.get(fgo + 1)
        if not fr:
            continue
        z1e = byf[fr[0]]["z1e"]
        steps = []
        last = None
        prev = z1e
        for f in fr:
            r = byf[f]
            cd_total += 1
            # model: A78C decrements zp_1E when rt & 7 = 0 and zp_1E > 0 (state seen at the next frame)
            if f + 1 in byf and byf[f + 1]["z19"] == 0 and byf[f + 1]["z20"] == 1:
                exp = r["z1e"] - (1 if (r["z1e"] > 0 and rt_of(f) % 8 == 0) else 0)
                if exp != byf[f + 1]["z1e"]:
                    cd_bad += 1
                    allfail.append(("countdown-model", f))
            if r["z1e"] != prev:
                steps.append(f)
                prev = r["z1e"]
        gaps = collections.Counter(b - a for a, b in zip(steps, steps[1:]))
        cdn = [f for (f, d) in ev_by_name["COUNTDOWN_DONE"] if fgo < f <= fr[-1] + 2]
        cd_rows.append((gi + 1, fgo, z1e, len(steps), dict(gaps), cdn[0] if cdn else None, fr[0], fr[-1]))
    for (g, fgo, z1e, n, gaps, cdn, a, b) in cd_rows:
        P("game over %d at f=%d: zp_1E starts at %d, %d steps, gaps %s, frames in the countdown state %d..%d, COUNTDOWN_DONE (main loop sees zp_1E = 0) %s" % (g, fgo, z1e, n, gaps, a, b, ("at f=%d" % cdn) if cdn else "not reached (countdown ended by a key)"))
    P("Countdown model (zp_1E decrements when RTCLOK2 AND 7 = 0): %d frames checked, %d mismatches" % (cd_total, cd_bad))

    # first frames after the game over
    for fgo in go[:1]:
        for f in range(fgo + 1, fgo + 3):
            if f in byf:
                r = byf[f]
                P("  frame after game over f=%d: z19=%d z20=%d z1e=%d z23=%d z24=%d lives=%s col3=$%02X display list=$%s s1=%s hi=%s" % (f, r["z19"], r["z20"], r["z1e"], r["z23"], r["z24"], r["lives"], r["c"][3], "".join("%02X" % x for x in r["sl"]), "".join("%02X" % x for x in r["s1"]), "".join("%02X" % x for x in r["hi"])))
    # return to the title: first frame with z19 = 4
    P("\nReturn to the title after a completed countdown:")
    for (f, d) in ev_by_name["SET_Z19"]:
        if d.get("new") != "4":
            continue
        t4 = [x for x in fnums if x >= f and byf[x]["z19"] == 4]
        if not t4:
            continue
        a = t4[0]
        before = byf[a - 1]
        after = byf[a]
        later = byf[t4[min(len(t4) - 1, 5)]]
        P("  SET z19 := 4 at f=%d (zp_1E = %s, zp_20 = %s); first VBI with z19 = 4: f=%d (+%d). Before: display list $%s colours %s lives %s ; at z19=4: display list $%s colours %s, ATRACT=%d, z20=%d z1e=%d scores s1=%s hi=%s"
          % (f, d["z1e"], d["z20"], a, a - f, "".join("%02X" % x for x in before["sl"]), ["%02X" % c for c in before["c"]], before["lives"], "".join("%02X" % x for x in later["sl"]), ["%02X" % c for c in later["c"]], later["at"], later["z20"], later["z1e"], "".join("%02X" % x for x in later["s1"]), "".join("%02X" % x for x in later["hi"])))
        # how long, what changes while the title stays
        end = a
        for x in fnums:
            if x >= a and byf[x]["z19"] == 4:
                end = x
            elif x > a and byf[x]["z19"] != 4:
                break
        diff = collections.Counter()
        for x in range(a + 1, end + 1):
            if x in byf and x - 1 in byf:
                for k in byf[x]:
                    if k not in ("f", "z45", "at") and byf[x][k] != byf[x - 1][k]:
                        diff[k] += 1
        P("    title state 4 lasted %d frames (f=%d..%d); variables that changed during it (other than the debounce counter zp_45 and ATRACT): %s" % (end - a + 1, a, end, dict(diff) or "none"))
    # attract counter
    a4 = [byf[f]["at"] for f in fnums if byf[f]["z19"] == 4]
    if a4:
        P("  ATRACT ($4D) while in title state 4: starts at %d, ends at %d after %d frames (the OS adds 1 about every 256 frames; from $80 on the OS rotates and dims the colours)" % (a4[0], a4[-1], len(a4)))
    a0 = [byf[f]["at"] for f in fnums if byf[f]["z19"] == 0 and byf[f]["z20"] == 0 and byf[f]["z21"] == 1]
    if a0:
        P("  ATRACT ($4D) during play (z19 = 0): values seen %d..%d (the game sets it to 0 when READY! is drawn, to 3 or 4 when the title is entered)" % (min(a0), max(a0)))
    # title colours against the ROM
    tc = [S.rd(0xBBEA + i) for i in range(4)]
    seen = set()
    for f in fnums:
        if byf[f]["z19"] >= 3:
            seen.add(tuple(byf[f]["c"][:4]))
    P("  title colours COLOR0-3 seen in states 3/4: %s; ROM ColorsTitle ($BBEA): %s" % ([["%02X" % c for c in s] for s in sorted(seen)], ["%02X" % c for c in tc]))

    # ---------------------------------------------------------------- key presses
    P("\n== Keys during the countdown and at the title (injected at the controller registers)")
    inj = [f for f in fnums if any(byf[f]["in"])]
    # group into press windows
    wins = []
    for f in inj:
        if wins and f - wins[-1][1] <= 2:
            wins[-1][1] = f
        else:
            wins.append([f, f])
    for (a, b) in wins:
        r = byf[a]
        which = {1: "START(CONSOL=6)", 2: "SELECT(CONSOL=5)", 4: "OPTION(CONSOL=3)"}.get(r["in"][0], None)
        if r["in"][1]:
            which = "STRIG0"
        if r["in"][2]:
            which = "STRIG1"
        nxt = None
        for (n, f, d, _) in evs:
            if f is not None and f >= a and n in ("NEWGAME", "KEY_SELECT", "KEY_OPTION", "SET_Z19"):
                nxt = (n, f, d)
                break
        g_at = r["g"]
        P("press %-16s frames %d..%d (game counter %d): state z19=%d z20=%d z1e=%d, StartLevel=%d, 1P/2P z1a=%d, lives=%s, s1=%s hi=%s  ->  first reaction: %s at f=%s (+%s frames)"
          % (which, a, b, g_at, r["z19"], r["z20"], r["z1e"], r["z1b"], r["z1a"], r["lives"], "".join("%02X" % x for x in r["s1"]), "".join("%02X" % x for x in r["hi"]), (nxt[0] + (" new=" + nxt[2]["new"] if nxt and nxt[0] == "SET_Z19" else "")) if nxt else None, nxt[1] if nxt else None, (nxt[1] - a) if nxt else None))
        if nxt:
            P("      press held %d frames (%d..%d); the reaction came %d frame(s) after the last frame of the press" % (b - a + 1, a, b, nxt[1] - b))
        if nxt and verbose:
            f2 = nxt[1]
            seq = []
            for f in range(f2 - 1, f2 + 6):
                if f in byf:
                    q = byf[f]
                    seq.append("f=%d z19=%d z20=%d z1e=%d z1a=%d sl=%s s1=%s lives=%s lv=%s" % (f, q["z19"], q["z20"], q["z1e"], q["z1a"], "".join("%02X" % x for x in q["sl"]), "".join("%02X" % x for x in q["s1"]), q["lives"], q["lv"]))
            P("      frames around the reaction:\n        " + "\n        ".join(seq[:5]))
    # frozen countdown after SELECT / OPTION
    P("\nKEY_SELECT / KEY_OPTION events:", [(n, f, d.get("z19"), d.get("z1e"), d.get("z1a") or d.get("startlevel")) for (n, f, d, _) in evs if n in ("KEY_SELECT", "KEY_OPTION")])
    P("SET_Z19 events (new value, frame, zp_20, zp_1E):", [(d["new"], f, d["z20"], d["z1e"]) for (f, d) in ev_by_name["SET_Z19"]])
    # a title (state 3) after SELECT/OPTION: z1e frozen, Sub_A632 each frame, scores cleared
    st3 = [f for f in fnums if byf[f]["z19"] == 3 and byf[f]["g"] >= 2]
    if st3:
        runs = []
        for f in st3:
            if runs and f == runs[-1][1] + 1:
                runs[-1][1] = f
            else:
                runs.append([f, f])
        for (a, b) in runs:
            P("Title state 3 f=%d..%d (%d frames): zp_20 %s, zp_1E %s (frozen), 1P/2P z1a %s, StartLevel %s; score at entry %s, from the next frame %s; high score %s"
              % (a, b, b - a + 1, sorted(set(byf[f]["z20"] for f in range(a, b + 1) if f in byf)), sorted(set(byf[f]["z1e"] for f in range(a, b + 1) if f in byf)),
                 sorted(set(byf[f]["z1a"] for f in range(a, b + 1) if f in byf)), sorted(set(byf[f]["z1b"] for f in range(a, b + 1) if f in byf)),
                 "".join("%02X" % x for x in byf[a]["s1"]), sorted(set("".join("%02X" % x for x in byf[f]["s1"]) for f in range(a + 1, b + 1) if f in byf)),
                 sorted(set("".join("%02X" % x for x in byf[f]["hi"]) for f in range(a, b + 1) if f in byf))))

    # ---------------------------------------------------------------- lives, refills
    P("\n== Lives (no refill anywhere in this session)")
    live_seq = []
    for gi, (f0, d0) in enumerate(new):
        f1 = new[gi + 1][0] if gi + 1 < len(new) else 10 ** 9
        s = []
        for f in fnums:
            if f0 <= f < f1:
                l = tuple(byf[f]["lives"])
                if not s or s[-1] != l:
                    s.append(l)
        live_seq.append(s)
        P("game %d lives (P1,P2) over time: %s" % (gi + 1, s))
    deaths = len(ev_by_name["DEATH_START"])
    P("Deaths: %d; game overs: %d; INITBOARD_CALL (restart after a death): %d" % (deaths, len(go), len(ev_by_name["INITBOARD_CALL"])))
    P("\nPROBLEMS: %s" % (allfail[:10] if allfail else "none"))
    if summary:
        with open(summary, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if allfail else 0


if __name__ == "__main__":
    sys.exit(main())
