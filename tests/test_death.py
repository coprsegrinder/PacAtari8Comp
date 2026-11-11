"""Evidence tests for Pac-Man's pictures and the death sequence (docs/20-pacman-and-death.md). Run:  python -I tests/test_death.py
Static: the code bytes of the picture selection, the death trigger, DeathSequence and DeathAnimation; the nine shapes; the software model of the death sequence (tools/analyze_death_log.py) gives the
durations and the sound/animation sequences that the live runs (analysis/evidence-death-summary.txt, analysis/evidence-pacman-screenshots-summary.txt) match frame by frame.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_death_log as D  # noqa: E402
import check_pacman_screenshots as C  # noqa: E402
import decode_streams as S  # noqa: E402

rd = S.rd
at = lambda a, n: bytes(rd(a + i) for i in range(n))
hx = bytes.fromhex


def run_model():
    v = dict(ds=1, ee=0x60, da=0, daf=0, dad=0, z24=0, f0=0, ef=0, f1=0)
    dur, anim, audf, n = {}, {}, [], 0
    while v["z24"] == 0 and n < 2000:
        dur[v["ds"]] = dur.get(v["ds"], 0) + 1
        w = D.model_audf(v)
        if w:
            audf.append(w)
        v, drawn = D.model_step(v)
        if drawn is not None:
            anim[drawn] = anim.get(drawn, 0) + 1
        n += 1
    return n, dur, anim, audf


class PacManPictures(unittest.TestCase):
    def test_nine_shapes_and_pointers(self):
        self.assertEqual(at(0xBB65, 10), hx("FCBA06BB1ABB2EBB42BB"))        # PacShapePtrs: Full, Right1, Left1, Up1, Down1; the second frame of a direction is 10 bytes further
        self.assertEqual(at(0xBB55, 3), hx("000A00"))                        # PacMouthOffsets
        self.assertEqual(len(C.SHAPES), 9)
        self.assertEqual(C.SHAPES["Full"], [0x38, 0x7C, 0xFE, 0xFE, 0xFE, 0xFE, 0xFE, 0xFE, 0x7C, 0x38])
        self.assertEqual(C.SHAPES["Right2"], [0x38, 0x7C, 0xF8, 0xF0, 0xE0, 0xE0, 0xF0, 0xF8, 0x7C, 0x38])

    def test_selection_and_draw_code(self):
        # moving: LDY #6 (up) / #8 (down) / #2 (right) / #4 (left), JMP $B2D3 (mouth cycle); standing still: LDY #index, LDA #$0A (second frame); no direction: LDY #0 (Full)
        self.assertEqual(at(0xB20C, 5), hx("A0064CD3B2"))
        self.assertEqual(at(0xB23A, 5), hx("A0084CD3B2"))
        self.assertEqual(at(0xB26D, 4), hx("A002D062"))
        self.assertEqual(at(0xB2A6, 4), hx("A004D029"))
        self.assertEqual(at(0xB2CA, 11), hx("A90AD01BA00098F016A6AB"))
        # mouth cycle: ChompPhase 0 -> Full; 1, 2, 3 -> offsets 0, 10, 0 ($BB55), then back to 0
        self.assertEqual(at(0xB2D3, 22), hx("A6ABD004E6ABD0F3CABD55BBE002D004A2FF86ABE6AB"))
        # staging at $0403, then 16 rows to $2300+PacY, the four missiles at PacX, +2, +4, +6 (M3, M2, M1, M0)
        self.assertEqual(at(0xB301, 55), hx("A009B13C9903048810F8A900853CA904853DA589853EA923853F18A58E8D07D069028D06D069028D05D069028D04D0A00FB13C913E8810"))


class DeathCode(unittest.TestCase):
    def test_trigger(self):
        # $A923: zp_AA |= $80 (Pac-Man frozen), ClearPokeyRegisters, zp_AE := 1, DeathState := 1, zp_EE := $60
        self.assertEqual(at(0xA923, 20), hx("A5AA098085AA20E6B0A90185AE85EDA96085EEA9"))

    def test_death_sequence_and_animation_bytes(self):
        self.assertEqual(at(0xAE3D, 0xAEF7 - 0xAE3D), hx(
            "A5EDC901D018A5EEF0102005ACA203B58F2002B9CA10F8C6EE60E6EDA5EDC902D023A203A9009D00D0CA10FAA93585F085EF20E6B085F185EBE6EAA90785ECA90385EDD010"
            "C903F00CC904F021C905F042C906F05BA9A88D01D2A5F08D00D218690885F0E6F1A5F1C904D043F022A9A88D01D2A5F08D00D238E90885F0C6F1D02EA5EFC96DF02618690485EF"
            "85F0A90385ED60A9A88D01D2A5EF8D00D238E90885EFC925D00920E6B0A98085F1E6ED60A5F1D003E62460C6F160"))
        self.assertEqual(at(0xAEF7, 0xAF54 - 0xAEF7), hx(
            "A5EAF058A589853EA923853FA5ECF004C6EC100CA5EBC90FF037E6EBA90785ECA5EBF011C90FF01BAACABD0006A888BD57BB913E60A00CA209BD38BB913E88CA10F760A00FA20F"
            "BD07BC913E88CA10F760A00FA900913E8810FB85EA60"))
        self.assertEqual(at(0xAE5F, 10), hx("A203A9009D00D0CA10FA"))        # ghosts hidden: LDX #3 / LDA #0 / STA HPOSP0,X / DEX / BPL


class DeathModel(unittest.TestCase):
    def test_durations(self):
        n, dur, anim, audf = run_model()
        self.assertEqual(n, 354)                                              # frames from DeathState 1 to zp_24 := 1 (about 5.9 s)
        self.assertEqual(dur, {1: 97, 3: 59, 4: 60, 5: 9, 6: 129})            # freeze 96 + 1, sound up 59, down 60, final sweep 9, silent wait 129
        self.assertEqual(anim[0], 7)                                          # PacShapeUp2 for 7 frames
        self.assertEqual([anim[k] for k in range(1, 16)], [8] * 15)           # 14 plot bytes and the star, 8 frames each
        self.assertEqual(anim["end"], 1)
        self.assertEqual(len(audf), 129)
        self.assertEqual(audf[:10], [(3, 53), (3, 61), (3, 69), (3, 77), (4, 85), (4, 77), (4, 69), (4, 61), (3, 57), (3, 65)])

    def test_animation_pages(self):
        self.assertEqual(C.death_page(0), [0, 0, 0] + C.UP2 + [0, 0, 0])
        self.assertEqual(C.death_page(15), C.STAR)
        self.assertEqual(C.death_page(16), [0] * 16)
        # each plot frame writes exactly one byte, at row DeathPlotRows[k-1] - 1
        for k in range(1, 15):
            self.assertEqual(sum(1 for a, b in zip(C.death_page(k), C.death_page(k - 1)) if a != b) <= 1, True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
