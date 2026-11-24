"""Generates tools/altirra_sound_bot2.cmd (OPEN-VERIFICATION.md OV-46): the sound-session harness of altirra_sound_bot.cmd with a STEERING bot that really goes for power pellets, frightened ghosts and the bonus item.
Usage: python -I tools/make_sound_bot2.py        (writes tools/altirra_sound_bot2.cmd)
       NGAMES=n sets the number of games of a session minus one (default 5), LONGPRESS=1 gives games 4 and 5 three OPTION presses, WATCH=1 adds the access watchpoints over the path table (OV-47).
Sessions recorded for OV-46:  C-34: default, 5 games;  C-35: the same bot with the older route;  C-36: NGAMES=12 (11 games, -Seconds 1150);  C-37: LONGPRESS=1 NGAMES=10 (9 games, -Seconds 900).

The bot is a path-finder over the 10x10 junction lattice of the maze (JunctionYList/JunctionXList at $BB83/$BB8D; the edges come from the decoded maze and are checked against all 16 patrol routes).
The inside of the ghost house (lattice points (4,4) and (4,5)) is left out.  At every frame, when Pac-Man stands exactly on a lattice point, the bot writes the STICK0 shadow ($0278) with the first step of the shortest
path to its target.  The target is, in this order:  1 the lattice point of the first frightened ghost (bit 7 of the ghost state $CE..$D1; its y is read from $85..$88, its x from $8A..$8D);
2 the bonus item while it is on screen (zp_9F = 1): the bot walks back and forth between the junctions (5,4) and (5,5), the item (x 124, y 132) lies between them;  3 the next of the pellet route (7,0) (1,0) (0,0) (1,9) (0,9) (7,9), which passes the four power pellets.
Only game memory is READ.  The path table (100 targets x 100 lattice cells, one STICK0 value per entry, at $5000-$76FF) is written by the harness into RAM that the game does not touch (OPEN-VERIFICATION.md OV-47 / C-39: WATCH=1 logs every CPU access; none comes from the game or from the OS after the boot).
"""
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402
import describe_patrol_routes as D  # noqa: E402

BASE = 0x5000
LONGPRESS = bool(os.environ.get('LONGPRESS'))     # games 4 and 5 get 3 OPTION presses instead of 1 (the schedule of the 10-game session C-37)
NGAMES = int(os.environ.get('NGAMES', '5'))      # games per session (default 5)
STICK = {1: 0x0E, 2: 0x0D, 4: 0x0B, 8: 0x07}          # up, down, left, right (active low)
XS = [S.rd(0xBB8D + i) for i in range(10)]
YS = [S.rd(0xBB83 + i) for i in range(10)]
maze = S.decode_a(0xA1E1)[0]
ok = lambda r, c: maze[r * 40 + c] in (0, 1, 2)
R, C = D.ROWS, D.COLS
HOUSE = {(4, 4), (4, 5)}      # the inside of the ghost house; the ring around it (lattice rows 3 and 5, columns 3-6) is open to Pac-Man through the tunnel row, and the bonus item lies on its lower side
edges = {}
for i in range(10):
    for j in range(10):
        e = 0
        if i > 0 and all(ok(r, C[j]) for r in range(R[i - 1], R[i] + 1)): e |= 1
        if i < 9 and all(ok(r, C[j]) for r in range(R[i], R[i + 1] + 1)): e |= 2
        if j > 0 and all(ok(R[i], c) for c in range(C[j - 1], C[j] + 1)): e |= 4
        if j < 9 and all(ok(R[i], c) for c in range(C[j], C[j + 1] + 1)): e |= 8
        edges[i, j] = e
for rt in D.routes():                                  # every patrol step must be an edge of the graph
    for a, d in zip(rt[3], rt[2]):
        assert edges[a] & d
MOVE = {1: (-1, 0), 2: (1, 0), 4: (0, -1), 8: (0, 1)}
nodes = [(i, j) for i in range(10) for j in range(10) if (i, j) not in HOUSE and edges[i, j]]


def nbrs(n):
    for d, (di, dj) in MOVE.items():
        m = (n[0] + di, n[1] + dj)
        if edges[n] & d and m in nodes:
            yield d, m


table = bytearray(10000)
for t in nodes:                                        # BFS from the target; the step from a node is the direction towards the node it was reached from
    dist, q = {t: 0}, deque([t])
    while q:
        n = q.popleft()
        for d, m in nbrs(n):
            if m not in dist:
                dist[m] = dist[n] + 1
                q.append(m)
                back = {1: 2, 2: 1, 4: 8, 8: 4}[d]    # from m, go in the direction opposite to d
                table[(t[0] * 10 + t[1]) * 100 + m[0] * 10 + m[1]] = STICK[back]
