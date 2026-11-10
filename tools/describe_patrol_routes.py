"""List the 16 patrol routes (start junction, steps, junction path) and optionally draw them over the maze (step C11).
Usage: python -I tools/describe_patrol_routes.py [--image out.png]      (the image needs Pillow; it shows game graphics, so it is not committed)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import decode_streams as S  # noqa: E402

NIB, _ = S.split_nibbles(0xBE95)
R = lambda a: NIB[a - 0x600]
YS = [S.rd(0xBB83 + i) for i in range(10)]
XS = [S.rd(0xBB8D + i) for i in range(10)]
ROWS = [(y - 36) // 8 for y in YS]
COLS = [(x - 46) // 4 for x in XS]
OFFS = [S.rd(0xBD16 + i) for i in range(16)]
DIRS = {1: (-1, 0), 2: (1, 0), 4: (0, -1), 8: (0, 1)}
NAME = {1: "U", 2: "D", 4: "L", 8: "R"}


def routes():
    out = []
    for i in range(16):
        x, y = S.rd(0xBCEE + 2 * i), S.rd(0xBCEE + 2 * i + 1)
        start = (YS.index(y), XS.index(x))
        steps, o = [], OFFS[i]
        while R(0x6AE + o + len(steps)):
            steps.append(R(0x6AE + o + len(steps)))
        path, (r, c) = [start], start
        for d in steps:
            r, c = r + DIRS[d][0], c + DIRS[d][1]
            path.append((r, c))
        out.append((i, start, steps, path))
    return out


def draw(path_out):
    from PIL import Image, ImageDraw
    maze = S.decode_a(0xA1E1)[0]
    cs = 12
    tiles = []
    for k, (i, start, steps, path) in enumerate(routes()):
        im = Image.new("RGB", (40 * cs, 23 * cs), (0, 0, 0))
        d = ImageDraw.Draw(im)
        for r in range(23):
            for c in range(40):
                v = maze[r * 40 + c]
                if v in (1, 2):
                    d.rectangle((c * cs + 4, r * cs + 4, c * cs + 7, r * cs + 7), fill=(90, 90, 90))
                elif v not in (0,):
                    d.rectangle((c * cs, r * cs, c * cs + cs - 1, r * cs + cs - 1), fill=(30, 40, 110))
        pts = [(COLS[c] * cs + cs // 2, ROWS[r] * cs + cs // 2) for r, c in path]
        d.line(pts, fill=(255, 200, 0), width=3)
        sx, sy = pts[0]
        d.ellipse((sx - 6, sy - 6, sx + 6, sy + 6), outline=(0, 255, 0), width=3)
        d.text((4, 4), "route %d  (%d steps)" % (i, len(steps)), fill=(255, 255, 255))
        tiles.append(im)
    W, H = tiles[0].size
    M = Image.new("RGB", (4 * W + 15, 4 * H + 15), (60, 60, 60))
    for k, t in enumerate(tiles):
        M.paste(t, ((k % 4) * (W + 5), (k // 4) * (H + 5)))
    M.save(path_out)


if __name__ == "__main__":
    print("route  start(row,col)  maze cell   steps  junction path (lattice row,col)")
    for i, start, steps, path in routes():
        cell = (ROWS[start[0]], COLS[start[1]])
        print("%3d    %-12s    r%-2d c%-2d    %2d     %s   %s" % (i, start, cell[0], cell[1], len(steps), "".join(NAME[d] for d in steps),
                                                               " ".join("(%d,%d)" % p for p in path)))
    if "--image" in sys.argv:
        draw(sys.argv[sys.argv.index("--image") + 1])
        print("image written")
