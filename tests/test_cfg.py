"""Stage 33: tests of tools/analyze_cfg.py and of docs/26-control-flow-graphs.md.  Run:  python -I tests/test_cfg.py"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import analyze_cfg as CFG  # noqa: E402
import analyze_functions as AF  # noqa: E402
import disasm6502 as D  # noqa: E402

ROM, F, G = CFG.analyse()
AF.solve(ROM, F)
BY = {f.name: e for e, f in F.items()}


class Blocks(unittest.TestCase):
    def test_blocks_partition_the_body(self):
        for e, g in G.items():
            seen = []
            for seq in g.blocks.values():
                seen += seq
            self.assertEqual(sorted(seen), sorted(F[e].body), F[e].name)
            self.assertEqual(len(seen), len(set(seen)), F[e].name)

    def test_blocks_are_straight_line(self):
        for e, g in G.items():
            for l, seq in g.blocks.items():
                for a, b in zip(seq, seq[1:]):
                    self.assertEqual(a + ROM.ins[a][0], b)
                    self.assertEqual(ROM.succ(a), [b])
                    self.assertNotIn(b, g.blocks, "%s $%04X" % (F[e].name, b))

    def test_every_block_is_reachable_from_the_entry(self):
        for e, g in G.items():
            seen, work = set(), [g.entry]
            while work:
                n = work.pop()
                if n not in seen:
                    seen.add(n)
                    work.extend(g.out[n])
            self.assertEqual(seen, set(g.blocks), F[e].name)

    def test_entry_has_a_block_and_no_block_starts_mid_instruction(self):
        for e, g in G.items():
            self.assertIn(e, g.blocks)
            for l in g.blocks:
                self.assertIn(l, ROM.ins)


class Edges(unittest.TestCase):
    def test_edges_match_the_instruction_successors(self):
        for e, g in G.items():
            for l, seq in g.blocks.items():
                want = sorted(s for s in ROM.succ(seq[-1]) if s in F[e].body)
                self.assertEqual(sorted(b for a, b, k in g.edges if a == l), want, "%s $%04X" % (F[e].name, l))

    def test_edge_targets_are_blocks(self):
        for e, g in G.items():
            for a, b, k in g.edges:
                self.assertIn(a, g.blocks)
                self.assertIn(b, g.blocks)

    def test_exit_blocks_end_in_rts_rti_or_a_jump_out(self):
        for e, g in G.items():
            for l in g.exits:
                last = g.blocks[l][-1]
                m = ROM.ins[last][1]
                self.assertTrue(m in ("rts", "rti") or (m == "jmp" and ROM.ins[last][3] not in F[e].body), "%s $%04X" % (F[e].name, l))

    def test_exits_agree_with_the_function_table(self):
        """RTS / RTI exit blocks = the exits counted in the function table; the only other exits are JMPs out of the routine (the interrupt handler that chains to the OS)."""
        for e, g in G.items():
            n = sum(1 for l in g.exits if ROM.ins[g.blocks[l][-1]][1] in ("rts", "rti"))
            self.assertEqual(n, sum(F[e].exits.values()), F[e].name)
        self.assertEqual({F[e].name for e, g in G.items() for l in g.exits if ROM.ins[g.blocks[l][-1]][1] == "jmp"}, {"VbiHandler"})


class Loops(unittest.TestCase):
    def test_back_edges_are_loops_of_the_function_table(self):
        """Every natural loop is a backward branch of the table; a decided branch can remove one, so back edges <= loops."""
        for e, g in G.items():
            self.assertLessEqual(len(g.back), len(F[e].loops), F[e].name)

    def test_back_edges_go_backward_and_target_a_dominator(self):
        for e, g in G.items():
            for a, b in g.back:
                self.assertIn(b, g.dom[a])

    def test_irreducible_graphs_are_the_known_six(self):
        """A loop entered at two places through an always-taken `lda #imm / bne`: a property of the code, listed in the document."""
        self.assertEqual(sorted(F[e].name for e, g in G.items() if not g.reducible),
                         ["FrameDispatch", "FrightenedSound", "FrightenedTick", "GhostBehaviour", "MovePacMan", "SteerToTarget"])
        for e, g in G.items():
            for a, b in g.bad:
                self.assertNotIn(b, g.dom[a])

    def test_complexity(self):
        for e, g in G.items():
            self.assertEqual(g.cc, len(g.edges) - len(g.blocks) + 2)
            self.assertGreaterEqual(g.cc, 1)


class Known(unittest.TestCase):
    def test_start_never_returns(self):
        self.assertEqual(G[BY["Start"]].exits, []) if "Start" in BY else None

    def test_interrupt_handlers_end_in_rti(self):
        for n in ("DliHandler1", "DliHandler2"):
            g = G[BY[n]]
            self.assertTrue(g.exits)
            for l in g.exits:
                self.assertEqual(ROM.ins[g.blocks[l][-1]][1], "rti")


class Document(unittest.TestCase):
    def test_document_is_up_to_date(self):
        want = "\n".join(CFG.report(ROM, F, G)) + "\n"
        got = open(os.path.join(ROOT, "docs", "26-control-flow-graphs.md"), encoding="utf-8", newline="").read().replace("\r\n", "\n")
        self.assertEqual(got, want, "docs/26-control-flow-graphs.md is out of date: python -I tools/analyze_cfg.py --write docs/26-control-flow-graphs.md")


if __name__ == "__main__":
    unittest.main()
