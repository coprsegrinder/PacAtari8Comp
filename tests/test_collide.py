"""OV-68: the collision geometry of the GTIA (tools/gtia_collisions.py), the scene stub and its harness, the analyzers, the committed evidence of the live audits, and the chapter."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_collide as AC  # noqa: E402
import cpu6502 as C  # noqa: E402
import gtia_collisions as G  # noqa: E402
import make_collide_cmd as M  # noqa: E402


def blank_playfield(cells=None, charset=None):
    return G.Playfield(cells or [0] * 920, charset or bytes(1024))


def pages():
    return [0] * 256, [[0] * 256 for _ in range(4)]


class Geometry(unittest.TestCase):
    def test_player_missile_edges(self):
        mp, pp = pages()
        mp[100] = 0x30                              # missile 2 (bits 5-4): clocks h, h + 1
        pp[1][100] = 0xFF                           # player 1: clocks 100 .. 107
        pf = blank_playfield()
        for h, hit in ((98, 0), (99, 1), (100, 1), (106, 1), (107, 1), (108, 0)):
            r = G.collision_registers([0, 100, 0, 0, 0, 0, h, 0], mp, pp, pf)
            self.assertEqual(r[8 + 2] == 2, bool(hit), h)       # M2PL bit 1; h = 99: the right pixel (100) touches; h = 107: the left pixel (107) touches

    def test_which_missile_bit_is_which_pixel(self):
        mp, pp = pages()
        mp[50] = 0x02                               # missile 0, bit 1 = its LEFT pixel (clock h)
        pp[0][50] = 0x80                            # player 0: clock 100 only
        pf = blank_playfield()
        self.assertEqual(G.collision_registers([100, 0, 0, 0, 100, 0, 0, 0], mp, pp, pf)[8], 1)
        self.assertEqual(G.collision_registers([100, 0, 0, 0, 99, 0, 0, 0], mp, pp, pf)[8], 0)     # the left pixel at 99, the (empty) right pixel at 100
        mp[50] = 0x01                               # bit 0 = the RIGHT pixel (clock h + 1)
        self.assertEqual(G.collision_registers([100, 0, 0, 0, 99, 0, 0, 0], mp, pp, pf)[8], 1)

    def test_player_does_not_touch_itself(self):
        mp, pp = pages()
        pp[2][60] = 0xFF
        pp[3][60] = 0xFF
        r = G.collision_registers([0, 0, 100, 104, 0, 0, 0, 0], mp, pp, blank_playfield())
        self.assertEqual((r[12 + 2], r[12 + 3]), (0b1000, 0b0100))

    def test_playfield_colours(self):
        # one glyph (code 1) with the four pixel values 0, 1, 2, 3 on its first row; cell (row 0, col 0): clocks 48-51, line 40
        cs = bytearray(1024)
        cs[8] = 0b00011011
        for code, want in ((1, [None, 0, 1, 2]), (0x81, [None, 0, 1, 3])):
            cells = [0] * 920
            cells[0] = code
            pf = G.Playfield(cells, bytes(cs))
            self.assertEqual([pf.pf_bit(40, 48 + k) for k in range(4)], want)
            self.assertIsNone(pf.pf_bit(41, 48))                # the next row of the glyph is empty
            self.assertIsNone(pf.pf_bit(40, 47))                # left of the screen
            self.assertIsNone(pf.pf_bit(39, 48))                # above the first maze row
        mp, pp = pages()
        mp[40] = 0xC0                               # missile 3 over the cell: clocks h, h + 1
        cells = [0] * 920
        cells[0] = 1
        pf = G.Playfield(cells, bytes(cs))
        r = G.collision_registers([0, 0, 0, 0, 0, 0, 0, 48], mp, pp, pf)
        self.assertEqual(r[3], 0b0001)              # clocks 48 and 49: values 0 (background) and 1 (PF0)
        r = G.collision_registers([0, 0, 0, 0, 0, 0, 0, 49], mp, pp, pf)
        self.assertEqual(r[3], 0b0011)              # clocks 49 and 50: values 1 and 2: PF0 and PF1


class Latch(unittest.TestCase):
    def test_platform_latches_until_hitclr(self):
        import platform_iface as PI
        mp, pp = pages()
        mp[100] = 0x30
        pp[1][100] = 0xFF
        state = {"hpos": [0, 100, 0, 0, 0, 0, 104, 0]}
        class W:
            pokey = []
        w = W()
        plat = PI.GtiaCollisions(lambda w: (state["hpos"], mp, pp, blank_playfield()))
        self.assertEqual(plat.collisions(w), [0] * 16)
        plat.frame_done(w)                                  # a frame showed an overlap: M2PL bit 1
        self.assertEqual(plat.collisions(w)[10], 2)
        state["hpos"] = [0, 100, 0, 0, 0, 0, 0, 0]          # the next frame shows no overlap: the latch stays (no HITCLR: death, eaten pause)
        plat.frame_done(w)
        self.assertEqual(plat.collisions(w)[10], 2)
        w.pokey = [(0xD01E, 0)]                             # a frame that clears and shows nothing
        plat.frame_done(w)
        self.assertEqual(plat.collisions(w)[10], 0)
        state["hpos"] = [0, 100, 0, 0, 0, 0, 104, 0]
        w.pokey = [(0xD01E, 0)]                             # a frame that clears first, then shows the overlap
        plat.frame_done(w)
        self.assertEqual(plat.collisions(w)[10], 2)


class Stub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.done = M.assemble()

    def machine(self, seed):
        with open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb") as fh:
            m = C.Machine(fh.read())
        m.mem[M.ORG:M.ORG + len(cls_code(self))] = cls_code(self)
        m.mem[0x4084], m.mem[0x4085] = seed & 255, seed >> 8
        return m

    def test_assembles_and_fits(self):
        self.assertEqual(self.code[:3], bytes([0xAD, 0x80, 0x40]))          # lda READY
        self.assertLess(len(self.code), 0x400)
        self.assertGreater(self.done, M.ORG)

    def test_scenes_are_reproducible_and_wellformed(self):
        a = AC.stub_scenes(M.SEEDS[1], 6)
        b = AC.stub_scenes(M.SEEDS[1], 6)
        c = AC.stub_scenes(M.SEEDS[2], 6)
        self.assertEqual(a, b)
        self.assertNotEqual(a[1], c[1])
        for blob in a.values():
            hpos, rows, pats = AC.scene_of(blob)
            self.assertTrue(all(56 - 16 <= h <= 151 + 16 for h in hpos))
            self.assertTrue(all(48 <= r + 0 and r + 16 <= 208 for r in rows), rows)   # inside the maze rows
            self.assertEqual(len(pats), 5)

    def test_install_puts_the_scene_in_the_pages(self):
        m = self.machine(M.SEEDS[1])
        for _ in range(3):
            m.call(M.ORG, until=self.done, limit=2000000)
        blob = bytes(m.mem[0x4110:0x4190])
        hpos, rows, pats = AC.scene_of(blob)
        for i in range(5):
            self.assertEqual(list(m.mem[0x2300 + 256 * i + rows[i]:0x2300 + 256 * i + rows[i] + 16]), pats[i])
        self.assertEqual(list(m.mem[0xD000:0xD008]), hpos)


def cls_code(t):
    return t.code


class Logs(unittest.TestCase):
    MINI = """4100: 01 00 00 00 00 00 00 00 00 00 06 00 00 00 00 00 |....|
