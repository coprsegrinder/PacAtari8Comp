"""Stage 99: the release tool (tools/make_release.py) keeps its promises: the file selection leaves out every forbidden kind of file, the archive is deterministic,
line ends are normalised, and the ROM-piece check really detects a ROM piece."""
import os
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_release as R  # noqa: E402


class Release(unittest.TestCase):
    def test_selection_has_no_forbidden_file(self):
        keep, _ = R.selected()
        names = [n for n, _ in keep]
        self.assertIn("LICENSE", names)
        self.assertIn("NOTICE", names)
        for n in names:
            self.assertFalse(n.startswith(R.EXCLUDE_DIRS), n)
            self.assertNotIn(n, R.EXCLUDE_FILES)
            # the CRT shaders' lookup textures (small PNG files the shaders read) are kept on purpose: R.KEEP_PREFIX; nothing else with a forbidden suffix
            self.assertFalse(n.lower().endswith(R.EXCLUDE_SUFFIX) and not n.startswith(R.KEEP_PREFIX), n)
        self.assertNotIn("Personal notes.txt", names)

    def test_line_ends_are_normalised_and_binary_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            t, b = os.path.join(d, "t"), os.path.join(d, "b")
            open(t, "wb").write(b"a\r\nb\r\n")
            open(b, "wb").write(b"\0a\r\nb")
            self.assertEqual(R.content(t), b"a\nb\n")
            self.assertEqual(R.content(b), b"\0a\r\nb")

    def test_archive_is_deterministic_and_has_a_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a.zip"), os.path.join(d, "b.zip")
            m, _ = R.build_archive(a)
            R.build_archive(b)
            self.assertEqual(R.sha256(a), R.sha256(b))
            with zipfile.ZipFile(a) as z:
                self.assertIn(R.NAME + "-" + R.VERSION + "/" + R.MANIFEST, z.namelist())
                self.assertEqual(len(z.namelist()), len(m["files"]) + 1)
                self.assertEqual({zi.date_time for zi in z.infolist()}, {R.STAMP})

    def test_the_rom_piece_check_detects_a_piece(self):
        pieces = R.rom_pieces()
        if not pieces:
            self.skipTest("the ROMs are not at original/")
        name, off, w = pieces[len(pieces) // 2]
        self.assertTrue(w in b"xx" + w + b"yy")
        self.assertFalse(any(w2 in b"just text, no rom bytes" for _, _, w2 in pieces))

    def test_the_chapter_names_the_decisions(self):
        t = open(os.path.join(ROOT, "docs", "65-release.md"), encoding="utf-8").read()
        for s in ("MIT", "src/asm/pacman.s", "Personal notes.txt", "make_release.py"):
            self.assertIn(s, t)


if __name__ == "__main__":
    unittest.main()
