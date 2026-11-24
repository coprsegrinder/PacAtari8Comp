"""Tests of tools/absint6502.py, the abstract interpreter that proves the state-transition rules (stage 58).  Run:  python -I tests/test_absint.py

The proof is only as good as the interpreter, so it is tested against the concrete interpreter (tools/cpu6502.py, itself compared with the ROM's own start-up and with 429 tests):
 - SOUNDNESS: the real code, run concretely from a random memory (the OV-58 contexts: random zero page, state variables in their domains), ends with followed values and makes stores that the abstract run from the same
   followed values contains (abstract = every concrete outcome, whatever the unknown bytes are);
 - the abstract machine's own pieces: flags, comparison refinement, the stack, a skipped routine's results, a store with an unknown index;
 - the assumptions the proof states: the table area $0600-$07FF is never written after the expansion; no indirect store aims into the zero page; the OS entry points are the two known ones.
"""
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import absint6502 as AB  # noqa: E402
import analyze_states as S  # noqa: E402
import algorithm_models as A  # noqa: E402
import algorithm_models6 as M6  # noqa: E402
import algorithm_models7 as M7  # noqa: E402
import cpu6502 as C  # noqa: E402

PROG = AB.Program()
ADDR = {n: a for a, n, s, d in S.STATES}
SLICE = [ADDR[n] for n in ("GameState", "IntroRequest", "PlayStarted", "StartTuneActive", "WaitState", "DeathState", "DeathAnimActive", "CountdownActive", "LevelComplete", "LevelEndStep", "PacFrozen", "EatPause", "CurrentPlayer")] + [0xCE]


def matches(conc, abstract_events):
    a, pc, old, new = conc
    return any(ea == a and epc == pc and eo in (old, None) and en in (new, None) for ea, epc, eo, en in abstract_events)


class Soundness(unittest.TestCase):
    def test_vertical_blank_handler_against_the_concrete_run(self):
        rng = random.Random(777)
        m_abs = AB.Machine(PROG, SLICE)
        base = A.started_machine()
        dom = {a: S.DOMAIN[S.ADDR[a][0]] for a in SLICE}
        checked = events = 0
        orig_wr = C.Machine.wr
        log = []

        def wr(self, a, v):
            if a in m_abs.idx and not (C.BASE <= a < self.rom_end):
                log.append((a, getattr(self, "_ipc", 0), self.mem[a], v & 0xFF))
            orig_wr(self, a, v)
        orig_step = C.Machine.step

        def step(self):
            self._ipc = self.pc
            orig_step(self)
        C.Machine.wr, C.Machine.step = wr, step
        try:
            for i in range(160):
                m = M6.prepare(base, rng)
                M7.frame_setup(m, rng, rng.choice(["game", "play", "title"]))
                for a in SLICE:
                    m.mem[a] = rng.choice(dom[a])
                m.random = [rng.randrange(256) for _ in range(12)]
                T_in = tuple(m.mem[a] for a in SLICE)
                del log[:]
                m.call(0xA5FD)
                T_out = tuple(m.mem[a] for a in SLICE)
                finals, ev, _ = m_abs.vbi(T_in)
                ok = any(all(f is None or f == t for f, t in zip(F, T_out)) for F in finals)
                self.assertTrue(ok, "concrete end state %r from %r is not in the abstract result" % (T_out, T_in))
                for e in log:
                    if e[2] != e[3]:
                        self.assertTrue(matches(e, ev), "concrete store %r not in the abstract stores" % (e,))
                        events += 1
                checked += 1
        finally:
            C.Machine.wr, C.Machine.step = orig_wr, orig_step
        self.assertEqual(checked, 160)
        self.assertGreater(events, 50)

    def test_key_loop_pass_against_the_concrete_run(self):
        """one pass of the key loop from $A4BA (with START / SELECT / OPTION / the space bar / the trigger, the restart included), no vertical-blank handler in it"""
        rng = random.Random(778)
        m_abs = AB.Machine(PROG, SLICE)
        base = A.started_machine()
        dom = {a: S.DOMAIN[S.ADDR[a][0]] for a in SLICE}
        orig_wr = C.Machine.wr
        orig_step = C.Machine.step
        log = []

        def wr(self, a, v):
            if a in m_abs.idx and not (C.BASE <= a < self.rom_end):
                log.append((a, getattr(self, "_ipc", 0), self.mem[a], v & 0xFF))
            orig_wr(self, a, v)

        def step(self):
            self._ipc = self.pc
            orig_step(self)
        C.Machine.wr, C.Machine.step = wr, step
        stores = 0
        try:
            for i in range(120):
                m = M6.prepare(base, rng)
                for a2, val in ((0x19, rng.choice([0, 1, 2, 3, 4])), (0x1A, rng.randrange(2)), (0x1B, rng.choice([0, 2, 4, 8])), (0x1E, rng.choice([0, 5])), (0x02F1, 0), (0x02FC, rng.choice([0x21, 0xFF])),
                                (0x0284, rng.choice([1, 1, 0])), (0x0285, 1), (0xD01F, rng.choice([7, 6, 5, 3, 4])), (0x9B, rng.randrange(2))):
                    m.mem[a2] = val
                for a in SLICE:
                    m.mem[a] = rng.choice(dom[a])
                m.mem[0x3C], m.mem[0x3D] = rng.randrange(256), 0x08 + rng.randrange(8)
                T_in = tuple(m.mem[a] for a in SLICE)
                del log[:]
                M6.run_key_loop(m)
                T_out = tuple(m.mem[a] for a in SLICE)
                # the abstract pass: from $A4BA until the next arrival there, no interrupt
                events = set()
                finals = []
                start = (0xA4BA, None, None, None, None, None, None, None, 0, (), T_in, None)
                seen = {}
                work = [start]
                first = True
                while work:
                    st = work.pop()
                    if not first and st[0] == 0xA4BA:
                        finals.append(st[AB.T_IDX])
                        continue
                    first = False
                    out = m_abs.step(st, events, False)
                    for s2 in out:
                        key = (m_abs.key(s2), m_abs.regs(s2))
                        if key not in seen:
                            seen[key] = 1
                            work.append(s2)
                self.assertTrue(any(all(f is None or f == t for f, t in zip(F, T_out)) for F in finals), "key loop: concrete end state %r from %r not in the abstract result %r" % (T_out, T_in, finals[:3]))
                for e in log:
                    if e[2] != e[3]:
                        self.assertTrue(matches(e, events), "key loop: concrete store %r not abstract" % (e,))
                        stores += 1
        finally:
            C.Machine.wr, C.Machine.step = orig_wr, orig_step
        self.assertGreater(stores, 30)


