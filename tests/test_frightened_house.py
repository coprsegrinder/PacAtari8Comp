"""Evidence tests for frightened-mode steering, the eaten-ghost return and the ghost house (step C11). Run:  python -I tests/test_frightened_house.py
Byte-level checks of the code that docs/18-frightened-eaten-house.md describes (the live results are in analysis/evidence-frightened-house-summary.txt).
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import analyze_steering_log as A  # noqa: E402
import analyze_speed_log  # noqa: E402,F401
import decode_streams as S  # noqa: E402

at = lambda a, n: bytes(S.rd(a + i) for i in range(n))
hx = bytes.fromhex


class Code(unittest.TestCase):
    def test_0(self):
        # SteerToTarget wants (vertical then horizontal), mask test, random choice ($B999, 128 bytes)
        self.assertEqual(at(0xB999, 128), hx(
            "B585D5C6F0129008B5CE3008A901D00AB5CE30F8A902D002A90095D6B58AD5C2"
            "F012B008B5CE3008A908D00AB5CE30F8A904D002A90095DAB5D6F019242AF015"
            "B5DAF009242AF005AD0AD23004B5D6D02AB5DAD026B5DA242AD0F6AD0AD2252A"
            "D002A52A4A9004A901D0104A9004A902D0094A9004A904D002A908958FB58F60"))

    def test_1(self):
        # door-side squares rule ($B4E6, 34 bytes)
        self.assertEqual(at(0xB4E6, 34), hx(
            "B585C964D018B58AC976F004C982D00EB5CE3006A52A290ED002A901852AA52A"
            "2860"))

    def test_2(self):
        # eaten ghost walk and door arrival (Sub_B69E ghost loop) ($B69E, 80 bytes)
        self.assertEqual(at(0xB69E, 80), hx(
            "A90085F2A203B5CEC944F0440A1041E4E8F03DE6F2B58AA8B585C07CD01CC964"
            "D018B58FC901D008A904958FB585D00AA94495CEA9FF95D2D016208EB4900C18"
            "A97C95C2A96495C62099B9B58F2002B9"))

    def test_3(self):
        # leave the house, door row, walks, inside rows ($B738, 109 bytes)
        self.assertEqual(at(0xB738, 109), hx(
            "B585C964D01BB5CED004A901D00C29800902100685ADA008D002A004948F95CE"
            "60A901958F4C02B9B5CE290F95CEBDE2BB9DC00260B58AC97CF0C5A908D0E4B5"
            "8AC97CF0BBA904D0DAB585C974D00AE002F00AE003F00ED0CFA902D0C6B58AC9"
            "70D0E2F0C3B58AC988D0D0F0BB"))

    def test_4(self):
        # release loop and bobbing ($B7A5, 80 bytes)
        self.assertEqual(at(0xB7A5, 80), hx(
            "A201B5CE297FD023B5CAF008D6CA20D6B74CD0B7E003D0062077B74CD0B7E002"
            "D006206DB74CD0B72038B7E8E004D0D260B58FC901D00AB585C970D00EA902D0"
            "08B585C978D004A901958FB58F4C02B9"))


    def test_speed_rule(self):
        # the ghost loop in the main step ($A9E9-$AA28): eaten ghosts (bit 6) are skipped; a ghost in the tunnel row (y = $74, x < $52 or x >= $A7) or a frightened ghost
        # acts only on every second time its move-delay counter runs out (zp_5A toggles), every other ghost acts every time
        self.assertEqual(at(0xA9E9, 64), hx("B5CE293FF03AB5CE0A3035B585C974D00AB58AC9A7B008C9529004B5CE10172090B5C900D01AB45AC001D004955AF00DA901955AD00A2090B5C900D00320F5B7"))

    def test_speed_kind(self):
        import analyze_speed_log as V
        self.assertEqual(V.kind(0x02, 100, 100), "normal")
        self.assertEqual(V.kind(0x82, 100, 100), "frightened")
        self.assertEqual(V.kind(0x02, 0x50, 0x74), "tunnel")
        self.assertEqual(V.kind(0x02, 0x52, 0x74), "normal")
        self.assertEqual(V.kind(0x02, 0xA7, 0x74), "tunnel")
        self.assertEqual(V.kind(0x82, 0xB0, 0x74), "tunnel (frightened)")


class Model(unittest.TestCase):
    def test_wants(self):
        W = A.wants
        # normal: toward the target; frightened: mirrored; equal axis: 0
        self.assertEqual(W(False, 100, 100, 50, 50), (1, 4))
        self.assertEqual(W(True, 100, 100, 50, 50), (2, 8))
        self.assertEqual(W(False, 50, 50, 100, 100), (2, 8))
        self.assertEqual(W(True, 50, 50, 100, 100), (1, 4))
        self.assertEqual(W(True, 50, 100, 50, 100), (0, 0))
    def test_allowed(self):
        self.assertEqual(A.allowed(1, 4, 0x05), {1, 4})        # both available: random between them
        self.assertEqual(A.allowed(1, 4, 0x01), {1})
        self.assertEqual(A.allowed(1, 4, 0x04), {4})
        self.assertEqual(A.allowed(1, 4, 0x0A), {2, 8})        # neither: any exit
        self.assertEqual(A.allowed(0, 0, 0x00), {8})


class CollisionRule(unittest.TestCase):
    def test_contact_with_a_ghost(self):
        # $A851: ghosts with bit 6 (eaten) are skipped; after the player/missile and |dy| < 5 tests, $A87F: bit 7 set -> GhostEaten ($A886), otherwise JMP $A923 (the death routine)
        self.assertEqual(at(0xA851, 4), hx("B5CE0A30"))               # LDA GhostState,X / ASL / BMI skip
        self.assertEqual(at(0xA87F, 7), hx("B5CE3003" "4C23A9"))      # LDA GhostState,X / BMI GhostEaten / JMP $A923
        self.assertEqual(at(0xA886, 4), hx("A94295CE"))               # GhostEaten: state := $42
        # so a ghost that is not frightened (bit 7 clear) and not eaten kills Pac-Man even while the frightened phase runs


if __name__ == "__main__":
    unittest.main(verbosity=2)
