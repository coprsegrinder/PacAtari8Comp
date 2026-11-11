"""After the death: the restart of the turn and the 'get ready' display, frame by frame, and the effect of zp_AE. Checks the log of tools\\altirra_afterdeath.cmd (a real game, Pac-Man is killed by the ghosts).
Code (docs/20): when DeathSequence has run, zp_24 := 1 ($AEF1). $A805 then calls Sub_AA2D ($AA2D), which (one player, lives left) calls InitBoard ($ADAF), DrawLevelIndicator ($AC93: the READY! text tiles
$A2-$AB at $0DEF and the fruit row) and Sub_AD0E ($AD0E: Sub_AD49 draws the four ghosts and Pac-Man in place with zp_AE = 1, then lives - 1, then the life icons); back at $A810 zp_24 := 2 and zp_25 := $40.
$A81F counts zp_25 down; when it is 0, zp_24 := 0 and $A800 starts the play (ghost 0 state := 1, Sub_AD5E clears the READY row).
zp_AE: StepAndDrawEntity ($B902) moves a ghost one step in its direction (y -/+ 2, x -/+ 1) only when zp_AE = 0; with zp_AE <> 0 it only draws.
Usage: python -I tools/analyze_afterdeath_log.py <log> [--summary-file out]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

ZP = [S.rd(0xBB6F + i) for i in range(20)]            # ZeroPageInit80 -> zero page $80-$93
OWN = [S.rd(0xBBE2 + i) for i in range(8)]            # ColorsGame
RE_FR = re.compile(r"FR f=(\d+) z20=(\d+) z21=(\d+) z22=(\d+) z23=(\d+) z24=(\d+) z25=(\d+) z26=(\d+) z1c=(\d+) z1e=(\d+) a3=(\d+) ds=(\d+) ae=(\d+) lives=(\d+),(\d+) "
                   r"gs=\$(..),\$(..),\$(..),\$(..) gx=(\d+),(\d+),(\d+),(\d+) gy=(\d+),(\d+),(\d+),(\d+) px=(\d+) py=(\d+) pd=(\d+) txt=([0-9A-F]{28}) c=((?:\$..,?){8}) "
                   r"dots=(\d+),(\d+) fl=\$(..) bon=(\d+) fc=(\d+) fd=(\d+) ch=(\d+) aa=\$(..) cp=(\d+) leg=(\d+) pel=(\d+),(\d+),(\d+),(\d+)")
KEYS = ("f z20 z21 z22 z23 z24 z25 z26 z1c z1e a3 ds ae l1 l2 gs0 gs1 gs2 gs3 gx0 gx1 gx2 gx3 gy0 gy1 gy2 gy3 px py pd txt c dots0 dots1 fl bon fc fd ch aa cp leg p0 p1 p2 p3").split()


def parse_fr(m):
    g = m.groups()
    d = {}
    for k, v in zip(KEYS, g):
        if k == "txt":
            d[k] = v
        elif k == "c":
            d[k] = [int(x, 16) for x in v.replace("$", "").split(",") if x]
        elif k in ("fl", "aa") or k.startswith("gs"):
            d[k] = int(v, 16)
        else:
            d[k] = int(v)
    return d


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    items = []                                         # ("fr", dict) / ("ev", name, line) / ("sad_in", ...) / ("sad_out", ...) / ("sndw",) / ("textw", pc)
    for line in open(path, errors="replace"):
        line = line.rstrip("\n")
        if line.startswith("FR "):
            m = RE_FR.match(line)
            if m:
                items.append(("fr", parse_fr(m)))
        elif line.startswith("SAD_IN"):
            m = re.match(r"SAD_IN g=(\d) ae=(\d+) dir=(\d+) x=(\d+) y=(\d+) st=\$(..) f=(\d+)", line)
            items.append(("sad_in", int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6), 16)))
        elif line.startswith("SAD_OUT"):
            m = re.match(r"SAD_OUT g=(\d) x=(\d+) y=(\d+) f=(\d+)", line)
            items.append(("sad_out", int(m.group(1)), int(m.group(2)), int(m.group(3))))
        elif line.startswith("SNDW"):
            items.append(("sndw", line.split()[1]))
        elif line.startswith("TEXTW"):
            items.append(("textw", line.split()[1]))
        else:
            m = re.match(r"([A-Z_0-9]+)( .*)?$", line)
            if m and m.group(1) in ("DEATH_START", "DEATH_DONE", "INITBOARD_CALL", "INITBOARD", "LEVEL_INDICATOR", "SUB_AD0E", "SUB_AD49", "TURN_START", "AA2D_RETURN", "Z24_INC", "START_PLAY", "CLEAR_READY", "GAME_OVER_TEXT"):
                f = re.search(r"f=(\d+)", line)
                lv = re.search(r"lives=(\d+)", line)
                ev = ("ev", m.group(1), int(f.group(1)) if f else None, int(lv.group(1)) if lv else None)
                if items and items[-1] == ev:            # the debugger sometimes prints a tracepoint twice (same line, same frame)
                    continue
                items.append(ev)
    cnt = collections.Counter()
    bad = collections.defaultdict(list)
    names = [it[1] for it in items if it[0] == "ev"]
    P("frames logged:", sum(1 for it in items if it[0] == "fr"), " events:", dict(collections.Counter(names)))

    # ---------------- 1. every death -> restart ----------------
    done_idx = [i for i, it in enumerate(items) if it[0] == "ev" and it[1] == "DEATH_DONE"]
    ORDER = ["DEATH_DONE", "INITBOARD_CALL", "INITBOARD", "LEVEL_INDICATOR", "SUB_AD0E", "SUB_AD49", "TURN_START", "AA2D_RETURN", "Z24_INC", "START_PLAY", "CLEAR_READY"]
    gaps = collections.Counter()
    wait_lens = collections.Counter()
    snd_total = 0
    textw = collections.Counter()
    for di in done_idx:
        end = next((i for i in range(di, len(items)) if items[i][0] == "ev" and items[i][1] == "START_PLAY"), None)
        if end is None:
            continue
        evs = [(i, it) for i, it in enumerate(items[di:end + 3], di) if it[0] == "ev"]
        got = [it[1] for _, it in evs]
        if got != ORDER:
            bad["event order after the death"].append(got)
            continue
        cnt["deaths followed to the start of play"] += 1
        f_done = evs[0][1][2]
        f_play = evs[ORDER.index("START_PLAY")][1][2]
        gaps[f_play - f_done] += 1
        seg = items[di:end + 1]
        # sound registers written between the end of the death and the start of play
        snd = sum(1 for it in seg if it[0] == "sndw")
        snd_total += snd
        for it in items[di:end + 60]:
            if it[0] == "textw":
                textw[it[1]] += 1
        # the frame lines of this restart
        z24_idx = next(i for i, it in evs if it[1] == "Z24_INC")
        frs = [it[1] for it in items[z24_idx:end + 400] if it[0] == "fr"][:70]
        # first frame after the restart frame: zp_24 = 2, zp_25 = 64
        first = frs[0]
        exp = dict(z24=2, z25=64, ds=0, ae=0, aa=0, fc=0, fd=0, ch=0, cp=0, leg=0, gs0=0, gs1=0, gs2=0, gs3=0, pd=ZP[0x13], px=ZP[0x0E], py=ZP[0x09],
                   gx0=ZP[0x0A], gx1=ZP[0x0B], gx2=ZP[0x0C], gx3=ZP[0x0D], gy0=ZP[5], gy1=ZP[6], gy2=ZP[7], gy3=ZP[8], txt="0000" + "".join("%02X" % c for c in range(0xA2, 0xAC)) + "0000")
        diff = {k: (first[k], v) for k, v in exp.items() if first[k] != v}
        if first["c"] != OWN:
            diff["colours"] = (first["c"], OWN)
        if diff:
            bad["state in the first frame of the get-ready wait"].append((first["f"], diff))
        else:
            cnt["first frame of the wait: zp_24 = 2, zp_25 = 64, DeathState 0, zp_AE 0, zp_AA 0, ghosts state 0 at the ZeroPageInit80 positions, Pac-Man (124,164) facing left, colours = ColorsGame, READY tiles"] += 1
        # life counter went down by one, nothing else of the player changed
        pre = next(it[1] for it in reversed(items[:di]) if it[0] == "fr")
        ts_lives = next(it[3] for _, it in evs if it[1] == "TURN_START")
        if first["l1"] != ts_lives - 1 or first["l2"] != pre["l2"]:
            bad["lives after the restart"].append((ts_lives, first["l1"], first["l2"]))
        else:
            cnt["lives: TURN_START took exactly one life of player 1 (the value logged before the DEC, minus 1); player 2 untouched"] += 1
        same = all(pre[k] == first[k] for k in ("dots0", "dots1", "fl", "bon"))
        if not same:
            bad["board progress changed by the death"].append(({k: pre[k] for k in ("dots0", "dots1", "fl", "bon")}, {k: first[k] for k in ("dots0", "dots1", "fl", "bon")}))
        else:
            cnt["dots eaten, power-pellet flags and bonus counter are kept through the death"] += 1
        # the wait: zp_25 counts 64 .. 0, everything else is constant
        wait = [fr for fr in frs if fr["z24"] == 2]
        wait_lens[len(wait)] += 1
        z25 = [fr["z25"] for fr in wait]
        if z25 != list(range(64, -1, -1)):
            bad["zp_25 does not count 64..0"].append(z25[:6])
        const_keys = ("gs0", "gs1", "gs2", "gs3", "gx0", "gx1", "gx2", "gx3", "gy0", "gy1", "gy2", "gy3", "px", "py", "pd", "txt", "dots0", "dots1", "fl", "bon", "ds", "ae", "aa", "l1", "l2")
        if any(any(fr[k] != wait[0][k] for k in const_keys) for fr in wait):
            bad["something changed during the wait"].append(first["f"])
        else:
            cnt["wait: 65 frames with zp_25 = 64..0, ghosts, Pac-Man, READY row, lives, dots unchanged"] += 1
        pel = collections.Counter("%d,%d,%d,%d" % (fr["p0"], fr["p1"], fr["p2"], fr["p3"]) for fr in wait)
        if set(pel) - {"2,2,2,2"}:
            bad["power pellets blink during the wait"].append(dict(pel))
        # the first frame after the wait: play has started
        after = next(fr for fr in frs if fr["z24"] == 0)
        if after["gs0"] != 1 or after["gs1"] != 0 or after["gs2"] != 0 or after["gs3"] != 0 or after["txt"] != "0" * 28:
            bad["first frame of play"].append(after)
        else:
            cnt["first frame of play: zp_24 = 0, ghost 0 state 1, ghosts 1-3 state 0, READY row cleared"] += 1
    P()
    P("PART 1 - the restart after the death:", cnt["deaths followed to the start of play"], "deaths")
    P("  frames from the end of the death routine (zp_24 := 1) to the start of play:", dict(gaps))
    P("  frames in the wait (zp_24 = 2):", dict(wait_lens))
    P("  sound registers written between the end of the death and the start of play:", snd_total)
    P("  writes to the READY row ($0DED-$0DFA) in that time (by instruction):", dict(textw), "(AC97 = DrawLevelIndicator writes the 10 tiles, AD62 = Sub_AD5E clears 14 bytes at the start of play)")

    # ---------------- 2. zp_AE ----------------
    P()
    P("PART 2 - zp_AE: calls of StepAndDrawEntity ($B902) with the value of zp_AE and the ghost's coordinates before and after the movement code")
    table = collections.Counter()
    in_death = False
    near_ad49 = 0
    moved_ae0 = collections.Counter()
    ae1_where = collections.Counter()
    for i, it in enumerate(items):
        if it[0] == "ev":
            if it[1] == "DEATH_START":
                in_death = True
            elif it[1] == "INITBOARD":
                in_death = False
            elif it[1] == "SUB_AD49":
                near_ad49 = 4
        if it[0] != "sad_in":
            continue
        _, g, ae, d, x, y, st = it
        nxt = items[i + 1] if i + 1 < len(items) else None
        if not nxt or nxt[0] != "sad_out" or nxt[1] != g:
            table[("no movement/draw code reached (direction %d)" % d, ae)] += 1
            continue
        dx, dy = nxt[2] - x, nxt[3] - y
        table[("ae=%d" % ae, d, (dx, dy))] += 1
        expect = (0, 0)
        if ae == 0:
            expect = {1: (0, -2), 2: (0, 2), 4: (-1, 0), 8: (1, 0)}.get(d, (0, 0))
        if (dx, dy) != expect:
            bad["StepAndDrawEntity moved a ghost differently from the zp_AE rule"].append((it, nxt))
        if ae:
            if in_death:
                ae1_where["during the death freeze (set at $A92E)"] += 1
            elif near_ad49 > 0:
                ae1_where["inside Sub_AD49 (draw in place)"] += 1
            else:
                ae1_where["elsewhere"] += 1
                bad["zp_AE set outside the death and Sub_AD49"].append(it)
        if near_ad49 > 0 and it[0] == "sad_in":
            near_ad49 -= 1
    for k in sorted(table, key=str):
        P("  ", k, table[k])
    P("  calls with zp_AE <> 0 by place:", dict(ae1_where))
    ae0 = sum(v for k, v in table.items() if k[0] == "ae=0" and k[2] != (0, 0))
    ae1 = sum(v for k, v in table.items() if k[0] == "ae=1")
    ae1_moved = sum(v for k, v in table.items() if k[0] == "ae=1" and k[2] != (0, 0))
    P("  zp_AE = 0: %d calls moved the ghost by one step in its direction (all equal to the rule); zp_AE = 1: %d calls, %d moved a ghost" % (ae0, ae1, ae1_moved))

    # ---------------- 3. the death of the last life: game over ----------------
    go = [i for i, it in enumerate(items) if it[0] == "ev" and it[1] == "GAME_OVER_TEXT"]
    if go:
        P()
        P("PART 3 - the death of the last life: %d game over(s)" % len(go))
        for gi in go:
            frs = [it[1] for it in items[gi:] if it[0] == "fr"]
            first = frs[0]
            tiles_ok = first["txt"] == "".join("%02X" % c for c in range(0xAC, 0xBA))
            P("  first frame: zp_20 = %d, zp_24 = %d, zp_1E = %d, READY/GAME OVER row = %s, COLOR3 = $%02X, lives = %d,%d, DeathState %d, zp_AE %d" % (first["z20"], first["z24"], first["z1e"], first["txt"], first["c"][7], first["l1"], first["l2"], first["ds"], first["ae"]))
            if not (first["z20"] == 1 and first["z24"] == 0 and first["z1e"] == 226 and tiles_ok and first["c"][7] == 0x44 and first["l1"] == 0):
                bad["game-over state"].append(first)
            else:
                cnt["game over: zp_20 = 1, zp_24 = 0, zp_1E = $E2, GAME OVER tiles $AC-$B9 at $0DED, COLOR3 = $44 (red), lives 0"] += 1
            # the countdown: zp_1E drops by one every 8th jiffy; everything on the screen stays as it is
            drops = [(a["f"], b["f"]) for a, b in zip(frs, frs[1:]) if b["z1e"] != a["z1e"]]
            steps = collections.Counter(b - a for a, b in zip([d[0] for d in drops], [d[0] for d in drops][1:]))
            P("  zp_1E counted from %d to %d over %d frames (%d decrements; spacing in frames between decrements: %s)" % (frs[0]["z1e"], frs[-1]["z1e"], frs[-1]["f"] - frs[0]["f"], len(drops), dict(sorted(steps.items()))))
            const = ("txt", "gs0", "gs1", "gs2", "gs3", "gx0", "gx1", "gx2", "gx3", "gy0", "gy1", "gy2", "gy3", "px", "py", "ds", "ae", "l1", "l2", "z20", "dots0", "dots1")
            if any(any(fr[k] != first[k] for k in const) for fr in frs):
                bad["the game-over screen changed during the countdown"].append(first["f"])
            else:
                cnt["game over screen unchanged during the whole countdown (text, ghosts, Pac-Man, lives, dots)"] += 1
            P("  last logged frame %d: zp_1E = %d (after it the per-frame routine is not called again: the code at $A4ED sets zp_19 := 4 and the game leaves the board screen)" % (frs[-1]["f"], frs[-1]["z1e"]))
    P()
    for k in sorted(cnt):
        P("  %-150s %d" % (k, cnt[k]))
    P("violations:", {k: len(v) for k, v in bad.items()} or "none")
    for k, v in bad.items():
        P("  first", k, v[:2])
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
