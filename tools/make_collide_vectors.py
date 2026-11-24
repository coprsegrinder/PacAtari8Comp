"""Stage 77a (docs/51 section 3, docs/50): writes the collision-scene vector sets of the C port into resources/vectors/ from the Altirra logs of the collision audit (analysis/raw-logs/collide-s*.txt,
collideplay-*.txt: derived data, git-ignored) and from the vectors of the play frame:
  gtia.scenes   the 73,111 random scenes of the six runs: the scene and the sixteen registers the REAL GTIA gave (tools/analyze_collide.py compares the Python model with them: 0 differences)
  gtia.play     the 27,193 frames of the real game in play: the scene on the screen, the latch carried as the analysis carries it, and the registers the game read
  gtia.worlds   the scenes the port's own drawing leaves (the after-states of core_play.vbi_play_frame.vec): the registers of the PYTHON model with the platform latch (not the hardware: there is no hardware log of those)
  gtia.charset.bin   the 1,024 bytes of the game's character set (the C needs one to read the maze cells from a World)
Usage: python -I tools/make_collide_vectors.py [--out DIR] [--limit N]    (N scenes / frames per log, for the tests)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_collide as AC  # noqa: E402
import core_draw as D  # noqa: E402
import gtia_collisions as G  # noqa: E402
import vecfmt as V  # noqa: E402

ROOT = AC.ROOT
M = AC.M


def pages_of(mp, pp):
    return [list(mp)] + [list(p) for p in pp]


def pad_cells(cells):
    return list(cells) + [0] * (V.SCENE_CELLS - len(cells))


def scenes(out, logs, limit=None):
    """the random scenes: the same selection as analyze_collide.analyse"""
    w = None
    n = 0
    for path in logs:
        mem, recs = AC.parse(path)
        pf = AC.playfield_of(mem)
        if w is None:
            w = V.SceneWriter(os.path.join(out, "gtia.scenes.vec"), "gtia.scenes", pf.charset, pf.cells)
        mode = M.MODES.get(AC.run_of(path), 0)
        sc = AC.stub_scenes(AC.seed_of(path), max([r["count"] for r in recs] + [0]), mode)
        by_count = {r["count"]: r for r in recs if r["valid"] or r["count"] > 1}
        bad_int = {r["count"] for r in recs if sc.get(r["count"]) != r["scene"]}
        k = 0
        for r in recs:
            c = r["count"]
            if c < 3 or (c - 1) not in by_count or c - 1 in bad_int or c in bad_int:
                continue
            hpos, rows, pats = AC.scene_of(by_count[c - 1]["scene"])
            mp, pp = G.scene_pages(rows, pats)
            idx = list(range(16))
            if mode & 4:
                idx = (list(range(8, 16)) if min(rows) >= 32 else []) + (list(range(8)) if all(40 <= r_ and r_ + 15 <= 223 for r_ in rows) else [])
                if not idx:
                    continue
            mask = sum(1 << i for i in idx)
            w.scene(V.MODE_ALONE, mask, pf.cells, hpos, pages_of(mp, pp), r["regs"])
            n += 1
            k += 1
            if limit and k >= limit:
                break
    w.close()
    return n


def play(out, logs, limit=None):
    """the frames of the real game: the chain of analyze_collide.analyse_play (a reset after a HITCLR, a carry, a latch taken from the file after a frame the handler overran into)"""
    cs = AC.rom_charset()
    w = None
    n = 0
    for path in logs:
        frames = AC.parse_play(path)
        if limit:
            frames = frames[:limit]
        if w is None:
            w = V.SceneWriter(os.path.join(out, "gtia.play.vec"), "gtia.play", cs, pad_cells(frames[0]["cells"]))
        prev = None                                                 # the chain's latch as the analysis keeps it (the model's), or the hardware's after a late frame
        prev_is_file = False
        for i, f in enumerate(frames):
            if f["gractl"] & 3 != 3:
                prev = None
                continue
            pf = G.Playfield(f["cells"], cs)
            shown = G.collision_registers(f["hpos"], f["pages"][0], f["pages"][1:], pf)
            if i > 0 and frames[i - 1]["hc"]:
                mode, want, lat = V.MODE_RESET, shown, None
            elif prev is not None:
                want = [a | b for a, b in zip(prev, shown)]
                mode, lat = (V.MODE_SET, prev) if prev_is_file else (V.MODE_CARRY, None)
            else:
                prev = None
                continue
            late = i > 0 and AC.overran(frames[i - 1])
            got = f["regs"]
            w.scene(mode, 0 if late else 0xFFFF, pad_cells(f["cells"]), f["hpos"], f["pages"], got, lat)
            n += 1
            if late or want != got:
                prev, prev_is_file = list(got), True
            else:
                prev, prev_is_file = want, False
    w.close()
    return n


def worlds(out, vec_path, cs, limit=None):
    """the scenes of the port's own frames: for each run of consecutive frames of core_play.vbi_play_frame.vec the latch of platform_iface.GtiaCollisions after every frame"""
    recs = V.read_set(vec_path)[3]
    base = V.unpack_state(recs[0]["before"])
    w = V.SceneWriter(os.path.join(out, "gtia.worlds.vec"), "gtia.worlds", cs, base.maze[:V.SCENE_CELLS])
    latch = [0] * 16
    prev_after = None
    n = 0
    for k, rec in enumerate(recs):
        if limit and k >= limit:
            break
        chained = False
        if prev_after is not None:
            e = bytearray(prev_after)
            e[0x14] = (e[0x14] + 1) & 0xFF
            chained = bytes(e) == rec["before"]
        prev_after = rec["after"]
        wd = V.unpack_state(rec["after"])
        hitclr = any(a == 0xD01E for a, v in rec["pokey"])
        hpos, mpage, ppages, pf = D.scene(wd, cs)
        shown = G.collision_registers(hpos, mpage, ppages, pf)
        if hitclr or not chained:
            latch = [0] * 16
            mode = V.MODE_RESET
        else:
            mode = V.MODE_CARRY
        latch = [a | b for a, b in zip(latch, shown)]
        w.scene(mode, 0xFFFF, wd.maze[:V.SCENE_CELLS], hpos, pages_of(mpage, ppages), latch)
        n += 1
    w.close()
    return n


def main():
    out = os.path.join(ROOT, "resources", "vectors")
    if "--out" in sys.argv:
        out = os.path.join(ROOT, sys.argv[sys.argv.index("--out") + 1])
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    os.makedirs(out, exist_ok=True)
    raw = os.path.join(ROOT, "analysis", "raw-logs")
    cs = AC.rom_charset()
    with open(os.path.join(out, "gtia.charset.bin"), "wb") as fh:
        fh.write(cs)
    n1 = scenes(out, sorted(os.path.join(raw, f) for f in os.listdir(raw) if f.startswith("collide-s") and f.endswith(".txt")), limit)
    n2 = play(out, sorted(os.path.join(raw, f) for f in os.listdir(raw) if f.startswith("collideplay-") and f.endswith(".txt")), limit)
    vp = os.path.join(out, "core_play.vbi_play_frame.vec")
    n3 = worlds(out, vp, cs, limit) if os.path.exists(vp) else 0
    print("gtia.scenes %d, gtia.play %d, gtia.worlds %d" % (n1, n2, n3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
