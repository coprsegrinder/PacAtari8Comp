"""OV-65: the key loop's outcome counters (tools/make_keyloop_cmd.py), their analysis (tools/analyze_keyloop.py), the claims about the outcomes that cannot happen, and the committed evidence."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_keyloop_cmd as K  # noqa: E402
import analyze_keyloop as AK  # noqa: E402
import absint6502 as AB       # noqa: E402

PROG = AB.Program()


def at(a):
    return PROG.ins[a]


class Generator(unittest.TestCase):
    def test_every_branch_has_two_counters(self):
        br = K.branches()
        self.assertEqual(len(br), 27)
        cmds = K.commands()
        for k, (a, m, t) in enumerate(br):
            line = [c for c in cmds if c.startswith("bp -n %x " % a)]
            self.assertEqual(len(line), 1, "$%04X" % a)
            self.assertIn("ew $%x" % (K.BASE + 4 * k), line[0])
            self.assertIn("ew $%x" % (K.BASE + 4 * k + 2), line[0])
        self.assertTrue(any(c.startswith("bt a5fd") and c.count("%d") == 2 + 2 * 27 for c in cmds))

    def test_flags_are_read_with_masks_not_shifts(self):
        self.assertNotIn(">>", " ".join(K.BR.values()))                       # the debugger's >> is not a shift
        self.assertEqual(K.BR["bne"], "1-((@p&2)/2)")

    def test_targeted_run(self):
        cmds = K.commands(only={0xA4EB}, passes=False, blocks=[0xA4ED, 0xA4F1])
        self.assertEqual(len([c for c in cmds if c.startswith("bp -n a4eb")]), 1)
        self.assertEqual(len([c for c in cmds if c.startswith("bp -n a4c6")]), 0)
        self.assertTrue(any(c.startswith("bp -n a4ed") for c in cmds) and any(c.startswith("bp -n a4f1") for c in cmds))
        self.assertTrue(any(c.startswith('bt a5fd "KB') for c in cmds))


class Claims(unittest.TestCase):
    """the outcomes that cannot happen: the flag a branch tests is fixed by the instruction before it"""
    def test_after_a_load_of_a_constant(self):
        self.assertEqual(at(0xA4DC)[1:], ("lda", "imm", 0))        # $A4DE beq: Z = 1
        self.assertEqual(at(0xA4DE)[1], "beq")
        self.assertEqual(at(0xA4F1)[1:], ("lda", "imm", 4))        # $A4F3 bne: Z = 0
        self.assertEqual(at(0xA4F3)[1], "bne")
        self.assertEqual(at(0xA548)[1:], ("lda", "imm", 1))        # $A54A bne: Z = 0
        self.assertEqual(at(0xA54A)[1], "bne")
        self.assertEqual(at(0xA56D)[1:], ("lda", "imm", 0))        # $A571 beq: the `sta` between does not change Z
        self.assertEqual(at(0xA56F)[1], "sta")
        self.assertEqual(at(0xA571)[1], "beq")

    def test_after_a_compare_and_a_branch(self):
        self.assertEqual(at(0xA531)[1:], ("cmp", "imm", 5))        # $A535 bne: `cmp #5 / beq` fell through, so not equal
        self.assertEqual(at(0xA533)[1], "beq")
        self.assertEqual(at(0xA535)[1], "bne")

    def test_after_an_increment(self):
        self.assertEqual(at(0xA55B)[1:], ("cmp", "imm", 2))
        self.assertEqual(at(0xA55D)[1], "bcs")                      # StartLevel < 2 here ...
        self.assertEqual(at(0xA55F)[1], "inc")                      # ... so the increment gives 1 or 2: $A561 bne always taken
        self.assertEqual(at(0xA561)[1], "bne")
        self.assertEqual((at(0xA567)[1], at(0xA569)[1], at(0xA56B)[1]), ("inc", "inc", "bne"))

    def test_the_dead_list_is_these_seven(self):
        self.assertEqual(sorted(AK.DEAD), [0xA4DE, 0xA4F3, 0xA535, 0xA54A, 0xA561, 0xA56B, 0xA571])


class Analysis(unittest.TestCase):
    def log(self, text):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "keyloop-x.txt")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def test_last_complete_line_is_used(self):
        nums = " ".join("0 0" for _ in range(27))
        p = self.log("KC f=1 p=5 %s\nKC f=2 p=7 %s\nKC f=3 p=9 " % (nums, nums))   # the last line is cut
        f, ps, v = AK.last_counters(p)
        self.assertEqual((f, ps, len(v)), (2, 7, 54))

    def test_blocks_give_the_countdown_outcomes(self):
        nums = " ".join("0 0" for _ in range(27))
        p = self.log("KC f=9 p=0 %s\nKB f=9 100 1\n" % nums)
        br, seen, frames, passes = AK.gather([p])
        self.assertIn((0xA4EB, "not taken"), seen)
        self.assertIn((0xA4EF, "taken"), seen)                      # 100 - 1 countdown passes with the timer not 0
        self.assertIn((0xA4EF, "not taken"), seen)
        self.assertIn((0xA4F3, "taken"), seen)


class Evidence(unittest.TestCase):
    def test_every_outcome_accounted_for(self):
        with open(os.path.join(ROOT, "analysis", "evidence-keyloop-summary.txt"), encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("54 outcomes of 27 branches: 47 seen, 7 cannot happen", txt)
        self.assertIn("0 not seen", txt)
        self.assertNotIn("NOT SEEN", txt)
        self.assertIn("idle pass on a title screen (GameState not 0, trigger and console not pressed): 111 instruction cycles", txt)
        self.assertIn("idle pass in a game (GameState 0, no key, no countdown, no console key): 114 instruction cycles", txt)


if __name__ == "__main__":
    unittest.main()