4110: 60 61 62 63 64 65 66 67 40 41 42 43 44 00 01 02 |....|
4120: 03 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 |....|
4130: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 |....|
4140: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 |....|
4150: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 |....|
4160: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 |....|
4170: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 |....|
4180: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 |....|
41A0: 01 03 01 00 |....|
0C00: 00 11 1C |...|
"""

    def test_parse(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "collide-s1.txt")
            with open(p, "w") as fh:
                fh.write(self.MINI)
            mem, recs = AC.parse(p)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual((r["valid"], r["count"]), (1, 0x103))                # the count is 16 bit
        self.assertEqual(r["regs"][10], 6)
        self.assertEqual(r["scene"][:8], bytes(range(0x60, 0x68)))
        self.assertEqual(mem[0x0C01], 0x11)

    def test_seed_of_the_file_name(self):
        self.assertEqual(AC.seed_of("analysis/raw-logs/collide-s2.txt"), M.SEEDS[2])


class Evidence(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_random_scenes(self):
        t = self.read("analysis/evidence-collide-summary.txt")
        m = re.search(r"total: (\d+) scenes compared, (\d+) differences \((\d+) records differ from the generator\); (\d+) distinct scenes", t)
        self.assertTrue(m)
        self.assertGreaterEqual(int(m.group(1)), 60000)
        self.assertEqual(m.group(2), "0")
        self.assertLessEqual(int(m.group(3)), 6)               # the first record of each of the six logs (made before a scene was installed)
        self.assertGreaterEqual(int(m.group(4)), 40000)         # the generator does not repeat after 512 scenes any more
        # every collision bit the game can produce was seen both set and clear
        rows = {r[0]: r for r in re.findall(r"^(\w{4})\s+(\d+)/(\d+)\s+(\d+)/(\d+)\s+(\d+)/(\d+)\s+(\d+)/(\d+)$", t, re.M)}
        for name in ("M1PL", "M2PL", "M2PF", "M0PF", "M3PL"):
            self.assertIn(name, rows)
        # the four playfield colours (bits 0-3 of M2PF) were all seen in the hardware: the test screen
        m2 = re.search(r"^M2PF\s+(\d+)/\d+\s+(\d+)/\d+\s+(\d+)/\d+\s+(\d+)/\d+$", t, re.M)
        self.assertTrue(m2 and all(int(g) > 1000 for g in m2.groups()))

    def test_play(self):
        t = self.read("analysis/evidence-collide-play-summary.txt")
        m = re.search(r"total: (\d+) frames compared, (\d+) differences \((\d+) frames with registers carried over\); (\d+) further frames .*?, (\d+) of them differ", t)
        self.assertTrue(m)
        self.assertGreaterEqual(int(m.group(1)), 25000)
        self.assertEqual(m.group(2), "0")
        self.assertGreaterEqual(int(m.group(3)), 5000)         # the latch was carried over in thousands of frames (the death sequence, the eaten-ghost pause)
        self.assertLessEqual(int(m.group(5)), max(5, int(m.group(4)) // 1000))

    def test_chapter(self):
        d = self.read("docs/50-collision-geometry.md")
        for k in ("OV-68", "OV-69", "0 differences", "M2PF", "GtiaCollisions", "34 to 221", "latch", "512 scenes"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
