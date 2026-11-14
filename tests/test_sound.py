"""Evidence tests for the sounds (docs/22-sound.md, OPEN-VERIFICATION.md OV-10).  Run:  python -I tests/test_sound.py
Static: the code bytes of the sound routines, the census of every instruction that stores to the POKEY page ($D200-$D20F), and the Python ports of the routines
(tools/analyze_sound_events.py) that the live traces are compared with call by call (analysis/evidence-sound-events-registers-summary.txt).
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_sound_events as E  # noqa: E402
import sound_inputs as SI  # noqa: E402
import decode_streams as S  # noqa: E402

rd = S.rd
at = lambda a, n: bytes(rd(a + i) for i in range(n))
hx = bytes.fromhex

# every store (STA/STX/STY absolute, STA absolute,X/Y) to $D200-$D20F in the ROM: 2 setup writes (IRQEN, SKCTL) and the 31 sound sites
POKEY_STORES = [0xA453, 0xA45D, 0xA617, 0xA7E2, 0xA7E8, 0xA7ED, 0xA7F2, 0xA8EE, 0xABFE, 0xAC01, 0xAE94, 0xAE99, 0xAEAD, 0xAEB2, 0xAED2, 0xAED7, 0xB021, 0xB028, 0xB042, 0xB058, 0xB05B, 0xB060, 0xB072, 0xB075, 0xB078, 0xB07D, 0xB080, 0xB088, 0xB0DD, 0xB0E2, 0xB0EA, 0xB546, 0xB54B]
SOUND_SITES = [a for a in POKEY_STORES if a not in (0xA453, 0xA45D)]


class Code(unittest.TestCase):
    def test_sound_routines(self):
        self.assertEqual(at(0xABC9, 60), hx("a6f7f037a5f8a0a5e007b00fc9b4f005186905d01ee6f7a0a3d018e009d004e6f7d002a0a338c978d007a90085f7a8f002e90585f88d00d28c01d260"))      # Sub_ABC9 (bonus item sound)
        self.assertEqual(at(0xAFD7, 85), hx("a5e4d00ea90585e3a90285e2e6e4a99085e1a5e2c901d01fa5e1c990d012a5e3c903d004a90585e3c6e3a90285e2d01318a5e16910d011a5e1c940d006a90185e2d0ed38a5e1e91085e18d02d2a5e309a08d03d260"))      # Sub_AFD7 (frightened sound)
        self.assertEqual(at(0xB02C, 29), hx("a5f3d006a90c85f3d008c917d004a90c85f3e6f3a5f38d02d2a9a4d0df"))      # Sub_B02C (eyes returning sound)
        self.assertEqual(at(0xB049, 157), hx("c6e6f01a38a5e7e90485e7c910f02d8d00d28d06d2a9848d08d2a9a4d019a90285e638a5e7e90385e78d00d28d04d28d06d2a9a88d05d28d07d2d05d20e6b08d08d285e585a784e8a92a8dc702a9118d6f02a203bdc002c9dcf004ca10f660a90c9dc0028d1ed0a90085a72079b1e6a84c3ab3a5f4f025a6f5e006d008a90085f485f5f014a5f6d006bdd8bc4cdbb0bddfbce6f58d00d2a9a48d01d260"))      # LB049..LB0E5 (ghost eaten sweep and its end)
        self.assertEqual(at(0xB0E6, 11), hx("a007a9009900d28810fa60"))      # ClearPokeyRegisters
        self.assertEqual(at(0xA8EC, 15), hx("a9008d03d2e6e5a98485e7a90285e6"))      # ghost eaten start $A8EC

    def test_census_of_pokey_stores(self):
        found = []
        for i in range(len(S.ROM) - 2):
            if S.ROM[i + 2] == 0xD2 and S.ROM[i] in (0x8D, 0x8E, 0x8C, 0x9D, 0x99) and S.ROM[i + 1] <= 0x0F:
                found.append(0xA000 + i)
        self.assertEqual(found, POKEY_STORES)
        self.assertEqual(len(SOUND_SITES), 31)

    def test_no_sound_code_for_extra_life_or_board_change(self):
        # the extra life ($B487: INC lives, JSR Sub_AD15) and the board end (AdvanceLevel, $AC75) contain no store to the POKEY page
        for start, n in ((0xB487, 8), (0xAC75, 40)):
            code = at(start, n)
            for i in range(len(code) - 2):
                self.assertFalse(code[i + 2] == 0xD2 and code[i] in (0x8D, 0x8E, 0x8C, 0x9D, 0x99), "POKEY store at $%04X" % (start + i))


class Ports(unittest.TestCase):
    def test_bonus_sequence(self):
        seq = E.bonus_sequence()
        self.assertEqual(len(seq), 31)
        self.assertEqual(seq[0], (0x7D, 0xA5))
        self.assertEqual([a for a, y in seq[:12]], [0x7D + 5 * i for i in range(12)])      # rises to $B4 with AUDC $A5
        self.assertEqual([(a, y) for a, y in seq[12:18]], [(0xB4, 0xA3)] * 6)               # holds $B4 for 6 more calls (7 with the last rising one) with AUDC $A3
        self.assertEqual(seq[18], (0xAF, 0xA3))                                           # then falls in steps of 5
        self.assertEqual(seq[-2], (0x78, 0xA3))
        self.assertEqual(seq[-1], (0x00, 0x00))                                            # the last call silences channel 1

    def test_ghost_eaten_frames(self):
        g = E.ghost_eaten_frames()
        self.assertEqual(len(g), 34)
        self.assertEqual(g[0], {3: 0})                                                      # A8EE: AUDC2 := 0
        self.assertEqual(g[1], {0: 0x80, 6: 0x80, 8: 0x84, 7: 0xA4, 1: 0xA4})              # first call: -4 path, high-pass AUDCTL $84
        self.assertEqual(g[2], {0: 0x7D, 4: 0x7D, 6: 0x7D, 5: 0xA8, 7: 0xA8, 1: 0xA8})     # second call: -3 path, channels 3 and 4 and 1 at volume 8
        self.assertEqual(g[-1], {**{r: 0 for r in range(8)}, 8: 0})                         # ClearPokeyRegisters and AUDCTL := 0

    def test_frightened_wobble(self):
        f = E.Frightened()
        seq = [f.call() for _ in range(50)]
        self.assertEqual([a for a, _ in seq[:10]], [0x80, 0x70, 0x60, 0x50, 0x40, 0x50, 0x60, 0x70, 0x80, 0x90])
        self.assertEqual([c & 15 for _, c in seq[0::10]], [5, 4, 3, 4, 3])                  # volume per 10-call period
        self.assertTrue(all(c >> 4 == 0xA for _, c in seq))

    def test_eyes_sequence(self):
        e = E.Eyes()
        seq = [e.call() for _ in range(24)]
        self.assertEqual([a for a, _ in seq[:12]], list(range(13, 24)) + [13])
        self.assertTrue(all(c == 0xA4 for _, c in seq))
        e.reset()
        self.assertEqual(e.call(), (13, 0xA4))


class Inputs(unittest.TestCase):
    def test_no_sound_routine_reads_the_level(self):
        """OV-11: no sound routine reads Level ($30/$31), StartLevel ($1B) or any table by level; their inputs are their own state variables, RTCLOK2 and (siren step) the dot counter."""
        for name, lo, hi in SI.ROUTINES:
            addrs = {a for (a, kind) in SI.reads(lo, hi)}
            self.assertFalse(addrs & {0x30, 0x31, 0x1B}, "%s reads a level variable" % name)
            # the only absolute-addressed reads are the tune and sweep tables (constants, indexed by step, not by level)
            for (a, kind), sites in SI.reads(lo, hi).items():
                if a >= 0x100:
                    self.assertIn(a, (0xBC50, 0xBC90, 0xBCD8, 0xBCDF), "%s reads $%04X" % (name, a))

    def test_siren_step_comes_from_the_dot_counter(self):
        # Sub_B5C7: zp_9C := 2 / 3 / 4 / 5 from the dots eaten (zp_34), 5 when the high byte zp_36 is non-zero
        self.assertEqual(at(0xB5D3, 44), hx("a62bb536f009a2032016b6a905d01db534c9f0b0f1c9e09009a2022016b6a904d00ac9b09004a903d002a902"))
        self.assertEqual({E.siren_step(d, 0) for d in range(0, 0xB0)}, {2})
        self.assertEqual({E.siren_step(d, 0) for d in range(0xB0, 0xE0)}, {3})
        self.assertEqual({E.siren_step(d, 0) for d in range(0xE0, 0xF0)}, {4})
        self.assertEqual({E.siren_step(d, 0) for d in range(0xF0, 0x100)}, {5})
        self.assertEqual(E.siren_step(0, 1), 5)

    def test_siren_port(self):
        s = E.Siren()
        self.assertEqual(s.call(0), (0x28, 0xA1))                 # the first call after the board set-up: zp_9C is still 0
        up = [s.call(2)[0] for _ in range(12)]
        self.assertEqual(up, list(range(0x2A, 0x42, 2)))           # up in steps of 2 to $40 (the turn is taken when zp_DE >= $40: it reaches $40, the next call goes down)
        down = [s.call(2)[0] for _ in range(13)]
        self.assertEqual(down[:3], [0x3E, 0x3C, 0x3A])
        for step, period, lo, hi in ((2, 26, 38, 64), (3, 18, 37, 64), (4, 14, 36, 64), (5, 12, 35, 65)):
            t = E.Siren()
            t.call(0)
            seen, vals = {}, []
            for i in range(400):
                st = (t.DE, t.DF)
                if st in seen:
                    self.assertEqual(i - seen[st], period, "step %d" % step)
                    break
                seen[st] = i
                vals.append(t.call(step)[0])
            self.assertEqual((min(vals), max(vals)), (lo, hi), "step %d" % step)


if __name__ == "__main__":
    unittest.main()