class Pieces(unittest.TestCase):
    def machine(self):
        return AB.Machine(PROG, [0x19, 0x2B])

    def run_code(self, start, code_regs=None):
        return None

    def test_compare_refines_the_register_on_the_equal_path(self):
        m = self.machine()
        # $A507 cmp #$07 / $A509 beq: A unknown -> on the equal path A = 7, on the other path the zero flag is 0
        st = (0xA507, None, None, None, None, None, None, None, 0, (), (0, 0), None)
        (after,) = m.step(st, set(), False)
        self.assertEqual(after[AB.CR], ("a", 7, "c"))
        outs = m.step((0xA509,) + after[1:], set(), False)
        eq = [o for o in outs if o[AB.Z] == 1]
        ne = [o for o in outs if o[AB.Z] == 0]
        self.assertEqual(len(eq), 1)
        self.assertEqual(len(ne), 1)
        self.assertEqual(eq[0][AB.A], 7)
        self.assertEqual(eq[0][AB.C], 1)
        self.assertIsNone(ne[0][AB.A])

    def test_a_known_flag_does_not_fork(self):
        m = self.machine()
        st = (0xA4BA, None, 3, None, None, None, None, None, 0, (), (0, 0), None)           # ldx #3
        (st2,) = m.step(st, set(), False)
        self.assertEqual((st2[AB.X], st2[AB.Z], st2[AB.N]), (3, 0, 0))

    def test_store_to_a_followed_variable_is_recorded(self):
        m = self.machine()
        ev = set()
        st = (0xA53B, 0, None, None, 0, 1, None, None, 0, (), (3, 1), None)                 # sta zp_19 with A = 0
        (st2,) = m.step(st, ev, False)
        self.assertEqual(st2[AB.T], (0, 1))
        self.assertEqual(ev, {(0x19, 0xA53B, 3, 0)})

    def test_store_with_an_unknown_index_forgets_the_followed_variables(self):
        m = self.machine()
        ev = set()
        st = (0xA4C3, 5, None, None, None, None, None, None, 0, (), (2, 1), None)           # sta zp_5E,x with X unknown
        (st2,) = m.step(st, ev, False)
        self.assertEqual(st2[AB.T], (None, None))
        self.assertGreater(m.havoc_count, 0)

    def test_a_skipped_call_keeps_the_preserved_registers_and_gives_the_known_results(self):
        m = self.machine()
        jsr = [a for a, (n, mn, mode, op) in PROG.ins.items() if mn == "jsr" and op == 0xB0E6][0]          # ClearPokeyRegisters: preserves X, returns A = 0 and Y = $FF
        self.assertIn(0xB0E6, m.skip)
        st = (jsr, 1, 2, 3, None, None, None, None, 0, (), (0, 0), None)
        outs = m.step(st, set(), False)
        self.assertEqual(len(outs), 1)
        self.assertEqual(outs[0][AB.PC], jsr + 3)
        self.assertEqual((outs[0][AB.A], outs[0][AB.X]), (0, 2))

    def test_an_executed_call_returns_to_the_caller_with_the_preserved_register(self):
        m = self.machine()
        jsr = [a for a, (n, mn, mode, op) in PROG.ins.items() if mn == "jsr" and op == 0xB590][0]          # MoveDelayTick reads CurrentPlayer (followed): executed, not skipped
        self.assertNotIn(0xB590, m.skip)
        st = (jsr, 1, 2, 3, None, None, None, None, 0, (), (0, 0), None)
        (inside,) = m.step(st, set(), False)
        self.assertEqual(inside[AB.PC], 0xB590)
        self.assertEqual(len(inside[AB.STK]), 3)
        rts = [a for a, (n, mn, mode, op) in PROG.ins.items() if mn == "rts" and PROG.owner[a] == 0xB590][0]
        st = (rts, None, 9, None, None, None, None, None, 0, inside[AB.STK], (0, 0), None)
        (back,) = m.step(st, set(), False)
        self.assertEqual(back[AB.PC], jsr + 3)
        self.assertEqual(back[AB.X], 2)                                                                  # the routine preserves X: the caller's value is back

    def test_a_skipped_routine_gives_its_known_results(self):
        m = AB.Machine(PROG, [0x19, 0x2B, 0xE5, 0xEA, 0xED])
        a, x, y, *_ = m.summary(0xB0E6)                                                      # ClearPokeyRegisters: A = 0 and Y = $FF on return
        self.assertEqual(a, 0)
        a, x, y, *_ = m.summary(0xB0F1)                                                      # ClearPlayerMemory: A = 0, X = 0
        self.assertEqual((a, x), (0, 0))


