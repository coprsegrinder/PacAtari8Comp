"""Analyses a trace of the FPS option (`pacman_a8_play --windowed --selftest 1300 --fps 180 --trace FILE`, docs/69): the rhythm of the pictures (interval, spread, the longest wait), the game time per picture (it must run at 59.92 frames a second and never go back), and the unevenness of the speed of the ghosts and Pac-Man (spread / mean of the step between pictures over 0.2 s stretches of steady movement) in the game's own steps and as drawn.
Usage: python -I tools/analyze_trace.py FILE"""
import sys, math
rows = [list(map(float, l.split())) for l in open(sys.argv[1])]
t = [r[0] for r in rows]; tau = [r[1] for r in rows]
dts = [t[i+1]-t[i] for i in range(len(t)-1)]
m = sum(dts)/len(dts); sd = math.sqrt(sum((d-m)**2 for d in dts)/len(dts))
print("ticks %d, mean interval %.3f ms (%.1f /s), spread %.3f ms, worst %.2f ms, over 8 ms: %d" % (len(rows), m, 1000/m, sd, max(dts), sum(1 for d in dts if d > 8)))
# the game time per tick: it must run at 59.92 frames/s smoothly
rate = [(tau[i+1]-tau[i])/(dts[i]/1000.0) for i in range(len(dts)) if dts[i] > 0]
span = (tau[-1]-tau[0])/((t[-1]-t[0])/1000.0)
print("game time: %.3f frames/s over the run (the original: 59.923); per-tick increments %.4f frames +- %.4f" % (span, sum(tau[i+1]-tau[i] for i in range(len(tau)-1))/len(dts), math.sqrt(sum(((tau[i+1]-tau[i]) - m/1000*59.9227)**2 for i in range(len(dts)))/len(dts))))
back = sum(1 for i in range(len(tau)-1) if tau[i+1] < tau[i])
print("ticks where the game time went back: %d" % back)
def metric(pos, label, lo=450.0, hi=1250.0):
    # unevenness of the speed on stretches of 36 ticks (0.2 s) where the object moves steadily (>= 3 steps)
    tot = 0; n = 0
    idx = [i for i in range(len(rows)) if lo <= tau[i] <= hi]
    for a in range(0, len(idx) - 36, 36):
        seg = idx[a:a+37]
        pts = [pos(i) for i in seg]
        if any(p[0] < 0 for p in pts): continue
        v = [math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(36)]
        mean = sum(v)/36
        if mean < 0.03: continue
        sdv = math.sqrt(sum((q-mean)**2 for q in v)/36)
        tot += sdv/mean; n += 1
    return tot/n if n else float('nan'), n
for k, name in enumerate(["ghost 0", "ghost 1", "ghost 2", "ghost 3", "Pac-Man"]):
    drawn = lambda i, k=k: (rows[i][3+4*k], rows[i][4+4*k])
    held = lambda i, k=k: (rows[i][5+4*k], rows[i][6+4*k])
    a, n1 = metric(drawn, name); b, n2 = metric(held, name)
    print("  %-8s speed unevenness (spread/mean, 0.2 s stretches of steady movement): the game's own steps %.2f -> in-between pictures %.2f   (%d stretches)" % (name, b, a, n1))
