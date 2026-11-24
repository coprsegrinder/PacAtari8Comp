"""Checklist stage 4: the architecture document - every routine of the ROM is classified against the port, the port functions exist, the order of the frame in the ROM is the order of play_frame, and the chapter says what it must."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_architecture as AA  # noqa: E402


def first_occurrences(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


class Classification(unittest.TestCase):
    def test_every_routine_is_classified_and_every_reference_exists(self):
        self.assertEqual(AA.check_refs(), [])
        self.assertEqual(len(AA.ROUTINE_PORT), 81)

    def test_statuses(self):
        for n, (st, ref, note) in AA.ROUTINE_PORT.items():
            self.assertIn(st, (AA.PORT, AA.PART, AA.NOT, AA.LAYER, AA.ASSET), n)
            self.assertTrue(note, n)
        self.assertEqual(AA.ROUTINE_PORT["MovePacMan"][:2], (AA.PORT, "core_pacman.move_pacman"))
        self.assertEqual(AA.ROUTINE_PORT["TurnControl"][0], AA.NOT)
        self.assertEqual(AA.ROUTINE_PORT["ExpandData"][0], AA.ASSET)

    def test_port_functions_are_the_ones_the_core_tests_check(self):
        """the functions named as port form are those the checkers of `44` compare with the ROM"""
        import check_ghost, check_pacman, check_score, check_sound, check_frame, check_play, check_draw  # noqa: F401
        for n, (st, ref, note) in AA.ROUTINE_PORT.items():
            if st == AA.PORT:
                mod = ref.split(".")[0]
                self.assertIn(mod, ("core_ghost", "core_pacman", "core_score", "core_sound", "core_frame", "core_play", "core_ref", "core_draw"), n)


class FrameOrder(unittest.TestCase):
    def test_the_rom_order_is_the_port_order(self):
        rom = [AA.port_function_of(name) for site, name in AA.rom_frame_order()]
        self.assertNotIn(None, rom)
        rom_first = first_occurrences(rom)
        port = first_occurrences(AA.port_frame_order())
        self.assertEqual([f for f in port if f in rom_first], rom_first)
        self.assertGreaterEqual(len(rom_first), 15)

    def test_the_call_sites_are_in_the_play_frame(self):
        sites = [s for s, n in AA.rom_frame_order()]
        self.assertEqual(sites, sorted(sites))
        self.assertTrue(all(0xA82C <= s <= 0xAA26 for s in sites))


class Chapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "docs", "48-architecture.md"), encoding="utf-8") as fh:
            cls.d = fh.read()

    def test_sections(self):
        for k in ("## 1. The result", "## 2. The program in one picture", "## 3. How one frame runs", "## 4. Subsystems", "## 5. The layers of a port", "## 6. The layout of `src/c` (decided, stage 74)", "## 7. How a port is tested", "## 8. Not yet specified", "## 9. The owner decisions of stages 71-74 (taken 2026-11-18)"):
            self.assertIn(k, self.d)

    def test_diagrams(self):
        self.assertEqual(self.d.count("```mermaid"), 2)

    def test_numbers_agree_with_the_table(self):
        from collections import Counter
        c = Counter(st for st, ref, note in AA.ROUTINE_PORT.values())
        self.assertIn("**%d are in port form**" % c[AA.PORT], self.d)
        self.assertIn("Each of the 81 routines is classified", self.d)

    def test_decisions_are_recorded(self):
        for k in ("**faithful frame-by-frame port with a thin hardware layer**", "**the whole state each frame**", "**C99, clang and gcc, CMake (Ninja)**", "**the layout of section 6**"):
            self.assertIn(k, self.d)
        for f in ("CMakeLists.txt", os.path.join("tests", "toolchain_check.c"), "README.md"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "src", "c", f)), f)
        for d in ("platform", "core", "assets", "app", "render", "tests"):
            self.assertTrue(os.path.isdir(os.path.join(ROOT, "src", "c", d)), d)

    def test_claims_tie_to_the_chapters(self):
        for k in ("37 scan lines of 262", "28 lines to the next vertical blank", "OV-69", "OV-02", "`$DC`"):
            self.assertIn(k, self.d)
        for ch in re.findall(r"`(\d\d)`", self.d):
            self.assertTrue([f for f in os.listdir(os.path.join(ROOT, "docs")) if f.startswith(ch + "-")], ch)


if __name__ == "__main__":
    unittest.main()
