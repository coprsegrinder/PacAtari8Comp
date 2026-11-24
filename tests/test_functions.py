"""Stages 33-40, 43: tests of tools/analyze_functions.py and of docs/23-function-table.md.  Run:  python -I tests/test_functions.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_functions as AF  # noqa: E402

ROM, F = AF.analyse()
AF.solve(ROM, F)
BY = {f.name: f for f in F.values()}


class Structure(unittest.TestCase):
    def test_every_jsr_target_in_the_rom_is_a_routine(self):
        for t in ROM.jsr_targets:
            if t in ROM.code:
                self.assertIn(t, F, hex(t))

    def test_call_sites_are_inside_bodies(self):
        for f in F.values():
            for site, callee in f.calls.items():
                self.assertIn(site, f.body)
                self.assertEqual(ROM.ins[site][1], "jsr")

    def test_no_indirect_jump_and_no_brk(self):
        self.assertFalse([a for a, i in ROM.ins.items() if i[1] == "jmp" and i[2] == "ind"])
        self.assertFalse([a for a, i in ROM.ins.items() if i[1] == "brk"])

    def test_bodies_cover_all_code(self):
        covered = set()
        for f in F.values():
            covered |= f.body
        self.assertEqual(len(set(ROM.ins) - covered), 0, sorted(set(ROM.ins) - covered)[:5])


class Contracts(unittest.TestCase):
    def test_known_inputs(self):
        self.assertEqual(BY["StepAndDrawEntity"].inputs, {"A", "X"})        # A = direction, X = entity
        self.assertEqual(BY["SetDisplayList"].inputs, {"X", "Y"})           # the display list address
        self.assertEqual(BY["ReadSrcByte"].inputs, {"Y"})
        self.assertEqual(BY["GhostBehaviour"].inputs, {"X"})
        self.assertEqual(BY["ClearPokeyRegisters"].inputs, set())

    def test_results_and_preserved(self):
        self.assertIn("C", BY["JunctionLookup"].out)                         # carry = an exit was found
        self.assertIn("X", BY["JunctionLookup"].preserved)
        self.assertIn("X", BY["GhostBehaviour"].preserved)
        self.assertEqual(BY["DliHandler1"].preserved & {"A", "X"}, {"A", "X"})
        self.assertEqual(BY["DliHandler2"].preserved, {"A", "X", "Y"})
        self.assertIn("A", BY["ReadSrcByte"].out)

    def test_interrupt_handlers(self):
        for n in ("DliHandler1", "DliHandler2"):
            self.assertEqual(BY[n].inputs, set())
            self.assertTrue(BY[n].exits.get("rti"))


class Document(unittest.TestCase):
    def test_document_is_up_to_date(self):
        want = "\n".join(AF.report(ROM, F)) + "\n"
        got = open(os.path.join(ROOT, "docs", "23-function-table.md"), encoding="utf-8", newline="").read().replace("\r\n", "\n")
        self.assertEqual(got, want, "docs/23-function-table.md is out of date: python -I tools/analyze_functions.py --write docs/23-function-table.md")


if __name__ == "__main__":
    unittest.main()
