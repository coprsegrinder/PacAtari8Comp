"""Stage 42: tests of tools/analyze_locals.py and of docs/27-local-variables.md.  Run:  python -I tests/test_locals.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_locals as LV  # noqa: E402
import analyze_variables as V  # noqa: E402

A, VARS, TEMP, CARRY, SINGLES, SUB, DEAD = LV.build()
F = A.F
BY = {f.name: e for e, f in F.items()}
SING = {name: (owner, cls) for first, n, name, kind, role, ev, owner, cls in SINGLES}


class Single(unittest.TestCase):
    def test_every_catalogue_local_is_classified_once(self):
        """the 28 LOCAL variables of docs/25 (one routine only) are exactly the single-routine variables here"""
        self.assertEqual(len(SINGLES), 28)
        self.assertEqual(len({s[2] for s in SINGLES}), 28)
        self.assertTrue(all(s[7] in ("TEMP", "STATIC", "OS", "DEAD") for s in SINGLES))

    def test_known_temporaries(self):
        for name, owner in (("JunctionTemp", "JunctionLookup"), ("BcdCarry", "AddToScore"), ("ClipMask", "ClipEntityAtTunnel"),
                            ("ClipCounter", "ClipEntityAtTunnel"), ("ClipPtr", "ClipEntityAtTunnel"), ("PopupMissilePtr", "GhostEaten"),
                            ("PopupPlayerPtr", "GhostEaten"), ("KeyValue", "Start")):
            self.assertEqual(SING[name], (BY[owner], "TEMP"), name)

    def test_known_state(self):
        for name in ("PlayStarted", "ExtraLifeFlag", "TuneStep", "HalfSpeedToggle", "MoveDelayCycle", "PatrolRoute", "SirenTone", "DeathStep", "LabelBlink", "PacWantedDir", "FrightenFlashTimer", "ChompPhase"):
            self.assertEqual(SING[name][1], "STATIC", name)

    def test_os_variable_is_never_a_temporary(self):
        self.assertEqual(SING["POKMSK"][1], "OS")

    def test_static_means_read_before_written_and_temp_means_not(self):
        for first, n, name, kind, role, ev, owner, cls in SINGLES:
            ue = bool(set(range(first, first + n)) & A.UE[owner])
            if cls == "STATIC":
                self.assertTrue(ue, name)
            if cls == "TEMP":
                self.assertFalse(ue, name)


class Shared(unittest.TestCase):
    def test_temporaries_are_not_live_in_or_out(self):
        for e, d in TEMP.items():
            for first in d:
                n = LV.VAR[first][0]
                bytes_ = set(range(first, first + n))
                self.assertFalse(bytes_ & A.UE[e], F[e].name)
                self.assertFalse(bytes_ & A.EL[e] & A.MAY[e], F[e].name)

    def test_no_temporary_is_read_by_an_interrupt_handler(self):
        isr = set()
        for e, f in F.items():
            if f.irq or f.name == "VbiHandler":
                isr |= A.UE[e]
        for e, d in TEMP.items():
            if F[e].irq or F[e].name == "VbiHandler":
                continue
            for first in d:
                self.assertFalse(set(range(first, first + LV.VAR[first][0])) & isr, F[e].name)

    def test_summaries_are_consistent(self):
        for e in F:
            if not any(A.is_exit(F[e], a) for a in F[e].body):
                continue                                              # Start never returns: 'written on every path to an exit' is vacuous
            self.assertLessEqual(A.MUST[e], A.MAY[e], F[e].name)       # a byte written on every path is written on some path
        # a routine that clears the sound registers reads nothing from the zero page
        self.assertEqual(A.UE[BY["ClearPokeyRegisters"]], frozenset())

    def test_scratch_2a_is_a_temporary_where_it_is_not_a_result(self):
        self.assertIn(0x2A, TEMP[BY["ExpandData"]])
        self.assertEqual(CARRY[BY["JunctionLookup"]][0x2A], "out")        # JunctionLookup hands the exit mask back in it


class Document(unittest.TestCase):
    def test_document_is_up_to_date(self):
        want = "\n".join(LV.report(*LV.build())) + "\n"
        with open(os.path.join(ROOT, "docs", "27-local-variables.md"), encoding="utf-8", newline="") as fh:
            got = fh.read().replace("\r\n", "\n")
        self.assertEqual(got, want, "run: python -I tools/analyze_locals.py --write docs/27-local-variables.md")


if __name__ == "__main__":
    unittest.main()
