"""Step C11, two players: check the log of tools\\altirra_player2.cmd (a real two-player game in Altirra) against what the code says.

The code (docs/19-two-players.md): per-player variables are indexed by CurrentPlayer ($2B): lives $2C/$2D, extra-life flag $2E/$2F, Level $30/$31, power-pellet flags $32/$33,
dots eaten $34+$36 / $35+$37, bonus counter $43/$44, score digits ending at $202F / $204C. zp_1A = 1 means two players; a player's turn ends (the other one starts) when a life is lost
and the other player has lives left.
Checks: (1) every table read logged with `level=` has the level of the player that was playing; (2) a level advance changes the playing player's level by +1 and nothing else's;
(3) between two switches the player who is not playing keeps every variable (lives, level, flags, dots, counters, score digits); (4) switches alternate, only with zp_1A = 1, and only when the
other player has lives; (5) score additions use the playing player's digits; (6) all the table checks of tools/analyze_levels_log.py (expected values from the ROM tables) on the same log.
Usage: python -I tools/analyze_player2_log.py analysis/raw-logs/player2.txt [--summary-file analysis/evidence-two-players-summary.txt]
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_levels_log as AL  # noqa: E402

SNAP = (r"lives=(\d+),(\d+) level=(\d+),(\d+) flags=\$([0-9A-F]+),\$([0-9A-F]+) dots=(\d+),(\d+) eml=(\d+),(\d+) zp43=(\d+),(\d+) "
        r"s1=([0-9A-F]{12}) s2=([0-9A-F]{12}) frame=(\d+)")
RE_SWITCH = re.compile(r"SWITCH to=(\d) from=(\d) 1a=(\d+) " + SNAP)
RE_BOARD = re.compile(r"BOARD_START cur=(\d) " + SNAP)
RE_ADV = re.compile(r"PLAYER_ADVANCE player=(\d) p1=(\d+) p2=(\d+) lives=(\d+),(\d+) frame=(\d+)")
RE_LOST = re.compile(r"LIFE_LOST player=(\d) lives=(\d+),(\d+) frame=(\d+)")
RE_EXTRA = re.compile(r"EXTRA_LIFE player=([0-9]) frame=([0-9]+)")
RE_SCORE = re.compile(r"SCORE_ADD player=(\d) base=\$([0-9A-F]+)")
RE_PLAYER = re.compile(r"^(MOVE_DELAY|FRIGHT_TIME|FRIGHT_END_CHECK|BONUS_APPEARS|BONUS_GLYPHS|BONUS_SCORE|RELEASE_TIMERS|LEVEL_SETUP|ITEM_COLOR) .*?level=([0-9]+) .*?player=([0-9])")


AID_START_LEVELS = (2, 7)     # tools/altirra_player2.cmd sets player 1 := 2 and player 2 := 7 at the start of the game


def snap(m, off):
    g = m.groups()[off:]
    return dict(lives=(int(g[0]), int(g[1])), level=(int(g[2]), int(g[3])), flags=(int(g[4], 16), int(g[5], 16)), dots=(int(g[6]), int(g[7])), eml=(int(g[8]), int(g[9])),
                zp43=(int(g[10]), int(g[11])), score=(g[12], g[13]), frame=int(g[14]))


def inactive_equal(a, b, p):
    """Everything of player p is the same in snapshots a and b."""
    return all(a[k][p] == b[k][p] for k in ("lives", "level", "flags", "dots", "eml", "zp43", "score"))


def main():
    path = sys.argv[1]
    summary = sys.argv[sys.argv.index("--summary-file") + 1] if "--summary-file" in sys.argv else None
    out = []
    P = lambda *a: (out.append(" ".join(str(x) for x in a)), print(*a))
    ev = []
    for line in open(path, errors="replace"):
        line = line.rstrip("\n")
        for kind, rx in (("switch", RE_SWITCH), ("board", RE_BOARD), ("adv", RE_ADV), ("lost", RE_LOST), ("extra", RE_EXTRA), ("score", RE_SCORE)):
            m = rx.search(line)
            if m:
                ev.append((kind, m, line))
                break
        else:
            m = RE_PLAYER.match(line)
            if m:
                ev.append(("table", m, line))
    P("events:", dict(collections.Counter(k for k, _, _ in ev)))
    bad = collections.defaultdict(list)
    cnt = collections.Counter()
    level = [None, None]          # last known level of each player
    active = 0
    last_snap = None
    levels_seen = [set(), set()]
    first_board = True
    extra_done, pending_extra = set(), set()
    setup_phase = True
    for kind, m, line in ev:
        if kind == "board":
            cur = int(m.group(1))
            s = snap(m, 1)
            active = cur
            level = list(s["level"])
            if first_board:       # the aid at $ADFD sets the two start levels right after the first board setup
                level = list(AID_START_LEVELS)
                first_board = False
            last_snap = s
            cnt["board starts (player %d)" % (cur + 1)] += 1
        elif kind == "switch":
            to, frm, f1a = int(m.group(1)), int(m.group(2)), int(m.group(3))
            s = snap(m, 3)
            cnt["switches to player %d" % (to + 1)] += 1
            if f1a != 1:
                bad["switch with zp_1A != 1"].append(line)
            if frm != 1 - to:
                bad["switch not to the other player"].append(line)
            if frm != active:
                bad["switch from a player that was not playing"].append((active, line))
            if s["lives"][to] == 0:
                bad["switch to a player without lives"].append(line)
            if last_snap is not None:
                # the player who was not playing during this turn must be unchanged since the previous snapshot
                if not inactive_equal(last_snap, s, 1 - active):
                    bad["inactive player's variables changed"].append((active, last_snap, s))
                else:
                    cnt["turns where the waiting player's lives, level, flags, dots, counters and score were unchanged"] += 1
                # the playing player must have changed something (score or dots) or the turn is trivial; only count
            for q in list(pending_extra):
                if s["eml"][q] == 1:
                    cnt["extra-life flags that were set for the player who got the life (and no other)"] += int(s["eml"][1 - q] == (1 if (1 - q) in extra_done else 0))
                    pending_extra.discard(q)
                else:
                    bad["extra life without its flag"].append((q, line))
            last_snap = s
            active = to
            level = list(s["level"])
        elif kind == "adv":
            p = int(m.group(1))
            p1, p2 = int(m.group(2)), int(m.group(3))
            cnt["level advances by player %d" % (p + 1)] += 1
            if p != active:
                bad["advance by a player who was not playing"].append(line)
            newl = [p1, p2]
            exp = list(level)
            exp[p] += 1
            if newl != exp:
                bad["level advance changed the wrong counter"].append((level, newl, line))
            else:
                cnt["advances that changed only the playing player's level by +1"] += 1
            level = newl
        elif kind == "lost":
            p = int(m.group(1))
            if p != active:
                bad["life lost by a player who was not playing"].append(line)
            cnt["lives lost by player %d" % (p + 1)] += 1
        elif kind == "extra":
            p = int(m.group(1))
            cnt["extra lives awarded to player %d" % (p + 1)] += 1
            if p != active:
                bad["extra life for a player who was not playing"].append(line)
            if p in extra_done:
                bad["a second extra life for the same player"].append(line)
            extra_done.add(p)
            pending_extra.add(p)
        elif kind == "score":
            p, base = int(m.group(1)), int(m.group(2), 16)
            if base != (0x2F if p == 0 else 0x4C):
                bad["score digits of the wrong player"].append(line)
            cnt["score additions to player %d's digits" % (p + 1)] += 1
        elif kind == "table":
            g = [x for x in m.groups() if x is not None]
            lv, p = int(g[1]), int(g[2])
            cnt["table reads logged for player %d" % (p + 1)] += 1
            levels_seen[p].add(lv)
            if first_board and level[p] is None:
                continue          # before the first board setup is logged
            if setup_phase and level[p] is not None and lv != level[p]:
                cnt["setup reads made before the aid at $ADFD sets the start levels (not checked)"] += 1
                continue
            setup_phase = False
            if level[p] is not None and lv != level[p]:
                bad["table read with another player's level"].append((level, line))
    for k in sorted(cnt):
        P("  %-90s %d" % (k, cnt[k]))
    P("levels (zero-based) the table reads were made with: player 1:", sorted(levels_seen[0]), " player 2:", sorted(levels_seen[1]))
    P("violations:", {k: len(v) for k, v in bad.items()} or "none")
    for k, v in bad.items():
        P("  first", k, v[:2])
    P()
    P("---- the same log through the one-player table checks (expected values from the ROM tables, level = the playing player's) ----")
    for l in AL.main(path):
        P(l)
    if summary:
        with open(summary, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
