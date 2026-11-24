"""Stage 58: tests of tools/analyze_states.py and docs/34-state-transitions.md.  Run:  python -I tests/test_states.py   (the raw logs are local; the tests read analysis/evidence-states-summary.txt)"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_states as S  # noqa: E402


class Rules(unittest.TestCase):
    def test_every_rule_names_an_instruction_that_writes_the_variable(self):
        w, rom, F, owner = S.static_writers()
        by = {(x["var"], x["pc"]): x for x in w}
        for var, froms, to, pcs, text in S.RULES:
            for pc in pcs:
                self.assertIn((var, pc), by, "%s $%04X" % (var, pc))

    def test_constants_and_increments_agree_with_the_code(self):
        w, rom, F, owner = S.static_writers()
        by = {(x["var"], x["pc"]): x for x in w}
        for var, froms, to, pcs, text in S.RULES:
            for pc in pcs:
                x = by[(var, pc)]
                if x["value"].startswith("$"):
                    self.assertTrue(isinstance(to, int) and to == int(x["value"][1:], 16), "%s $%04X stores %s, the rule says %r" % (var, pc, x["value"], to))
                elif x["value"] == "+1":
                    self.assertTrue(to == "+1" or (isinstance(to, int) and froms is not None and all(f + 1 == to for f in froms)), "%s $%04X" % (var, pc))

    def test_every_variable_has_rules_and_every_store_has_a_rule(self):
        w, rom, F, owner = S.static_writers()
        ruled = {(v, pc) for v, f, t, pcs, x in S.RULES for pc in pcs}
        for a, name, size, d in S.STATES:
            self.assertTrue(any(r[0] == name for r in S.RULES), name)
        missing = [(x["var"], hex(x["pc"])) for x in w if (x["var"], x["pc"]) not in ruled and x["pc"] not in (0xA47B, 0xA4E2)]
        # the stores that are not rules of their own: the restart clear ($A47B, a BULK_CLEARS entry) and the pause toggle (rules for both values)
        self.assertEqual(missing, [])

    def test_explain_notices_a_transition_no_rule_allows(self):
        self.assertTrue(S.explain("GameState", 2, 3, 0xA70A))
        self.assertTrue(S.explain("GhostState", 0x08, 0x10, 0xB895))
        self.assertTrue(S.explain("FrightenPhase", 5, 6, 0xAFB6))
        self.assertTrue(S.explain("DeathState", 6, 0, 0xADB4))                  # the board set-up clears it
        self.assertFalse(S.explain("GameState", 3, 2, 0xA70A))
        self.assertFalse(S.explain("GhostState", 0x08, 0x20, 0xB895))
        self.assertFalse(S.explain("DeathState", 1, 3, 0xAE57))
        self.assertFalse(S.explain("FrightenPhase", 5, 7, 0xAFB6))


class Live(unittest.TestCase):
    def test_summary(self):
        trans, rc, bulk, unexpl, nwrites, lines = S.read_summary()
        txt = "\n".join(lines)
        self.assertEqual(unexpl, 0)
        self.assertIn("rules of the code: 68, seen in the sessions: 68, not seen: 0", txt)
        self.assertNotIn("NOT SEEN", txt)
        self.assertGreater(nwrites, 200000)
        self.assertIn("20 harness logs", lines[0])
        # every rule has a count in the summary
        self.assertEqual(sum(len(v) for v in rc.values()), len(S.RULES))
        for var, idx in rc.items():
            for i, c in idx.items():
                self.assertEqual(S.RULES[i][0], var)
                self.assertGreater(c, 0, "%s rule %d" % (var, i))

    def test_known_sequences(self):
        trans, rc, bulk, unexpl, nwrites, lines = S.read_summary()
        self.assertEqual(sorted(trans["DeathState"]), [(0, 1), (1, 2), (2, 3), (3, 4), (4, 3), (4, 5), (5, 6), (6, 0)])
        self.assertEqual(sorted(trans["GameState"]), [(0, 1), (0, 3), (0, 4), (1, 2), (2, 0), (2, 3), (3, 0), (4, 0), (4, 3)])
        self.assertEqual(sorted(trans["TurnSwitchState"]), [(0, 1), (0, 2), (1, 3), (2, 3), (3, 0)])
        self.assertIn((0x44, 0x04), trans["GhostState"])
        self.assertIn((0x04, 0x02), trans["GhostState"])
        self.assertEqual(sorted(trans["TwoPlayers"]), [(0, 1), (1, 0)])


class Exactness(unittest.TestCase):
    """the relation of the code, found by running it (tools/check_state_rules.py, analysis/evidence-state-rules-summary.txt), against the rules and the sessions"""

    def setUp(self):
        self.lines, self.counts, self.ex = S.read_exact()

    def test_header(self):
        self.assertGreater(self.counts["calls"], 90000)
        self.assertEqual(self.counts["missing"], 0)                         # every pair of every rule was made by the code
        self.assertGreaterEqual(self.counts["sites"], 90)

    def test_every_rule_pair_is_a_pair_of_the_code(self):
        for rl in S.RULES:
            pairs = S.rule_pair_set(rl)
            for pc in rl[3]:
                e = self.ex.get((rl[0], pc))
                self.assertIsNotNone(e, "%s $%04X has no exact pairs" % (rl[0], pc))
                missing = {p for p in pairs if p not in e["f"] and p not in e["d"]}
                # a rule shared by several instructions lists the pairs of all of them
                others = set()
                for pc2 in rl[3]:
                    e2 = self.ex.get((rl[0], pc2), {"f": set(), "d": set()})
                    others |= e2["f"] | e2["d"]
                self.assertFalse({p for p in pairs if p not in others}, "%s %r" % (rl[0], rl[3]))

    def test_every_pair_the_code_makes_beyond_the_rules_has_an_argument(self):
        by = {}
        for rl in S.RULES:
            for pc in rl[3]:
                by.setdefault((rl[0], pc), set()).update(S.rule_pair_set(rl))
        for (name, pc), e in self.ex.items():
            al = set(by.get((name, pc), set()))
            dom = set(S.DOMAIN[name])
            bulk = any(pc == cpc and any(a == S.ADDR_OF_NAME[name] for a in range(lo, hi + 1)) for cpc, lo, hi, t in S.BULK_CLEARS) or pc in S.BOOT_PCS
            extra = {p for p in (e["f"] | e["d"]) if p not in al and p[0] in dom}
            if bulk:
                extra = {p for p in extra if p[1] != 0}
            if extra:
                self.assertIn((name, pc), S.EXTRA_PAIRS_SITES, "%s $%04X makes %r that no rule allows and no argument explains" % (name, pc, sorted(extra)[:4]))
        for key, note in S.EXTRA_PAIRS_SITES.items():
            self.assertGreater(len(note), 40, key)

    def test_every_transition_seen_live_is_made_by_the_code(self):
        live = S.live_pairs()
        for (name, pc), pairs in live.items():
            e = self.ex.get((name, pc))
            self.assertIsNotNone(e, "%s $%04X was seen live but the exactness run never made a store there" % (name, pc))
            for p in pairs:
                self.assertTrue(p in e["f"] or p in e["d"], "%s $%04X %02X -> %02X seen live, not made by the interpreter" % (name, pc, p[0], p[1]))

    def test_specific_pairs(self):
        self.assertIn((0x04, 0x84), self.ex[("GhostState", 0xB40A)]["f"] | self.ex[("GhostState", 0xB40A)]["d"])      # a pellet eaten while a ghost is in state $04: the code makes 04 -> 84
        self.assertEqual(self.ex[("GhostState", 0xA800)]["f"] >= {(0, 1)}, True)
        self.assertNotIn((0, 1), self.ex[("FrightenPhase", 0xAFB6)]["f"] | self.ex[("FrightenPhase", 0xAFB6)]["d"])  # the frightened tick returns before the increment at phase 0


class Proof(unittest.TestCase):
    """the abstract-search proof (tools/prove_state_rules.py, analysis/raw-logs/proof-slice-*.json, analysis/evidence-state-proof-summary.txt)"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import prove_state_rules as P
        cls.P = P
        cls.res = {n: P.load(n) for n in P.SLICES}

    def test_every_slice_has_a_result_and_every_state_variable_is_followed(self):
        followed = set()
        for r in self.res.values():
            followed |= {S.ADDR[a][0] for a in r["tracked"]}
        self.assertEqual(followed, {n for a, n, s, d in S.STATES})

    def test_no_store_that_no_rule_allows_and_none_of_an_unknown_value(self):
        for n, r in self.res.items():
            extras, unknowns, race, imprecise = self.P.classify(r)
            self.assertEqual(extras, [], n)
            self.assertEqual(unknowns, [], n)

    def test_the_only_race_is_the_ghost_0_increment(self):
        for n, r in self.res.items():
            extras, unknowns, race, imprecise = self.P.classify(r)
            self.assertTrue(all((x[0], x[2]) == ("GhostState", 0xA800) for x in race), n)
            if n != "G0":
                self.assertEqual(race, [], n)
        self.assertEqual(len(self.P.classify(self.res["G0"])[2]), 255)
        self.assertIn(("GhostState", 0xA800), S.RACE_ONLY)

    def test_the_only_imprecision_is_the_one_explained(self):
        found = []
        for n, r in self.res.items():
            found += [(n, x[0], x[2], x[3], x[4]) for x in self.P.classify(r)[3]]
        self.assertEqual(found, [("G0", "WaitState", 0xA818, 0, 1)])
        r_events = {(a, pc, o, nw) for a, pc, o, nw in self.res["R"]["events"]}
        self.assertNotIn((0x24, 0xA818, 0, 1), r_events)

    def test_every_change_of_the_real_sessions_is_inside_the_abstract_result(self):
        """soundness against the real game: each (old, new) pair of each state variable that the 20 sessions made is among the stores of the abstract search (the one exception is the boot step GameState 0 -> 1, which happens before the key loop the search starts at)"""
        strans = S.read_summary()[0]
        proof = {}
        for r in self.res.values():
            for a, pc, o, nw in r["events"]:
                if o is not None and nw is not None and o != nw:
                    proof.setdefault(S.ADDR[a][0], set()).add((o, nw))
        missing = [(v, o, n) for v, d in strans.items() for (o, n) in d if (o, n) not in proof.get(v, set())]
        self.assertEqual(missing, [("GameState", 0, 1)])

    def test_ghost_pellet_pair_04_84_is_reached(self):
        for n in ("G1", "G2", "G3"):
            self.assertIn(("GhostState", 0xB40A, 0x04, 0x84), {(S.ADDR[a][0], pc, o, nw) for a, pc, o, nw in self.res[n]["events"]})

    def test_the_evidence_file_matches_the_results(self):
        with open(os.path.join(ROOT, "analysis", "evidence-state-proof-summary.txt"), encoding="utf-8") as fh:
            have = fh.read()
        L = self.P.report([self.res[n] for n in self.P.SLICES])
        L.insert(1, "slices not finished (no result yet, so nothing is claimed for them): none")
        self.assertEqual(have.replace("\r\n", "\n"), "\n".join(L) + "\n", "run: python -I tools/prove_state_rules.py --write analysis/evidence-state-proof-summary.txt")
        self.assertIn("totals over 11 slices: stores that no rule allows: 0; stores of an unknown value: 0; race-only stores: 255", have)
        self.assertIn("slices not finished (no result yet, so nothing is claimed for them): none", have)


class Document(unittest.TestCase):
    def test_document_is_current(self):
        with open(os.path.join(ROOT, "docs", "34-state-transitions.md"), encoding="utf-8", newline="") as fh:
            have = fh.read().replace("\r\n", "\n")
        self.assertEqual(have, "\n".join(S.doc_lines()) + "\n", "run: python -I tools/analyze_states.py --doc docs/34-state-transitions.md")
        self.assertNotIn("NOT YET RUN", have)
        self.assertNotIn("**not seen**", have)


if __name__ == "__main__":
    unittest.main()
