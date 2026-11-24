"""OV-69: the drawing routines in port form (tools/core_draw.py) against the ROM routines on the concrete 6502.  Random game states (tools/check_ghost.py's: entities on the lattice and off it, ghosts in every state, both leg
phases); each routine is run in the ROM and in the port from the same state; compared: the zero page (except the declared temporaries), the player-missile pages, the eight position registers and the picture buffers.
  step_and_draw_entity StepAndDrawEntity $B902 (A = a direction: the four, none, a mixed value; DrawOnly set and clear)
  draw_pacman          MovePacMan $B2E9 (Y = a picture index, A = a mouth frame offset)
  draw_all_in_place    DrawAllInPlace $AD49
  death_animation      DeathAnimation $AEF7 (every frame, every delay)  [counters and pictures]
  clip                 ClipEntitiesOnTunnelRow $AB48 and ClipEntityAtTunnel $AB57 (entities on the tunnel row at every X)
  clear                ClearPlayerMemory $B0F1, FillPlayerPages $B100
Usage: python -I tools/check_draw.py [--write analysis/evidence-draw-summary.txt] [--quick]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import algorithm_models as A  # noqa: E402
import check_ghost as CG  # noqa: E402
import core_draw as D  # noqa: E402
import core_sound as SO  # noqa: E402
import core_world as W  # noqa: E402

ROOT = A.ROOT


def scene_noise(m, rng):
    """the pages hold random pictures, the buffers random rows, the position registers random values (a drawing must leave exactly the same as the ROM from any earlier scene)"""
    for a in range(0x2300, 0x2800):
        m.mem[a] = rng.choice([0, 0, 0, rng.randrange(256)])
    for a in range(0x0400, 0x0420):
        m.mem[a] = rng.choice([0, rng.randrange(256)])
    for a in range(0xD000, 0xD008):
        m.mem[a] = rng.randrange(256)


def pre_common(m, rng):
    CG.setup(m, rng)
    scene_noise(m, rng)
    m.mem[0xAF] = rng.choice([0, 1])                      # LegPhase
    for g in range(4):
        m.mem[0xCE + g] = rng.choice(CG.STATES)
    for g in range(5):
        if rng.random() < 0.2:
            m.mem[0x85 + g] = rng.choice([0x74, 0x74, 0x73, 0x75])
        if rng.random() < 0.3:
            m.mem[0x8A + g] = rng.choice([0x2A, 0x2B, 0x29, 0x39, 0x38, 0xC0, 0xC1, 0xCA, 0xCB, 0xC9, 0x00, 0xFF, rng.randrange(256)])


def run(name, rom_call, port, n, seed, pre=None, tweak=None):
    base = A.started_machine()
    rng = random.Random(seed)
    bad = []
    for _ in range(n):
        m = A.fresh(base)
        pre_common(m, rng)
        if pre:
            pre(m, rng)
        w = W.World().load(m.mem)
        args = tweak(m, w, rng) if tweak else None
        # the entity rows are bounded so that a picture stays in the pages (the game never draws past $27FF)
        port(w, args)
        rom_call(m, args)
        d = CG.world_diff(m, w, None)
        if d:
            bad.append((args, d[:4]))
    return n, bad


# ---- the checks
def t_step(m, w, rng):
    x = rng.randrange(4)
    d = rng.choice([1, 2, 4, 8, 1, 2, 4, 8, 0, 3, 5, 0x0C, 0xFF])
    do = rng.choice([0, 0, 1])
    m.mem[0xAE] = do
    w.DrawOnly = do
    for k in (0x85 + x,):
        m.mem[k] = rng.choice([m.mem[k], rng.randrange(0xE0), 0x74])
    w.EntityY = list(m.mem[0x85:0x8A])
    return x, d


def t_pac(m, w, rng):
    y = rng.choice([0, 2, 4, 6, 8])
    a = rng.choice([0, 0x0A, 0, 0x0A, 1])
    m.mem[0x89] = rng.randrange(0xE0)
    w.EntityY = list(m.mem[0x85:0x8A])
    return y, a


def t_all(m, w, rng):
    for g in range(5):
        m.mem[0x85 + g] = rng.randrange(0xE0)
    w.EntityY = list(m.mem[0x85:0x8A])
    return None


def t_death(m, w, rng):
    m.mem[0xEA] = rng.choice([1, 1, 1, 0])
    m.mem[0xEB] = rng.choice([0, 1, 2, 5, 13, 14, 15, 15, rng.randrange(16)])
    m.mem[0xEC] = rng.choice([0, 1, 2, 7, 8, 0x80, rng.randrange(256)])
    m.mem[0x89] = rng.randrange(0xE0)
    w.DeathAnimActive, w.DeathAnimFrame, w.DeathAnimDelay = m.mem[0xEA], m.mem[0xEB], m.mem[0xEC]
    w.EntityY = list(m.mem[0x85:0x8A])
    return None


def t_clip(m, w, rng):
    for g in range(5):
        if rng.random() < 0.6:
            m.mem[0x85 + g] = 0x74
        m.mem[0x8F + g] = rng.choice([1, 2, 4, 8, 4, 8, 4, 8])
    w.EntityY, w.EntityDir = list(m.mem[0x85:0x8A]), list(m.mem[0x8F:0x94])
    w.EntityX = list(m.mem[0x8A:0x8F])
    return None


def t_clear(m, w, rng):
    return None


def report(quick=False):
    N = 800 if quick else 4000
    rows = [
        ("step_and_draw_entity", "StepAndDrawEntity $B902 (the four directions, none, mixed values; DrawOnly set and clear; every ghost state, both leg phases)",
         lambda m, a: m.call(0xB902, a=a[1], x=a[0]), lambda w, a: D.step_and_draw_entity(w, a[0], a[1]), None, t_step),
        ("draw_pacman", "MovePacMan $B2E9 (the five pictures, the mouth frame offsets)",
         lambda m, a: m.call(0xB2E9, a=a[1], y=a[0]), lambda w, a: D.draw_pacman(w, a[0], a[1]), None, t_pac),
        ("draw_all_in_place", "DrawAllInPlace $AD49 (the four ghosts, then the full disc: its jump into MovePacMan runs to the end of the draw)",
         lambda m, a: m.call(0xAD49), lambda w, a: D.draw_all_in_place(w), None, t_all),
        ("death_animation", "DeathAnimation $AEF7 (counters and pictures; every frame, every delay, the last step clears)",
         lambda m, a: m.call(0xAEF7), lambda w, a: SO.death_animation(w), None, t_death),
        ("clip_entities_on_tunnel_row", "ClipEntitiesOnTunnelRow $AB48 (entities on the tunnel row at every X, both directions: the masks, the wrap, Pac-Man's maze pointer)",
         lambda m, a: m.call(0xAB48), lambda w, a: D.clip_entities_on_tunnel_row(w), None, t_clip),
        ("clear_player_memory", "ClearPlayerMemory $B0F1 (all five pages to 0, rows $F0-$FF to $FE)",
         lambda m, a: m.call(0xB0F1), lambda w, a: D.clear_player_memory(w), None, t_clear),
    ]
    L = ["The drawing routines in port form (tools/core_draw.py) against the ROM routines (tools/check_draw.py, OV-69): zero page (except the scratch), the player-missile pages, the eight positions and the picture buffers compared", ""]
    res = []
    for name, what, rc, pt, pre, tw in rows:
        n, bad = run(name, rc, pt, N, 69, pre, tw)
        res.append(bad)
        L.append("%s: %s: %d calls: %d differences" % (name, what, n, len(bad)))
        for b in bad[:3]:
            L.append("  %s" % (b,))
    return L, res


def main():
    L, res = report("--quick" in sys.argv)
    txt = "\n".join(L) + "\n"
    if "--write" in sys.argv:
        with open(os.path.join(ROOT, sys.argv[sys.argv.index("--write") + 1]), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
    print(txt)
    return 1 if any(res) else 0


if __name__ == "__main__":
    sys.exit(main())
