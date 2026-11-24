"""Stage 100: the archive tool (tools/make_archive.py) keeps its promises: Personal notes.txt is never selected, the big regenerable folders are skipped,
and the preservation chapter names every part the tool writes."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_archive as A  # noqa: E402


class Archive(unittest.TestCase):
    def test_selection(self):
        ev = A.ignored_files()
        self.assertNotIn("Personal notes.txt", ev)
        for f in ev:
            self.assertFalse(f.startswith(A.SKIP_PREFIX), f)
            self.assertNotIn("__pycache__", f)
        self.assertIn("Personal notes.txt", A.NEVER)

    def test_chapter_names_every_part(self):
        t = open(os.path.join(ROOT, "docs", "66-preservation.md"), encoding="utf-8").read()
        for part in ("pacman-a8-history.bundle", "pacman-a8-owner-materials.zip", "pacman-a8-dependencies.zip", "pacman-a8-local-evidence.zip", "SHA256SUMS", "ARCHIVE-MANIFEST.json", "Personal notes.txt", "analysis/raw-logs"):
            self.assertIn(part, t)

    def test_readme_names_the_restore_steps(self):
        for s in ("git clone", "sha256sum -c SHA256SUMS", "docs/63"):
            self.assertIn(s, A.README)


if __name__ == "__main__":
    unittest.main()
