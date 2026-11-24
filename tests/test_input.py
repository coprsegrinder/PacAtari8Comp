"""Stage 63 (input processing): the executable model of tools/input_model.py against the real code on the concrete 6502, its rules, the analysis of the live logs, and the committed evidence and chapter."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import input_model as I   # noqa: E402
import analyze_input as AN  # noqa: E402

UP, DOWN, LEFT, RIGHT = I.UP, I.DOWN, I.LEFT, I.RIGHT


class Rules(unittest.TestCase):
    def test_nothing_pressed_changes_nothing(self):
        self.assertEqual(I.steer(0x0F, 0x0C, LEFT, UP, 0x77), (UP, LEFT, 0x77, 0))

    def test_two_directions_are_refused(self):
        for v in (0x0A, 0x09, 0x06, 0x05, 0x0C, 0x03):                     # the diagonals and the two opposite pairs
            self.assertEqual(I.steer(v, 0x0F, LEFT, 0, 0x77), (0, LEFT, 0x77, 0), hex(v))              # nothing changes: the wanted direction stays 0

    def test_a_single_direction_is_remembered_and_taken_when_open(self):
        w, d, a, c = I.steer(0x0E, 0x0C, LEFT, 0, 0)                      # up in a horizontal corridor: closed
        self.assertEqual((w, d, a), (UP, LEFT, UP))
        w, d, a, c = I.steer(0x0F, 0x0F, d, w, a)                          # the stick is back in the middle, the cell opens up: the buffered turn
        self.assertEqual((w, d), (UP, UP))
        self.assertEqual(c, UP | LEFT)                                      # a corner: the flag is set (to the OR of the two directions)

    def test_a_reversal_is_immediate_and_gives_no_corner(self):
        self.assertEqual(I.steer(0x07, 0x0C, LEFT, LEFT, 0), (RIGHT, RIGHT, RIGHT, 0))

    def test_an_immediate_turn_gives_no_corner_flag(self):
        self.assertEqual(I.steer(0x0E, 0x0F, LEFT, LEFT, 0), (UP, UP, UP, 0))   # the flag is only for the buffered path

    def test_three_directions_become_a_value_no_case_matches(self):
        w, d, a, c = I.steer(0x01, 0x0C, LEFT, 0, 0)                      # down+left+right pressed
        self.assertEqual((w, d), (0x0E, 0x0E))
        self.assertEqual(I.motion(d, 0x0C), "none")

    def test_motion(self):
        self.assertEqual(I.motion(LEFT, 0x0C), "left")
        self.assertEqual(I.motion(UP, 0x0C), "blocked")
        self.assertEqual(I.motion(0x0E, 0x0F), "none")

    def test_contact(self):
        y = [100, 100, 100, 100]
        self.assertEqual(I.contact(0x01, 0x01, 100, y, [0x02] * 4), ("death", 0))
        self.assertEqual(I.contact(0x02, 0x02, 104, y, [0x00, 0x82, 0x00, 0x00]), ("eaten", 1))
        self.assertEqual(I.contact(0x02, 0x02, 105, y, [0x00, 0x82, 0x00, 0x00]), ("none", None))   # 5 lines: too far
        self.assertEqual(I.contact(0x04, 0x04, 100, y, [0x00, 0x00, 0x42, 0x00]), ("none", None))   # the eyes are skipped
        self.assertEqual(I.contact(0x04, 0x00, 100, y, [0x00, 0x00, 0x02, 0x00]), ("none", None))   # one register is not enough
        self.assertEqual(I.contact(0x0F, 0x0F, 100, y, [0x82, 0x02, 0x02, 0x02]), ("eaten", 0))     # the first ghost decides


class AgainstTheCode(unittest.TestCase):
    def test_joystick_path_exhaustive(self):
        n, bad, first = I.check(players=(0,))
        self.assertEqual((n, bad), (65536, 0), first)

    def test_second_player_reads_stick1(self):
        n, bad, first = I.check(sticks=range(16), dirs=(0, 1, 4, 5, 12, 15), players=(1,))
        self.assertEqual(bad, 0, first)

    def test_contact_test_sampled(self):
        n, bad, first = I.check_contacts(full=False, sample=20000, seed=3)
        self.assertEqual((n, bad), (20000, 0), first)


class Analysis(unittest.TestCase):
    def test_a_synthetic_log(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "stick.txt")
        steer = I.steer(0x0B, 0x0C, RIGHT, 0, 0x55, 0)
        with open(p, "w") as fh:
            fh.write("SI f=1 x=0 ac=0 pd=8 m=12 at=85 a8=0\nST f=1 v=11\nSO f=1 ac=%d pd=%d at=%d a8=%d\nMV f=1 c=left\n" % steer[:4])
            fh.write("SI f=2 x=0 ac=0 pd=8 m=12 at=85 a8=0\nST f=2 v=11\nSO f=2 ac=9 pd=9 at=1 a8=0\nMV f=2 c=none\n")      # a wrong line
        st = AN.check([p])
        self.assertEqual(st["n"], 2)
        self.assertEqual(len(st["bad"]), 1)


class Evidence(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_evidence(self):
        t = self.read("analysis/evidence-input-summary.txt")
        self.assertIn("131072 cases, 0 mismatches", t)
        self.assertIn("1048576 cases, 0 mismatches", t)
        self.assertIn("passes of `$B183-$B1C4`, 0 disagree with the model", t)
        self.assertIn("0 disagree with the model; outcomes: death", t)
        for v in range(16):
            self.assertIn("$%X:" % v, t)                                      # every stick value was read in the real game
        self.assertIn("A REAL press", t)
        self.assertIn("equals the PIA port (`$D300`) masked to four bits, 0 differ", t)

    def test_chapter_table_is_the_models(self):
        doc = self.read("docs/41-input-processing.md")
        names = ((1, "up"), (2, "down"), (4, "left"), (8, "right"))
        for v in range(16):
            p = v ^ 15
            nm = "+".join(x for b, x in names if p & b) or "none"
            self.assertIn("| `$%X` | %s |" % (v, nm), doc)
            n = bin(p).count("1")
            line = [ln for ln in doc.splitlines() if ln.startswith("| `$%X` | %s |" % (v, nm))][0]
            if n == 2:
                self.assertIn("refused", line)
            elif n == 0:
                self.assertIn("nothing pressed", line)
            elif n == 1:
                self.assertIn("accepted: wanted direction := %s, ATRACT := %d" % (nm, p), line)
            else:
                self.assertIn("none of the four directions", line)
        for k in ("131,072", "1,048,576", "53,207", "138,104"):
            self.assertIn(k, doc)


if __name__ == "__main__":
    unittest.main()
