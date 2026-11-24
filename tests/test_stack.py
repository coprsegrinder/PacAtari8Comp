"""Stage 44: tests of tools/analyze_stack.py, tools/analyze_stack_log.py and docs/28-stack.md.  Run:  python -I tests/test_stack.py"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_stack as S  # noqa: E402
import analyze_stack_log as SL  # noqa: E402

ROM, F, OWNER, DEPTH, BAD, UNBAL, PEAK, CHAIN, OPS, PAGE1 = S.analyse()
BY = {f.name: e for e, f in F.items()}


class Code(unittest.TestCase):
    def test_stack_page_is_never_addressed(self):
        self.assertEqual(PAGE1, [])

    def test_only_these_instructions_touch_the_stack(self):
        got = sorted((a, m) for lst in OPS.values() for a, m in lst)
        self.assertEqual(got, [(0xA480, "txs"), (0xA573, "pha"), (0xA575, "pha"), (0xA5CA, "pla"), (0xA5CC, "pla"), (0xA5CE, "pha"), (0xA5D0, "pha"), (0xA5D2, "pha"),
                               (0xA5F7, "pla"), (0xA5F9, "pla"), (0xA5FB, "pla"), (0xB1A8, "pha"), (0xB1B5, "pla"), (0xB43F, "pha"), (0xB448, "pla"), (0xB4D7, "php"), (0xB506, "plp")])
        self.assertEqual(sorted(S.NOTE), sorted(a for a, m in got))                      # every one is explained

    def test_no_tsx_no_plp_pushed_address_trick_no_indirect_jump(self):
        self.assertFalse([a for a, i in ROM.ins.items() if i[1] == "tsx"])
        self.assertFalse([a for a, i in ROM.ins.items() if i[1] == "jmp" and i[2] == "ind"])

    def test_every_routine_is_balanced(self):
        self.assertEqual(UNBAL, [])
        self.assertEqual({F[e].name: v for e, v in BAD.items() if v}, {})

    def test_pushes_and_pops_pair_up_per_routine(self):
        for e, lst in OPS.items():
            push = sum(1 for a, m in lst if m in ("pha", "php"))
            pop = sum(1 for a, m in lst if m in ("pla", "plp"))
            self.assertEqual(push, pop, F[e].name)

    def test_initial_stack_pointer(self):
        t, ok, sp = S.init_sp(ROM)
        self.assertEqual((t, ok, sp), (0xA480, True, 0xFF))
        # the loop before it: ldx #$1F ... dex / bpl
        self.assertEqual([ROM.data[0xA479 - 0xA000], ROM.data[0xA47A - 0xA000]], [0xA2, 0x1F])

    def test_peaks(self):
        self.assertEqual({n: PEAK[BY[n]] for n in ("Start", "VbiHandler", "DliHandler1", "DliHandler2")},
                         {"Start": 6, "VbiHandler": 10, "DliHandler1": 2, "DliHandler2": 3})
        self.assertEqual(PEAK[BY["FillPlayerPages"]], 0)
        self.assertEqual(PEAK[BY["ClearPlayerMemory"]], 2)
        # a call adds 2, a push adds 1
        self.assertEqual(PEAK[BY["JunctionLookup"]], 1)
        self.assertEqual(PEAK[BY["MovePacMan"]], 3)

    def test_peak_is_at_least_every_callee_plus_two(self):
        for e, f in F.items():
            for site, c in f.calls.items():
                if c in F:
                    self.assertGreaterEqual(PEAK[e], PEAK[c] + 2, F[e].name)


class LogAnalyzer(unittest.TestCase):
    def synthetic(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "stack-demo.txt")
        lines = [
            "STK a=$0100 pc=$F140 f=3",                       # boot: ignored
            "STK a=$01EB pc=$A575 f=200",
            "STK a=$01EF pc=$A573 f=201",
            "VBIE s=$F9 f=300 vp=256 ipc=$A4BA",              # 6 bytes in use, main idle, a valid instruction
            "VBIE s=$F5 f=310 vp=256 ipc=$B124",              # 10 bytes: the main program is 4 deep
            "FILL s=$EF f=320 vp=258", "FILL s=$EF f=320 vp=259",     # 16 bytes in use: one event (two iterations)
            "DLI1E s=$EC f=320 vp=39 ipc=$B100",              # 19 bytes inside FillPlayerPages
            "DLI2E s=$FC f=321 vp=87 ipc=$A6E0",
            "VBIX s=$F9 f=321 vp=60",
            "FILL s=$EF f=330 vp=258",                        # a second event
            "DLI1E s=$FC f=330 vp=39 ipc=$B000",              # not inside the fill range
            "VBIX s=$F9 f=331 vp=60",
            "DLI1E s=$FC f=340 vp=39 ipc=$E4AA",              # inside the OS
        ]
        with open(p, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        return p

    def test_summary_of_a_synthetic_log(self):
        p = self.synthetic()
        L, depth, ent = SL.summary([p], ROM.ins, {f.name: PEAK[e] for e, f in F.items()})
        txt = "\n".join(L)
        self.assertEqual(depth, 0x200 - 0x1EB)
        self.assertEqual(sorted(ent["VBIE"]), [0xF5, 0xF9])
        self.assertIn("340 frames", txt)
        self.assertIn("lowest write $01EB = 21 bytes deep", txt)
        self.assertIn("VbiHandler  $A5FD        2 entries, bytes in use 6 to 10", txt)
        self.assertIn("16 bytes: 2 times", txt)                                             # two events, not three iterations
        self.assertIn("DliHandler1 1, bytes in use at entry 19", txt)                        # only the one inside $B0F1-$B111 counts
        self.assertIn("DliHandler2 0", txt)
        self.assertIn("0 (1 entries, pc $A4BA-$A4BA); 4 (1 entries, pc $B124-$B124)", txt)
        self.assertIn("instruction of the cartridge in 2 of 2 cases", txt)
        self.assertIn("BOUND BY CONSTRUCTION", txt)
        self.assertIn("= 28 bytes of 256", txt)
        self.assertIn("equal to the measurement", txt)

    def test_a_wrong_stack_layout_is_noticed(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "stack-bad.txt")
        with open(p, "w") as fh:
            fh.write("VBIE s=$F9 f=300 vp=256 ipc=$A4BB" + "\n")                           # $A4BB is not the start of an instruction
        L, depth, ent = SL.summary([p], ROM.ins, {f.name: PEAK[e] for e, f in F.items()})
        self.assertIn("instruction of the cartridge in 0 of 1 cases", "\n".join(L))


class Document(unittest.TestCase):
    def test_document_is_up_to_date(self):
        want = "\n".join(S.report()) + "\n"
        with open(os.path.join(ROOT, "docs", "28-stack.md"), encoding="utf-8", newline="") as fh:
            got = fh.read().replace("\r\n", "\n")
        self.assertEqual(got, want, "run: python -I tools/analyze_stack.py --write docs/28-stack.md")

    def test_measurement_exists_and_is_inside_the_page(self):
        ev = S.evidence()
        self.assertIsNotNone(ev, "run tools/run_stack_audit.ps1 and tools/analyze_stack_log.py --write analysis/evidence-stack-summary.txt")
        line = [x for x in ev if x.startswith("DEEPEST STACK USE SEEN")]
        self.assertTrue(line)
        n = int(line[0].split(":")[1].split()[0])
        self.assertLess(n, 256)
        self.assertGreater(n, 16)
        txt = chr(10).join(ev)
        self.assertIn("equal to the measurement", txt)                                      # the model predicts the measured deepest case
        self.assertIn("= 28 bytes of 256", txt)
        self.assertIn("DliHandler2 0", txt)
        self.assertIn("inside a display-list handler ($A573-$A5FC): 0 of", txt)

    def test_the_two_display_lists_set_the_two_handlers(self):
        """SetDisplayList writes the display list and VDSLST together; the game screen uses handler 1, the title screen handler 2"""
        d = ROM.data
        self.assertEqual(d[0xA499 - 0xA000:0xA49C - 0xA000], bytes([0xA0, 0x73, 0x20]))         # ldy #$73 / jsr
        self.assertEqual(ROM.ins[0xA49B][1:], ("jsr", "abs", 0xA6B5))
        self.assertEqual(d[0xA61F - 0xA000:0xA622 - 0xA000], bytes([0xA0, 0xCE, 0x20]))         # ldy #$CE / jsr
        self.assertEqual(ROM.ins[0xA621][1:], ("jsr", "abs", 0xA6B5))
        self.assertEqual(F[BY["DliHandler1"]].entry, 0xA573)
        self.assertEqual(F[BY["DliHandler2"]].entry, 0xA5CE)

    def test_the_bound_does_not_depend_on_the_measurement_of_a_single_run(self):
        self.assertEqual(PEAK[BY["Start"]] + 6 + PEAK[BY["VbiHandler"]] + 3 + PEAK[BY["DliHandler2"]], 28)


if __name__ == "__main__":
    unittest.main()
