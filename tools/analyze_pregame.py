"""OV-34: the two-player pre-game screens and the maze copies at the turn switches, checked against the log of tools\\altirra_pregame.cmd.

1. The title screen in state 3, one player (before SELECT) and two players (after SELECT): the screen RAM written by Sub_A6CC ($A719-$A78B) is compared, byte for byte, with what the code writes from the ROM tables:
   $1C54 = (zp_1A + 1) | $50;  $1C90 = $12 (zp_1A = 0, "2" of "PRESS SELECT FOR 2 PLAYER GAME") or $11 (zp_1A <> 0);  $1C92.. = TextPlayerGame and $1C56.. = TextPlayerGame | $40;
   $1C7A.. TextPressSelectFor, $1CF2.. TextPressOptionTo, $1D56.. TextPressStartTo, $1CC6/$1CC7 = LevelIconCodes[StartLevel], +1, $1D05.. TextChangeDifficulty, $1D6D.. TextPlayGame.
2. The status-line labels "1UP" ($2004-$2006) and "2UP" ($2021-$2023) (Sub_AD69, Sub_AD9F, Sub_AD87): in a two-player game the label of the player NOT on turn is steady, the label of the player on turn is shown and blanked
   in turn (zp_FA toggles every 16th jiffy).
3. The maze copies (Copy0C00To1000, Copy0C00To1400, the loads at $AA3F / $AA69): after every save the saved copy equals the maze ($0C00) before it; after every load the maze equals the saved copy; the saved copy of a player has not
   changed between its save and its load; the first copy of both players equals the stored original ($0800); and the two players' mazes are not equal (so the check is not empty).
Usage: python -I tools\\analyze_pregame.py analysis\\raw-logs\\pregame.txt [--summary-file out.txt]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

DUMP = re.compile(r"^([0-9A-F]{4}): ((?:[0-9A-F]{2} ){1,16})\|")
FR = re.compile(r"FR f=(\d+) z19=(\d+) z1a=(\d+) cp=(\d+) fa=(\d+) lives=(\d+),(\d+) z23=(\d+) lev=(\d+),(\d+) l1=([0-9A-F]{6}) l2=([0-9A-F]{6}) t1=(\d+) t7=(\d+)")
MARK = re.compile(r"^(TITLE|SAVE1_IN|SAVE1_OUT|SAVE2_IN|SAVE2_OUT|LOAD1_IN|LOAD1_OUT|LOAD2_IN|LOAD2_OUT) f=(\d+)(.*)")
UP1, UP2, BLANK = "113530", "123530", "000000"                  # "1UP", "2UP" in the screen codes ($11 $35 $30 / $12 $35 $30), and blank


def parse(path):
    marks = []                       # (name, frame, extra, [dump, ...]) ; dump = [start, bytearray]
    frs = []
    cur = None
    for l in open(path, errors="replace"):
        m = MARK.match(l)
        if m:
            cur = [m.group(1), int(m.group(2)), m.group(3), []]
            marks.append(cur)
            continue
        m = DUMP.match(l)
        if m and cur is not None:
            a = int(m.group(1), 16)
            b = bytes(int(x, 16) for x in m.group(2).split())
            d = cur[3]
            if d and d[-1][0] + len(d[-1][1]) == a:
                d[-1][1] += b
            else:
                d.append([a, bytearray(b)])
            continue
        m = FR.match(l)
        if m:
            g = m.groups()
            frs.append(dict(f=int(g[0]), z19=int(g[1]), z1a=int(g[2]), cp=int(g[3]), fa=int(g[4]), l1=g[10], l2=g[11], t1=int(g[12]), t7=int(g[13])))
    return marks, frs


def rom(a, n):
    return bytes(S.rd(a + i) for i in range(n))


def expected_title(z1a, level):
    """{address: byte} of the screen RAM that Sub_A6CC writes in states >= 3."""
    e = {0x1C54: (z1a + 1) | 0x50, 0x1C90: 0x12 if z1a == 0 else 0x11}
    pg = rom(0xBFC6, 11)
    for i, b in enumerate(pg):
        e[0x1C92 + i] = b
        e[0x1C56 + i] = b | 0x40
    for base, src, n in ((0x1C7A, 0xBFD1, 16), (0x1CF2, 0xBFE1, 16), (0x1D56, 0xBDE7, 16), (0x1D05, 0xBDD6, 17), (0x1D6D, 0xBFF1, 9)):
        for i, b in enumerate(rom(src, n)):
            e[base + i] = b
    icon = S.rd(0xBE05 + level)
    e[0x1CC6] = icon
    e[0x1CC7] = (icon + 1) & 0xFF
    return e


def text(b):
    """Screen codes to text: 0 = space, $10-$19 digits, $21-$3A letters; the top two bits are the colour (mode 6)."""
    out, col = "", None
    for c in b:
        ch = c & 0x3F
        s = " " if ch == 0 else chr(0x30 + ch - 0x10) if 0x10 <= ch <= 0x19 else chr(0x41 + ch - 0x21) if 0x21 <= ch <= 0x3A else "?"
        out += s
    return out


def check_title(marks):
    L, bad = [], []
    titles = [m for m in marks if m[0] == "TITLE" and m[3] and "z19=3" in m[2]]
    res = {}
    for z1a in (0, 1):
        ms = [m for m in titles if "z1a=%d" % z1a in m[2]]
        n = bad_n = 0
        last = None
        for m in ms[2:]:                           # the first frames of a phase are still being drawn
            dump = m[3][0]
            if dump[0] != 0x1C00 or len(dump[1]) != 0x200:
                continue
            lv = int(re.search(r"lv=(\d+)", m[2]).group(1))
            e = expected_title(z1a, lv)
            diff = [(a, dump[1][a - 0x1C00], v) for a, v in e.items() if dump[1][a - 0x1C00] != v]
            n += 1
            if diff:
                bad_n += 1
                if len(bad) < 5:
                    bad.append((m[1], z1a, diff[:4]))
            last = (m, dump[1])
        res[z1a] = (len(ms), n, bad_n, last)
    return res, bad


def check_labels(frs):
    out = {}
    twop = [f for f in frs if f["z19"] == 0 and f["z1a"] == 1]
    dev = []
    runs = collections.defaultdict(list)
    cnt = collections.Counter()
    prev = None
    for f in twop:
        steady, mine = (f["l2"], f["l1"]) if f["cp"] == 0 else (f["l1"], f["l2"])
        want_steady = UP2 if f["cp"] == 0 else UP1
        want_mine = UP1 if f["cp"] == 0 else UP2
        cnt[("player %d on turn" % (f["cp"] + 1), "other label steady" if steady == want_steady else "other label NOT steady (%s)" % steady,
             "own label shown" if mine == want_mine else "own label blank" if mine == BLANK else "own label ODD (%s)" % mine)] += 1
        if steady != want_steady or mine not in (want_mine, BLANK):
            if len(dev) < 8:
                dev.append((f["f"], f["cp"], f["l1"], f["l2"]))
        key = (f["cp"], mine == BLANK)
        if prev and prev[0] == key and f["f"] == prev[1] + 1:
            prev[1] = f["f"]
            prev[2] += 1
        else:
            if prev:
                runs[prev[0]].append(prev[2])
            prev = [key, f["f"], 1]
    if prev:
        runs[prev[0]].append(prev[2])
    return cnt, dev, runs


def check_mazes(marks, frs):
    L, bad = [], []
    saved = {}                         # 1 / 2: the last saved copy of that player
    orig = None
    n_save = n_load = 0
    first = {}
    for name, f, extra, dumps in marks:
        if name.startswith("SAVE") or name.startswith("LOAD"):
            pass
    ev = [m for m in marks if m[0] != "TITLE"]
    i = 0
    pend = {}
    differ = []
    for name, f, extra, dumps in ev:
        if name in ("SAVE1_IN", "SAVE2_IN") and dumps:
            pend[name[4]] = bytes(dumps[0][1])
        elif name in ("SAVE1_OUT", "SAVE2_OUT") and dumps:
            p = name[4]
            n_save += 1
            dst = bytes(dumps[0][1])
            if p not in pend:
                bad.append("save %s at f=%d without its source" % (p, f))
            elif dst != pend[p]:
                bad.append("save %s at f=%d: saved copy differs from the maze before it (%d bytes)" % (p, f, sum(a != b for a, b in zip(dst, pend[p]))))
            saved[p] = dst
        elif name in ("LOAD1_IN", "LOAD2_IN") and dumps:
            p = name[4]
            src = bytes(dumps[0][1])
            n_load += 1
            if p in saved and src != saved[p]:
                bad.append("load %s at f=%d: the saved copy changed since its save (%d bytes)" % (p, f, sum(a != b for a, b in zip(src, saved[p]))))
            if len(dumps) > 1:
                orig = bytes(dumps[1][1])
            pend["L" + p] = src
        elif name in ("LOAD1_OUT", "LOAD2_OUT") and dumps:
            p = name[4]
            out = bytes(dumps[0][1])
            if out != pend.get("L" + p):
                bad.append("load %s at f=%d: the maze after it differs from the saved copy" % (p, f))
    # the first copies of both players of the game are the stored original
    firsts = {}
    g0 = next((f["f"] for f in frs if f["t7"] >= 1), 0)       # the frame where the real game starts ($A537 counted); the saves at the boot (before the title) copy an unset maze and are not game copies
    for name, f, extra, dumps in ev:
        if name in ("SAVE1_OUT", "SAVE2_OUT") and dumps and f >= g0 - 5 and name[4] not in firsts:
            firsts[name[4]] = bytes(dumps[0][1])
    if orig is not None:
        for p, b in firsts.items():
            if b != orig:
                bad.append("the first saved copy of player %s differs from the stored original" % p)
    last = {p: saved[p] for p in saved}
    nd = sum(a != b for a, b in zip(last.get("1", b""), last.get("2", b""))) if len(last) == 2 else 0
    if len(last) == 2 and nd == 0:
        bad.append("the two players' mazes are identical: the check would be empty")
    return n_save, n_load, bad, nd


def report(path):
    marks, frs = parse(path)
    L = []
    P = L.append
    problems = []
    res, bad = check_title(marks)
    P("Title screen in state 3 (screen RAM $1C00-$1DFF, every frame; the bytes Sub_A6CC writes compared with the ROM tables):")
    for z1a in (0, 1):
        total, n, bad_n, last = res[z1a]
        P("  %s: %d frames logged, %d compared (the first two of a phase skipped), %d with a deviation" % ("one player (zp_1A = 0)" if z1a == 0 else "two players (zp_1A = 1)", total, n, bad_n))
        if last:
            m, b = last
            for name, a, n_ in (("title line 1", 0x1C54 - 0x1C00 - 0, 0), ):
                pass
            P("      screen text of frame %d:" % m[1])
            for a, n_ in ((0x1C54, 1), (0x1C56, 11), (0x1C90, 1), (0x1C92, 11), (0x1C7A, 16), (0x1CF2, 16), (0x1D56, 16), (0x1D05, 17), (0x1D6D, 9)):
                P("        $%04X  %r" % (a, text(b[a - 0x1C00:a - 0x1C00 + n_])))
        if n == 0 or bad_n:
            problems.append("title screen, zp_1A = %d" % z1a)
    for f, z1a, diff in bad:
        P("    deviation f=%d zp_1A=%d: %s" % (f, z1a, ["$%04X got $%02X want $%02X" % d for d in diff]))
    cnt, dev, runs = check_labels(frs)
    P("")
    P("Status-line labels in a two-player game (%d frames, from the game's first frame to its end; \"1UP\" = $11 $35 $30 at $2004, \"2UP\" = $12 $35 $30 at $2021):" % sum(cnt.values()))
    for k, v in sorted(cnt.items()):
        P("  %6d  %s: %s, %s" % ((v,) + k))
    for k in sorted(runs):
        r = runs[k]
        r_in = r[1:-1] or r
        P("  player %d on turn, own label %s: %d stretches, length %d..%d frames (median %d)" % (k[0] + 1, "blank" if k[1] else "shown", len(r), min(r_in), max(r_in), sorted(r_in)[len(r_in) // 2]))
    if dev:
        P("  deviations: %s" % (dev,))
        problems.append("labels")
    # title/state 4 labels
    tt = collections.Counter((f["z19"], f["z1a"], f["l1"], f["l2"]) for f in frs if f["z19"] in (3, 4))
    P("  title frames (z19, zp_1A, label 1, label 2): " + "; ".join("%s: %d" % (k, v) for k, v in sorted(tt.items())))
    ns, nl, badm, nd = check_mazes(marks, frs)
    P("")
    P("Maze copies at the turn switches: %d saves and %d loads checked, the two players' last saved mazes differ in %d bytes; deviations: %d" % (ns, nl, nd, len(badm)))
    for b in badm[:10]:
        P("  " + b)
    if badm:
        problems.append("maze copies")
    P("")
    P("PROBLEMS: " + ("none" if not problems else "; ".join(problems)))
    return L, problems


def main():
    args = list(sys.argv[1:])
    summ = None
    if "--summary-file" in args:
        i = args.index("--summary-file")
        summ = args[i + 1]
        del args[i:i + 2]
    L, problems = report(args[0])
    txt = "\n".join(L)
    print(txt)
    if summ:
        open(summ, "w", encoding="utf-8").write(txt + "\n")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
