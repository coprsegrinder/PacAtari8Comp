"""Stage 50: tests of tools/analyze_constants.py and docs/31-constants-algorithms.md.  Run:  python -I tests/test_constants.py"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_constants as K  # noqa: E402

ROM, F, OWNER, CEN = K.census()
NAMES = {f.name for f in F.values()}


class Census(unittest.TestCase):
    def test_every_immediate_operand_is_in_the_census(self):
        n = sum(1 for a, (sz, m, mode, op) in ROM.ins.items() if mode == "imm")
        self.assertEqual(sum(len(v) for v in CEN.values()), n)

    def test_every_census_routine_exists(self):
        self.assertLessEqual(set(CEN), NAMES)

    def test_kinds(self):
        kinds = {k for v in CEN.values() for a, k, val, s in v}
        self.assertEqual(kinds, {"cmp", "assign", "logic", "arith", "load"})

    def test_subjects_use_catalogue_names(self):
        subjects = [s for v in CEN.values() for a, k, val, s in v if k in ("cmp", "assign")]
        self.assertFalse([s for s in subjects if s.startswith("zp_")])

    def test_a_few_known_constants(self):
        d = {(rn, a): (k, val, s) for rn, v in CEN.items() for a, k, val, s in v}
        self.assertIn(("assign", 0x96, "GhostTimer,x"), [(k, val, s) for a, k, val, s in CEN["GhostSelectPatrol"]])
        self.assertIn(("assign", 0xA0, "ChaseTimer"), [(k, val, s) for a, k, val, s in CEN["GhostSeesPacMan"]])
        self.assertIn(("assign", 0x42, "GhostState,x"), [(k, val, s) for a, k, val, s in CEN["GhostEaten"]])


class Named(unittest.TestCase):
    def test_every_named_constant_is_used_where_it_says(self):
        imm = {rn: {val for a, k, val, s in v} for rn, v in CEN.items()}
        for name, val, meaning, routines, chap in K.NAMED:
            self.assertTrue(routines, name)
            for r in routines:
                self.assertIn(r, NAMES, "%s: %s" % (name, r))
                self.assertIn(val, imm.get(r, set()), "%s ($%02X) not an immediate in %s" % (name, val, r))

    def test_names_and_values_are_unique(self):
        names = [n[0] for n in K.NAMED]
        self.assertEqual(len(names), len(set(names)))
        pairs = [(n[0], n[1]) for n in K.NAMED]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_door_and_tunnel_facts(self):
        d = {n[0]: n[1] for n in K.NAMED}
        self.assertEqual((d["DOOR_X"], d["DOOR_Y"]), (124, 100))
        self.assertEqual((d["TUNNEL_X_LEFT"], d["TUNNEL_X_RIGHT"]), (0x2A, 0xCA))
        self.assertEqual(d["MAZE_ROW_STRIDE"], 40)
        self.assertEqual(d["BONUS_TIME_HI"] * 256 + d["BONUS_TIME_LO"], 0x02C0)
        self.assertEqual((d["BONUS_FIRST_DOTS"], d["BONUS_SECOND_DOTS"]), (80, 160))
        self.assertEqual(d["PATROL_TIME"] * 8, 1200)                                      # 150 x 8 jiffies = 20 s at 60 Hz


class Random(unittest.TestCase):
    def test_random_is_read_at_exactly_three_places(self):
        sites = sorted(a for a, (n, m, mode, op) in ROM.ins.items() if mode in ("abs", "abx", "aby") and op == 0xD20A)
        self.assertEqual(sites, [0xB859, 0xB9E1, 0xB9F4])
        self.assertEqual([F[OWNER[a]].name for a in sites], ["GhostSelectPatrol", "SteerToTarget", "SteerToTarget"])


class Algorithms(unittest.TestCase):
    def test_every_routine_belongs_to_an_algorithm(self):
        rtn = K.routine_algorithm()
        missing = [n for n in NAMES if n not in rtn and n not in K.EXTRA_ROUTINES]
        self.assertEqual(missing, [])

    def test_algorithm_routines_exist_and_ids_are_unique(self):
        ids = [a[0] for a in K.ALGORITHMS]
        self.assertEqual(len(ids), len(set(ids)))
        for aid, name, routines, rule, tables, evidence, status in K.ALGORITHMS:
            for r in routines:
                self.assertIn(r, NAMES, "%s: %s" % (aid, r))
            self.assertTrue(rule and evidence and status, aid)

    def test_files_named_as_evidence_exist(self):
        for aid, name, routines, rule, tables, evidence, status in K.ALGORITHMS:
            for path in re.findall(r"`((?:tests|tools)/[A-Za-z0-9_./]+)`", evidence):
                self.assertTrue(os.path.exists(os.path.join(ROOT, path)), "%s: %s" % (aid, path))

    def test_the_modelled_algorithms_are_marked(self):
        modelled = {a[0] for a in K.ALGORITHMS if "MODEL" in a[6]}
        self.assertEqual(modelled, {"A%02d" % i for i in range(1, 23)})                  # all 22 since OV-58


class Document(unittest.TestCase):
    def test_document_is_current(self):
        path = os.path.join(ROOT, "docs", "31-constants-algorithms.md")
        with open(path, encoding="utf-8", newline="") as fh:
            have = fh.read().replace("\r\n", "\n")
        self.assertEqual(have, "\n".join(K.report()) + "\n", "run: python -I tools/analyze_constants.py --write docs/31-constants-algorithms.md")
        self.assertNotIn("NOT FOUND", have)
        self.assertNotIn("**NONE**", have)


if __name__ == "__main__":
    unittest.main()