# the dot route: a closed walk over the junction graph that covers every corridor (and so every dot and the four power pellets, two of which lie on the edges (1,0)-(0,0) and (1,9)-(0,9));
# built greedily: walk to the nearest corridor not yet covered, cross it, repeat; then return to the start.  The bot visits the points of the walk one after the other (a point counts as reached
# when Pac-Man stands on it); after a death or a chase it simply goes on with the next point.
def shortest(a, b):
    prev, q = {a: None}, deque([a])
    while q:
        n = q.popleft()
        if n == b:
            break
        for d, m in nbrs(n):
            if m not in prev:
                prev[m] = n
                q.append(m)
    path, n = [], b
    while n is not None:
        path.append(n)
        n = prev[n]
    return path[::-1]


comp, q = {(7, 5)}, deque([(7, 5)])          # only the part of the graph Pac-Man can reach from his start
while q:
    n = q.popleft()
    for d, m in nbrs(n):
        if m not in comp:
            comp.add(m)
            q.append(m)
print("unreachable lattice points:", sorted(set(nodes) - comp))
todo = {frozenset((n, m)) for n in comp for d, m in nbrs(n)}
cur = (7, 5)
walk = [cur]


def step(a, b):
    walk.append(b)
    todo.discard(frozenset((a, b)))


while todo:
    best = None
    for e in todo:
        for a in e:
            pth = shortest(cur, a)
            if best is None or len(pth) < len(best[0]):
                best = (pth, a, next(iter(e - {a})))
    pth, a, b = best
    for x, y in zip(pth, pth[1:]):
        step(x, y)
    step(a, b)
    cur = b
for x, y in zip(shortest(cur, (7, 5)), shortest(cur, (7, 5))[1:]):
    step(x, y)