class Assumptions(unittest.TestCase):
    def test_no_instruction_writes_the_table_area(self):
        for a, (n, m, mode, op) in PROG.ins.items():
            if m in ("sta", "stx", "sty", "inc", "dec", "asl", "lsr", "rol", "ror") and mode in ("abs", "abx", "aby") and isinstance(op, int):
                self.assertFalse(0x0600 <= op <= 0x07FF or (mode != "abs" and op < 0x0600 and op + 255 >= 0x0600 and op >= 0x0500), "$%04X writes into $0600-$07FF" % a)

    def test_indirect_stores_use_the_pointers_of_docs_29(self):
        # the six pointer variables and the stores through them: SrcPtr/DstPtr ($3C-$3F), $38-$3B, $47/$48, MazePtr $80 (the zero-page pointers all point to RAM pages from $0200 on)
        ptrs = {a: op for a, (n, m, mode, op) in PROG.ins.items() if mode == "izy" and m in ("sta",)}
        self.assertTrue(ptrs)
        self.assertLessEqual({op for op in ptrs.values()}, {0x3E, 0x38, 0x3A, 0x47, 0x80})

    def test_the_only_os_entries_are_setvbv_and_xitvbv(self):
        os_calls = {(m, op) for a, (n, m, mode, op) in PROG.ins.items() if isinstance(op, int) and op >= 0xC000 and m in ("jsr", "jmp")}
        self.assertEqual(os_calls, {("jsr", 0xE45C), ("jmp", 0xE462)})


if __name__ == "__main__":
    unittest.main()
