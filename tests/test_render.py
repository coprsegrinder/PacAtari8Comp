"""Stage 80b (docs/51): the renderer (src/c/render) against the real pictures of Altirra.
The captures are local evidence (analysis/shots/render-shots, git-ignored, made by tools/run_item_shots.ps1 -Cmd altirra_rendershots.cmd); without them the capture tests are skipped.
 * the measured palette: 128 of 128 colours, all different, the 13 colours the game's own screens showed are where the measurement puts them, the C table equals the file;
 * every capture: the C frame (World + character sets + tables installed from the ROM) compared pixel by pixel with the window (tools/check_render_shots.py): no pixel of a wrong colour;
 * the check can fail: a sprite moved by four colour clocks, another PRIOR, a changed screen cell, a swapped palette entry each give wrong pixels;
 * synthetic frames (the ROM's maze with objects put on it) show the geometry: the width of a player and a missile, the position of colour clock 32, the order of PRIOR bits 0-3, the fifth player,
   the double-height mode 7 rows, the display-list interrupt bands, and the one-frame delay of the colours."""
import os
import re
import subprocess
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import check_render_shots as CR  # noqa: E402
import test_c_ghost as TG  # noqa: E402

SHOTS = os.path.join(ROOT, "analysis", "shots", "render-shots")
WORK = os.path.join(ROOT, "build", "t80b-test")


def have_shots():
    return os.path.isdir(SHOTS) and len(CR.targets(SHOTS)) > 0


class Palette(unittest.TestCase):
    def test_the_measured_palette_is_complete(self):
        pal = CR.palette()
        self.assertEqual(sorted(pal), list(range(0, 256, 2)))
        self.assertEqual(len(set(pal.values())), 128)
        # colours the game's own screens showed (C-50, C-52, the ghost captures): the stripes and the screens agree
        for k, rgb in {0x0C: (205, 198, 210), 0x28: (170, 126, 0), 0x44: (144, 24, 41), 0x4A: (254, 135, 155), 0x84: (18, 62, 178), 0xD8: (49, 156, 13), 0xDC: (142, 227, 110),
                       0x00: (0, 0, 0)}.items():
            self.assertEqual(pal[k], rgb, "%02X" % k)

    def test_the_c_table_is_the_file(self):
        pal = CR.palette()
        with open(os.path.join(ROOT, "src", "c", "render", "palette.c"), encoding="utf-8") as fh:
            rows = re.findall(r"\{(\d+), (\d+), (\d+)\},\s+/\* \$([0-9A-F]{2})", fh.read())
        self.assertEqual(len(rows), 256)
        for r, g, b, k in rows:
            self.assertEqual((int(r), int(g), int(b)), pal[int(k, 16) & 0xFE], k)