WALK = [n[0] * 10 + n[1] for n in walk[1:]]
for k in WALK:
    assert (k // 10, k % 10) in nodes
if os.environ.get("TUNNELWALK"):                    # OV-31: Pac-Man only keeps going to the tunnel mouth (4,0): at the target the bot holds its last direction (left), so he runs into the tunnel and out at the right side
    WALK = [40]
OV59 = os.environ.get("OV59", "")                    # OV-59 (stage 53 coverage): "row6" = Pac-Man walks back and forth between the junctions (2,3) and (2,4), the corridor above the ghost house, so that he steps right across the
                                                     # page boundary of MazePtr ($0CFF -> $0D00); "tunnel" = he runs into the tunnel (target (4,0)) and, standing at x = $CA after the wrap, is pushed right (see below)
if OV59 == "row6":
    WALK = [23, 24]
elif OV59 in ("tunnel", "tunnel_control"):
    WALK = [40]                                      # "tunnel_control" = the same session without the pushed RIGHT: the control of the proof in docs/32 (tools/analyze_ov59_tunnel.py)
NW = len(WALK)
for k in (54, 55):
    assert (k // 10, k % 10) in nodes
XM = [(XS[i] + XS[i + 1]) // 2 for i in range(9)]
YM = [(YS[i] + YS[i + 1]) // 2 for i in range(9)]
px, py = "db($8e)", "db($89)"
colx = "+".join("(%s=%d)*%d" % (px, XS[i], i + 1) for i in range(10))
rowy = "+".join("(%s=%d)*%d" % (py, YS[i], i + 1) for i in range(10))
fr = ["((db($%02x)&$80)>0)" % (0xCE + g) for g in range(4)]
sel = ["%s" % fr[0], "(1-%s)*%s" % (fr[0], fr[1]), "(1-%s)*(1-%s)*%s" % (fr[0], fr[1], fr[2]), "(1-%s)*(1-%s)*(1-%s)*%s" % (fr[0], fr[1], fr[2], fr[3])]
anyf = "((%s)>0)" % "+".join(fr)
gx = "(" + "+".join("%s*db($%02x)" % (sel[g], 0x8A + g) for g in range(4)) + ")"
gy = "(" + "+".join("%s*db($%02x)" % (sel[g], 0x85 + g) for g in range(4)) + ")"
gcol = "(" + "+".join("(%s>=%d)" % (gx, m) for m in XM) + ")"
grow = "(" + "+".join("(%s>=%d)" % (gy, m) for m in YM) + ")"
FLEE = bool(os.environ.get("FLEE"))      # OV-49: a ghost that is not frightened and within 40 pixels makes the bot head for the lattice point opposite the ghost's (9-row, 9-col)
dg = ["(((db($%02x)&$80)=0)*((db($%02x)-%s)*(db($%02x)-%s)+(db($%02x)-%s)*(db($%02x)-%s)<=1600))" % (0xCE+g, 0x8A+g, px, 0x8A+g, px, 0x85+g, py, 0x85+g, py) for g in range(4)]
dsel = [dg[0], "(1-%s)*%s" % (dg[0], dg[1]), "(1-%s)*(1-%s)*%s" % (dg[0], dg[1], dg[2]), "(1-%s)*(1-%s)*(1-%s)*%s" % (dg[0], dg[1], dg[2], dg[3])]
anyd = "((%s)>0)" % "+".join(dg)
hx = "(" + "+".join("%s*db($%02x)" % (dsel[g], 0x8A + g) for g in range(4)) + ")"
hy = "(" + "+".join("%s*db($%02x)" % (dsel[g], 0x85 + g) for g in range(4)) + ")"
hcol = "(" + "+".join("(%s>=%d)" % (hx, m) for m in XM) + ")"
hrow = "(" + "+".join("(%s>=%d)" % (hy, m) for m in YM) + ")"
routek = "(" + "+".join("(@t4=%d)*%d" % (s, k) for s, k in enumerate(WALK)) + ")"
L = []
A = L.append
A(chr(10).join("# " + x for x in __doc__.strip().split(chr(10))))
A("# NOTHING in the game is written (no pokes, no invulnerability, no PC move, no life refill); the injected values are only what the game READS: STICK0 (the bot above) and CONSOL (START 6, SELECT 5, OPTION 3).")
A("# Schedule (g = games started): g=0 START at title frame 120-170 -> game 1 one player level 0;  g=1 at the title OPTION x3, SELECT, START -> game 2 two players level 4;  g=2 OPTION x2, SELECT, START -> game 3 one player level 8;  g=3 OPTION x3, START -> game 4 one player level 0;  g=4 OPTION x3, START -> game 5 one player level 4.")
A("# Run:  powershell -NoProfile -ExecutionPolicy Bypass -File tools/record_tune.ps1 -Cmd altirra_sound_bot2.cmd -Trace analysis/raw-logs/sound-bot2.txt -Out analysis/sound-bot2-recorded.wav -Seconds 1500")
A("# then  python -I tools/analyze_sound_events.py analysis/raw-logs/sound-bot2.txt   python -I tools/analyze_tail_sound.py analysis/sound-bot2-recorded.wav analysis/raw-logs/sound-bot2.txt   python -I tools/analyze_full_waveform.py analysis/sound-bot2-recorded.wav analysis/raw-logs/sound-bot2.txt")
src = open(os.path.join(HERE, "altirra_sound_bot.cmd"), encoding="utf-8").read().split("\n")
# the title schedule: g=1 -> 3 OPTION presses (start level 4, two players), g=2 -> 2 more (start level 8, one player)
# keep the schedule, the trace and the events of altirra_sound_bot.cmd; replace its random STICK0 line and the scripted levels
for l in src:
    if l.startswith("bp -n a82f \"eb $278"):
        continue
    if l.startswith("#"):
        continue
    l = l.replace('(@t1<=327)', '(@t1<=187)').replace('(@t1<=247)', '(@t1<=107)')
    if l.startswith('bp -n a5fd "r @t3'):      # more one-player games: g=3 and g=4 with 3 OPTION presses, g=5..NGAMES-1 with 1 press each, then START
        extra = ''.join('+((@t7=%d)&(db($19)>=3)&(@t1>=60)&(@t1<=%d)&(((@t1-60)%%40)<8))*4+((@t7=%d)&(db($19)>=3)&(@t1>=400)&(@t1<=450))*1' % (g, 187 if (LONGPRESS and g < 5) else 67, g) for g in range(3, NGAMES - 1))
        l = l[:-1] + extra + '"'
    L.append(l)
A("r @t2 $0B")
A("r @t4 0")
A("r @t6 255")
# the path table into RAM (every NEWGAME; idempotent)
for off in range(0, 10000, 56):
    A('bp -n a537 "eb %04x %s"' % (BASE + off, " ".join("%02x" % b for b in table[off:off + 56])))
A('bt a537 "TABLE_CHECK f=%d t0=%d t1=%d t2=%d" @frame db($5000+69*100+70) db($5000+0*100+5) db($5000+79*100+0)')
A('bp -n a82f "r @t8 %s; r @t9 %s; r @t6 ((@t8>0)*(@t9>0))*((@t9-1)*10+@t8-1)+(1-(@t8>0)*(@t9>0))*255"' % (colx, rowy))
A('bp -n a82f "r @t4 (@t4+(@t6=%s))%%%d"' % (routek, NW))
A('bp -n a82f "r @t9 %s*(%s*10+%s)+(1-%s)*((db($9f)=1)*(54+(@t6=54))+(1-(db($9f)=1))*%s)"' % (anyf, grow, gcol, anyf, routek))
if FLEE:
    A('bp -n a82f "r @t9 %s*(9-%s)*10+%s*(9-%s)+(1-%s)*@t9"' % (anyd, hrow, anyd, hcol, anyd))
A('bp -n a82f "r @t5 db($5000+@t9*100+@t6)*(@t6<100)"')
A('bp -n a82f "r @t2 (@t5>0)*@t5+(@t5=0)*@t2"')
A('bp -n a800 "r @t2 $0B"')                 # at every start of play (a new board or a new life) Pac-Man begins by walking left
A('bp -n a82f "eb $278 @t2"')
if OV59:
    A('bt b179 "MOVE f=%d px=%d py=%d dir=%d z80=%02X%02X" @frame db($8e) db($89) db($93) db($81) db($80)')
    A('bt b267 "PAGE_CROSS_RIGHT f=%d px=%d py=%d z80=%02X%02X" @frame db($8e) db($89) db($81) db($80)')
    A('bt b249 "RIGHT_WRAP_IN_MOVE f=%d px=%d py=%d dir=%d" @frame db($8e) db($89) db($93)')
    A('bt b27b "LEFT_WRAP_IN_MOVE f=%d px=%d py=%d dir=%d" @frame db($8e) db($89) db($93)')
    A('bt ab89 "CLIP_WRAP_RIGHT_TO_LEFT f=%d ent=%d" @frame x')
    A('bt abb1 "CLIP_WRAP_LEFT_TO_RIGHT f=%d ent=%d" @frame x')
    A('bt b1a4 "STICK_READ f=%d px=%d dir=%d stick=$%02X" @frame db($8e) db($93) @a')
    A('bt a923 "DEATH f=%d" @frame')
if OV59 == "tunnel":
    # TEST AID (input only): at the one instant the game is about to read STICK0 inside MovePacMan with Pac-Man standing at x = $CA (the clip has just wrapped him in from the left exit), the joystick shadow is RIGHT ($07)
    A('bp -n b19f "eb $278 (db($8e)=$ca)*$07+(1-(db($8e)=$ca))*db($278)"')
if os.environ.get("WATCH"):                          # OV-47: every CPU write to and read from the path table's RAM ($5000-$76FF) is logged with the program counter
    A('bta w 5000 L2710 "TBLW a=$%04X v=$%02X pc=$%04X f=%d" @address @value pc @frame')
    A('bta r 5000 L2710 "TBLR a=$%04X pc=$%04X f=%d" @address pc @frame')
if os.environ.get("BOTDEBUG"):
    A('bt a82f "BOT f=%d px=%d py=%d k=%d tc=%d held=$%02X rt=%d" @frame db($8e) db($89) @t6 @t9 @t2 @t4')
OUTNAME = "altirra_sound_bot2.cmd"
if OV59:
    OUTNAME = "altirra_ov59_%s.cmd" % OV59
if os.environ.get("TUNNELTRACE"):                    # OV-31: the same bot session with a trace of the tunnel-edge clipping of the game's own entities (tools/analyze_tunnel_clip.py); written to altirra_tunnel_bot.cmd
    A('bt ab57 "ENTER x=%d X=%d Y=%d dir=%d k=0 f=%d" x db($8a+x) db($85+x) db($8f+x) @frame')
    A('bt abc8 "LEAVE x=%d X=%d dir=%d mask=$%02X ptr=$%02X%02X z80=$%02X b0=$%02X b7=$%02X b15=$%02X f=%d" x db($8a+x) db($8f+x) db($fe) db($48) db($47) db($80) db(dw($47)+0) db(dw($47)+7) db(dw($47)+15) @frame')
    OUTNAME = "altirra_tunnel_bot.cmd"
out = "\n".join(L) + "\n"
open(os.path.join(HERE, OUTNAME), "w", encoding="utf-8").write(out)
print("walk of %d points;" % NW, "wrote", len(out), "bytes;", len(nodes), "nodes;", sum(1 for b in table if b), "table entries")
