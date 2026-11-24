"""Stages 69-70: the asset pack of the port - completeness, equality with the RAM the original builds, the loader, a negative control, the previews, the evidence and the chapter."""
import copy
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import algorithm_models as A  # noqa: E402
import asset_pack as AP  # noqa: E402
import check_assets as CA  # noqa: E402


class Pack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P, cls.res = CA.checks()

    def test_every_check_passes(self):
        for name, ok, detail in self.res:
            self.assertTrue(ok, "%s: %s" % (name, detail))
        self.assertGreaterEqual(len(self.res), 19)

    def test_structure(self):
        P = self.P
        self.assertEqual(P["schema"], 2)
        for k in ("regions", "charsets", "maze", "sprites", "text", "tunes", "colours", "tables", "display_lists", "font", "rom"):
            self.assertIn(k, P)
        self.assertEqual(sum(r["size"] for r in P["regions"]), 2246)
        self.assertEqual(P["charsets"]["game"]["glyphs"], 101)
        self.assertEqual((P["maze"]["rows"], P["maze"]["cols"], P["maze"]["dots"]), (23, 40, 256))
        self.assertEqual(len(P["sprites"]["shapes"]), 21)

    def test_the_tables_are_the_nibble_tables(self):
        t = self.P["tables"]
        self.assertEqual(len(t["JunctionExits"]), 100)
        self.assertEqual(t["ReverseDir"][:5], [0, 2, 1, 0, 8])
        self.assertEqual([t["NoReverseMask"][d] for d in (1, 2, 4, 8)], [0xD, 0xE, 0x7, 0xB])      # every exit but the reverse of the direction

    def test_loader_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            AP.write(d)
            P = AP.load(os.path.join(d, "assets.json"))
            self.assertEqual(P, json.loads(AP.dumps(self.P)))
            with open(os.path.join(d, "manifest.json")) as fh:
                man = json.load(fh)
            self.assertEqual(set(man["files"]), {"assets.json", "charset_game.png", "maze.png", "sprites.png", "text.png"})
            self.assertEqual(man["rom_sha256"], P["rom"]["sha256"])

    def test_the_check_can_fail(self):
        """negative control: one changed maze code and the loader's image no longer equals the RAM that Start builds"""
        bad = copy.deepcopy(self.P)
        bad["maze"]["codes"][5][7] ^= 1
        img = AP.ram_image(bad)
        mem = A.started_machine().mem
        self.assertNotEqual(bytes(img[0x800:0x800 + 920]), bytes(mem[0x800:0x800 + 920]))
        self.assertEqual(bytes(AP.ram_image(self.P)[0x800:0x800 + 920]), bytes(mem[0x800:0x800 + 920]))

    def test_previews_are_png(self):
        with tempfile.TemporaryDirectory() as d:
            AP.write(d)
            for name, size in (("maze.png", (320, 184)), ("charset_game.png", (128, 56)), ("sprites.png", (210, 16)), ("text.png", (272, 64))):
                with open(os.path.join(d, name), "rb") as fh:
                    b = fh.read()
                self.assertEqual(b[:8], b"\x89PNG\r\n\x1a\n")
                w, h = struct.unpack(">II", b[16:24])
                self.assertEqual((w, h), size, name)
                i = b.index(b"IDAT")
                n = struct.unpack(">I", b[i - 4:i])[0]
                self.assertEqual(len(zlib.decompress(b[i + 4:i + 4 + n])), h * (w + 1))


class Evidence(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_evidence(self):
        t = self.read("analysis/evidence-assets-summary.txt")
        self.assertIn("19 checks", t)
        self.assertNotIn("FAIL", t)
        self.assertEqual(t.count("PASS:"), 19)

    def test_chapter(self):
        d = self.read("docs/47-resources.md")
        for k in ("schema 2", "Every byte of the ROM that is not code", "third-party/README.md", "EightBit Atari-Regular", "bit-for-bit", "never committed", "256 dots + 4 power pellets = 260", "19 of 19 checks pass", "OV-68"):
            self.assertIn(k, d)

    def test_font_credit_and_licence_files(self):
        base = os.path.join(ROOT, "third-party", "EightBit-Atari-Fonts")
        for f in ("EightBit Atari-Regular.ttf", "OFL.txt", "README.upstream.md"):
            self.assertTrue(os.path.exists(os.path.join(base, f)), f)
        ofl = self.read("third-party/EightBit-Atari-Fonts/OFL.txt")
        self.assertIn("Steve Boswell", ofl)
        self.assertIn("SIL OPEN FONT LICENSE Version 1.1", ofl)
        self.assertIn("PERMISSION & CONDITIONS", ofl)
        note = self.read("third-party/README.md")
        for k in ("Steve Boswell", "SIL Open Font License", "8b5a19f41f46fc93fe58455355b5bc0c31c31bda", "provenance"):
            self.assertIn(k, note)

    def test_font_glyphs(self):
        rows = [bytes.fromhex(r) for r in AP.build()["font"]["rows"]]
        self.assertEqual(rows[0], bytes(8))
        self.assertEqual(rows[0x21], bytes([0x00, 0x18, 0x3C, 0x66, 0x66, 0x7E, 0x66, 0x00]))      # 'A'
        self.assertEqual(AP.ram_image(AP.build())[0xE000 + 0x21 * 8:0xE000 + 0x22 * 8], rows[0x21])

    def test_pack_is_not_tracked(self):
        ig = self.read(".gitignore")
        self.assertIn("/resources/", ig)


if __name__ == "__main__":
    unittest.main()