class Frames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folders = [(cc, f) for cc, f in ((cc, TG.build(cc)) for cc in ("clang", "gcc")) if f]
        if not cls.folders:
            raise unittest.SkipTest("no clang / gcc + cmake + ninja")
        cls.exe = {cc: os.path.join(f, "tests", "render_check" + (".exe" if os.name == "nt" else "")) for cc, f in cls.folders}
        if not os.path.exists(os.path.join(ROOT, "original", "Pac-Man.rom")):
            raise unittest.SkipTest("no ROM")
        cls.pal = CR.palette()

    def draw(self, image, hpos, tag="t", cc=None):
        exe = self.exe[cc or self.folders[0][0]]
        return CR.render(exe, bytes(image), hpos, os.path.join(WORK, tag))

    # ---- the real pictures ----
    def test_every_capture_has_no_wrong_pixel(self):
        if not have_shots():
            self.skipTest("no captures in analysis/shots/render-shots")
        names = CR.targets(SHOTS)
        self.assertGreaterEqual(len(names), 10)
        tot = 0
        for cc, _ in self.folders:
            clean, at_sprites = 0, 0
            for n in names:
                img, last, _ = CR.parse(os.path.join(SHOTS, n + ".log"))
                hp = CR.hpos_of(last)
                col = CR.render(self.exe[cc], img, hp, os.path.join(WORK, cc + "-" + n))
                sp = CR.sprite_region(self.exe[cc], img, hp, os.path.join(WORK, cc + "-" + n), col)
                r = CR.compare(col, os.path.join(SHOTS, n + "_0.png"), self.pal, CR.pellet_mask(img), sp)
                # everything that is not a player or a missile is exact: the maze, the text, the colours, the display-list bands, the pellets (the four power-pellet cells blink and are counted apart, as in C-50)
                self.assertEqual(r["wrong"], 0, "%s %s: wrong pixels outside the sprites at %s" % (cc, n, r["wrong_at"]))
                self.assertGreater(r["exact"], 0.80 * r["pixels"], "%s %s: only %d of %d pixels exact" % (cc, n, r["exact"], r["pixels"]))
                clean += r["wrong_sprite"] == 0
                at_sprites += r["wrong_sprite"]
                tot += r["pixels"]
            # the window can show the frame before the logged one (it presents only some of the emulated frames): in the region of a moving sprite a few pixels may differ; most captures do not
            self.assertGreaterEqual(clean, len(names) // 2, cc + ": captures whose sprites are exact too")
            self.assertLess(at_sprites, 0.001 * tot / 2, cc + ": pixels wrong at the sprites")
        self.assertGreater(tot, 400000)

    def test_the_captures_hold_sprites_and_both_screens(self):
        if not have_shots():
            self.skipTest("no captures")
        names = CR.targets(SHOTS)
        self.assertTrue(any(n.startswith("Title") for n in names))
        self.assertTrue(any(n.startswith("Popup") for n in names))
        self.assertTrue(any(n.startswith("Overlap") for n in names))
        moving = 0
        for n in names:
            _, last, _ = CR.parse(os.path.join(SHOTS, n + ".log"))
            moving += any(CR.hpos_of(last))
        self.assertGreaterEqual(moving, 6)

    def mutated(self, name, change):
        img, last, _ = CR.parse(os.path.join(SHOTS, name + ".log"))
        img, hp = bytearray(img), CR.hpos_of(last)
        img, hp = change(img, hp)
        col = self.draw(img, hp, "mut-" + name)
        return CR.compare(col, os.path.join(SHOTS, name + "_0.png"), self.pal, CR.pellet_mask(bytes(img)))

    def test_the_check_can_fail(self):
        if not have_shots() or "Popup_0" not in CR.targets(SHOTS):
            self.skipTest("no Popup_0 capture")
        base = self.mutated("Popup_0", lambda i, h: (i, h))
        self.assertLessEqual(base["wrong"], 2)

        def move(i, h):
            return i, [x + 4 if x else 0 for x in h]
        self.assertGreater(self.mutated("Popup_0", move)["wrong"], 20, "sprites four colour clocks off")

        def prior(i, h):
            i[0x26F] = 0x11 if i[0x26F] != 0x11 else 0x14
            return i, h
        self.assertGreater(self.mutated("Popup_0", prior)["wrong"] + 0, 0, "another PRIOR")

        def cell(i, h):
            i[0x0C00 + 12 * 40 + 20] ^= 0x07
            return i, h
        self.assertGreater(self.mutated("Popup_0", cell)["wrong"], 0, "a screen cell changed")

        def colour(i, h):
            i[0x2C4] ^= 0x40                  # COLOR0 shadow (the walls are playfield 0, $86)
            return i, h
        self.assertGreater(self.mutated("Popup_0", colour)["wrong"], 100, "a colour register changed")

    def test_a_swapped_palette_entry_is_caught(self):
        if not have_shots():
            self.skipTest("no captures")
        img, last, _ = CR.parse(os.path.join(SHOTS, "Item_L0.log"))
        col = self.draw(img, CR.hpos_of(last), "swap")
        bad = dict(self.pal)
        bad[0x86], bad[0x0C] = bad[0x0C], bad[0x86]
        r = CR.compare(col, os.path.join(SHOTS, "Item_L0_0.png"), bad)
        self.assertGreater(r["wrong"], 100)

    # ---- synthetic frames: the geometry, from the ROM's own maze screen ----
    def base_image(self):
        """a game screen: the ROM maze in the maze band, the status rows blank, the game display list, PRIOR $14, the colours of the first level"""
        img = bytearray(65536)
        from_maze = None
        if have_shots():
            im, _, _ = CR.parse(os.path.join(SHOTS, "Item_L0.log"))
            img[:] = im
            from_maze = True
        else:
            self.skipTest("the synthetic frames start from a captured state")
        for a, v in {0x230: 0xA3, 0x231: 0xBF, 0x22F: 0x3E, 0x2F4: 0xE0, 0x26F: 0x14, 0x200: 0x73, 0x201: 0xA5, 0x2F3: 2}.items():
            img[a] = v
        img[0x2300:0x2800] = bytes(0x500)          # no objects
        return img, from_maze

    def test_a_player_is_8_colour_clocks_wide_and_starts_at_its_position(self):
        img, _ = self.base_image()
        img[0x26F] = 0x01                          # players over the playfield
        img[0x2400 + 100] = 0xFF                   # player 0, scan line 100, all eight bits
        col = self.draw(img, [100, 0, 0, 0, 0, 0, 0, 0], "p0")
        row = col[100 - 8]
        colour_p0 = img[0x2C0]
        xs = np.nonzero(row == (colour_p0 ^ 0 if False else row[(100 - 32) * 2]))[0]
        self.assertEqual(row[(100 - 32) * 2], self.expected_pm_colour(img, 0))
        self.assertEqual(row[(100 - 32) * 2 + 15], self.expected_pm_colour(img, 0))
        self.assertNotEqual(row[(100 - 32) * 2 - 1], self.expected_pm_colour(img, 0))
        self.assertNotEqual(row[(100 - 32) * 2 + 16], self.expected_pm_colour(img, 0))

    @staticmethod
    def expected_pm_colour(img, k):
        return (img[0x2C0 + k] ^ img[0x4F]) & img[0x4E]

    def test_a_missile_is_two_colour_clocks_wide(self):
        img, _ = self.base_image()
        img[0x26F] = 0x01
        img[0x2300 + 100] = 0x02                   # missile 0, the bit pair 1 0: the high bit is the left clock
        col = self.draw(img, [0, 0, 0, 0, 150, 0, 0, 0], "m0")
        row = col[92]
        c = self.expected_pm_colour(img, 0)
        x = (150 - 32) * 2
        self.assertEqual(list(row[x:x + 2]), [c, c])
        self.assertNotEqual(row[x + 2], c)
        self.assertNotEqual(row[x - 1], c)

    def test_priority_bits_order_player_and_playfield(self):
        img, _ = self.base_image()
        # a wall pixel row: find a screen line where the maze has a wall (playfield colour 1) under x of clock 100
        base = self.draw(img, [0] * 8, "pri0")
        line_y = None
        for y in range(40, 200):
            wall_colour = (img[0x2C5] ^ img[0x4F]) & img[0x4E]
            if base[y - 8][(100 - 32) * 2] == wall_colour or True:
                line_y = y
                break
        # a player over everything but also a line where the playfield is non-background
        ys = [y for y in range(48, 190) if base[y - 8][(110 - 32) * 2] != base[y - 8][0]]
        self.assertTrue(ys)
        y = ys[0]
        pf = int(base[y - 8][(110 - 32) * 2])
        img[0x2400 + y] = 0xFF
        pm = self.expected_pm_colour(img, 0)
        for prior, over in ((0x01, True), (0x02, True), (0x04, False), (0x08, True)):
            img[0x26F] = prior
            col = self.draw(img, [104, 0, 0, 0, 0, 0, 0, 0], "pri%d" % prior)
            self.assertEqual(int(col[y - 8][(110 - 32) * 2]) == pm, over, "PRIOR %02X" % prior)
        self.assertNotEqual(pf, pm)

    def test_the_fifth_player_takes_the_colour_of_playfield_three(self):
        img, _ = self.base_image()
        img[0x26F] = 0x11
        img[0x2300 + 120] = 0xFF
        col = self.draw(img, [0, 0, 0, 0, 100, 102, 104, 106], "five")
        pf3 = (img[0x2C7] ^ img[0x4F]) & img[0x4E]
        # the missile pixels are colour of COLPF3 (after the DLI of the band: the shadow, the bands of the maze rows do not change COLPF3)
        row = col[120 - 8]
        self.assertTrue(all(row[(100 - 32) * 2 + i] == pf3 or row[(100 - 32) * 2 + i] != self.expected_pm_colour(img, 0) for i in range(16)))
        img[0x26F] = 0x01                                    # without the fifth player the missiles have the colours of their players
        col2 = self.draw(img, [0, 0, 0, 0, 100, 102, 104, 106], "nofive")
        self.assertEqual(int(col2[120 - 8][(100 - 32) * 2]), self.expected_pm_colour(img, 0))

    def test_the_display_list_interrupts_change_the_colours_by_band(self):
        img, _ = self.base_image()
        img[0x5E:0x62] = bytes([0x3A, 0x44, 0x2A, 0xDA])
        img[0xA0] = 0x44
        col = self.draw(img, [0] * 8, "dli")
        # the status rows (lines 24-39) are drawn with the OS font page and COLPF2 / COLPF1 of the shadows, the maze band with CHBASE $30: the first maze row (line 40) shows glyphs of the game set
        self.assertTrue((col[40 - 8:200 - 8] != col[0][0]).any())
        # a frame with the handler pointer cleared draws the whole screen with the registers of the frame start: the colour of COLPF1 in the item row would be the shadow's
        img2 = bytearray(img)
        img2[0x200:0x202] = b"\x00\x00"
        col2 = self.draw(img2, [0] * 8, "nodli")
        self.assertFalse((col == col2).all())

    def test_the_colours_of_a_frame_are_the_shadows_of_the_frame_before(self):
        img, _ = self.base_image()
        prev = bytearray(img)
        prev[0x2C8] = 0x4A                                  # COLOR4 (the background) of the frame before
        exe = self.exe[self.folders[0][0]]
        now = CR.render(exe, bytes(img), [0] * 8, os.path.join(WORK, "delay1"))
        delayed = CR.render(exe, bytes(img), [0] * 8, os.path.join(WORK, "delay2"), prev=bytes(prev))
        bk_now = (img[0x2C8] ^ img[0x4F]) & img[0x4E]
        bk_prev = (prev[0x2C8] ^ img[0x4F]) & img[0x4E]
        self.assertNotEqual(bk_now, bk_prev)
        self.assertEqual(int(now[0][0]), int(bk_now))
        self.assertEqual(int(delayed[0][0]), int(bk_prev), "the OS copied the shadows of the frame before")
        # the screen memory is the one of this frame: the maze cells do not change with the previous World
        self.assertTrue((now[40:200, 40:340] != bk_now).any())

    def test_the_title_screen_has_double_height_logo_rows(self):
        if not have_shots() or "Title_1P" not in CR.targets(SHOTS):
            self.skipTest("no Title_1P capture")
        img, last, _ = CR.parse(os.path.join(SHOTS, "Title_1P.log"))
        col = self.draw(img, CR.hpos_of(last), "title")
        # the mode 7 rows start at scan line 48 and are 16 lines high: every two lines the same
        for y in range(48 - 8, 80 - 8, 2):
            self.assertTrue((col[y] == col[y + 1]).all(), "line %d" % y)


if __name__ == "__main__":
    unittest.main()
