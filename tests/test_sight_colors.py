"""Evidence tests for the small tables around $BBAB-$BBF7 (step C11). Run:  python -I tests/test_sight_colors.py
The live checks (6,069 sight tests, colour-register writes) are summarised in analysis/evidence-sight-colors-summary.txt.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import decode_streams as S  # noqa: E402
import sight_model as M  # noqa: E402

rd = S.rd
at = lambda a, n: bytes(rd(a + i) for i in range(n))
hx = bytes.fromhex
NIB, _ = S.split_nibbles(0xBE95)
J = [[NIB[0x60E - 0x600 + 10 * r + c] for c in range(10)] for r in range(10)]


def lst(base, off):
    out, k = [], 0
    while rd(base + off + k) != 0xFF:
        out.append(rd(base + off + k))
        k += 1
    return out


class SightData(unittest.TestCase):
    def test_layout_is_offset_tables_plus_lists(self):
        hoff = list(at(0xBBB8, 10))
        voff = list(at(0xBBD8, 10))
        self.assertEqual(hoff, [0, 12, 2, 6, 0, 6, 0, 9, 2, 12])
        self.assertEqual(voff, [0, 3, 10, 12, 17, 17, 12, 10, 3, 0])            # mirror-symmetric, one per junction column
        self.assertEqual(sorted(set(hoff)), [0, 2, 6, 9, 12])                   # exactly the starts of the five x lists
        self.assertEqual(sorted(set(voff)), [0, 3, 10, 12, 17])                 # exactly the starts of the five y lists
        self.assertEqual([lst(0xBBAB, o) for o in (0, 2, 6, 9, 12)], [[0x7C], [0x58, 0x7C, 0x9E], [0x58, 0x9E], [0x3C, 0xAC], []])
        self.assertEqual([lst(0xBBC2, o) for o in (0, 3, 10, 12, 17)],
                         [[0x64, 0x84], [0x38, 0x4C, 0x64, 0x84, 0x9C, 0xBC], [0x3C], [0x38, 0x5C, 0x9C, 0xBC], [0x4C, 0x74, 0x8C, 0xAC]])
        self.assertEqual(0xBBAB + 13 + 10 + 22, 0xBBD8)                           # lists, offsets, lists, then the second offset table

    def test_code_indexes_the_offset_tables_directly(self):
        # LDA $BBB8,Y / CMP #$FF / BEQ / CMP EntityX,X ... : no LDY offset, no base $BBAB (horizontal); same with $BBD8 (vertical)
        self.assertEqual(at(0xBA3F, 6), hx("B9B8BBC9FFF0"))
        self.assertEqual(at(0xBA58, 6), hx("B9B8BBC9FFF0"))
        self.assertEqual(at(0xBA84, 6), hx("B9D8BBC9FFF0"))
        self.assertEqual(at(0xBA9D, 6), hx("B9D8BBC9FFF0"))
        self.assertEqual(at(0xBA19, 13), hx("B585C589F007B58AC58EF04660"))        # same row / same column tests
        self.assertEqual(at(0xBAAF, 17), hx("E002D004A5143008A90295CEA9A085AD60"))   # ghost 2 only when RTCLOK2 bit 7 is clear; state 2, ChaseTimer $A0

    def test_effective_rule_of_the_shipped_code(self):
        sees = M.sees
        # horizontal: only x = 100 ($64) and x = 132 ($84) block, on every row; zones: x <= 100, 100 < x <= 132, x > 132
        for y in M.YS:
            self.assertTrue(sees(0, 58, y, 8, 98, y))        # same zone
            self.assertFalse(sees(0, 58, y, 8, 118, y))      # crosses x = 100
            self.assertFalse(sees(0, 118, y, 4, 58, y))
            self.assertTrue(sees(0, 118, y, 8, 130, y))      # middle zone
            self.assertFalse(sees(0, 118, y, 8, 150, y))     # crosses x = 132
            self.assertTrue(sees(0, 150, y, 8, 190, y))      # right zone
        # vertical: blocked only across the top rows (68 / 74), on every column
        for x in M.XS:
            self.assertTrue(sees(0, x, 44, 2, x, 68))        # both in the top band
            self.assertFalse(sees(0, x, 44, 2, x, 84))       # leaves the top band
            self.assertFalse(sees(0, x, 84, 1, x, 68))
            self.assertTrue(sees(0, x, 84, 2, x, 196))       # everything below sees everything
            self.assertTrue(sees(0, x, 196, 1, x, 84))
        # direction matters: the ghost must face the target
        self.assertFalse(sees(0, 58, 44, 4, 98, 44))
        # ghost 2 reacts only when RTCLOK2 bit 7 is clear
        self.assertTrue(sees(2, 58, 44, 8, 98, 44, 0x00))
        self.assertFalse(sees(2, 58, 44, 8, 98, 44, 0x80))
        self.assertTrue(sees(1, 58, 44, 8, 98, 44, 0x80))

    def test_the_lists_were_built_for_the_offsets(self):
        """Applying the offsets (what the data is laid out for) fits the maze much better than what the code does."""
        hl = [lst(0xBBAB, rd(0xBBB8 + i)) for i in range(10)]
        vl = [lst(0xBBC2, rd(0xBBD8 + i)) for i in range(10)]
        blocked = lambda L, a, b: any(min(a, b) <= e < max(a, b) for e in L)
        conn_row = lambda r, a, b: all((J[r][c] & 8) and (J[r][c + 1] & 4) for c in range(min(a, b), max(a, b)))
        conn_col = lambda c, a, b: all((J[r][c] & 2) and (J[r + 1][c] & 1) for r in range(min(a, b), max(a, b)))
        tot = ag_int = ag_ship = 0
        for r in range(10):
            for a in range(10):
                for b in range(10):
                    if a != b and J[r][a] and J[r][b]:
                        want = conn_row(r, a, b)
                        tot += 1
                        ag_int += (not blocked(hl[r], M.XS[a], M.XS[b])) == want
                        ag_ship += M.sees(0, M.XS[a], M.YS[r], 8 if M.XS[a] < M.XS[b] else 4, M.XS[b], M.YS[r]) == want
        self.assertEqual((tot, ag_int, ag_ship), (746, 732, 478))
        tot = ag_int = ag_ship = 0
        for c in range(10):
            for a in range(10):
                for b in range(10):
                    if a != b and J[a][c] and J[b][c]:
                        want = conn_col(c, a, b)
                        tot += 1
                        ag_int += (not blocked(vl[c], M.YS[a], M.YS[b])) == want
                        ag_ship += M.sees(0, M.XS[c], M.YS[a], 2 if M.YS[a] < M.YS[b] else 1, M.XS[c], M.YS[b]) == want
        self.assertEqual((tot, ag_int, ag_ship), (728, 648, 360))


class Colours(unittest.TestCase):
    def test_tables(self):
        self.assertEqual(at(0xBBE2, 8), hx("444AD828860C002A"))   # PCOLR0-3 then COLOR0-3
        self.assertEqual(at(0xBBEA, 4), hx("DA0C002A"))          # title COLOR0-3
        self.assertEqual(at(0xBBEE, 4), hx("3A442ADA"))          # DLI colours

    def test_loaders(self):
        self.assertEqual(at(0xB113, 12), hx("A207BDE2BB9DC002CA10F760"))     # ColorsGame -> $02C0..$02C7
        self.assertEqual(at(0xA626, 8), hx("B9EABB99C4028810"))   # ColorsTitle -> COLOR0..3
        self.assertEqual(at(0xA4BC, 12), hx("BDEEBB454F254E955ECA10F4"))     # (ColorsDli EOR COLRSH AND DRKMSK) -> zp $5E..$61

    def test_what_each_dli_band_writes(self):
        self.assertEqual(at(0xA584, 23), hx("E001D013A5A0454F254EA65E8D0AD48D17D08E18D0D02D"))   # band 1: COLPF1 = ItemColor, COLPF2 = $5E
        self.assertEqual(at(0xA59B, 14), hx("E002D00AA55F8D0AD48D17D0D01F"))                    # band 2: COLPF1 = $5F
        self.assertEqual(at(0xA5A9, 19), hx("E003D00FA560A6618D0AD48E16D08D19D0D00C"))          # band 3: COLPF0 = $61, COLPF3 = $60
        self.assertEqual(at(0xA5BC, 14), hx("CAA9009D12D0CA10FA8D19D0E618"))                    # band 4: COLPF3 = 0
        self.assertEqual(at(0xACA2, 22), hx("A62BB530C9069008C90AB004A0DAD002A04484A0A000"))      # ItemColor: $DA on levels 6-9, else $44


if __name__ == "__main__":
    unittest.main(verbosity=2)
