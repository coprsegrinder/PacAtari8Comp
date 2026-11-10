"""Step B6-B7 helper: cartridge header, OS vectors, and a HEURISTIC scan of hardware/OS references.

Usage (project root):  python -I tools/scan_vectors.py > analysis/b-vectors-and-hw-scan.txt
Read-only. The reference scan only sees 3-byte instructions with an absolute operand, and
cannot tell code from data, so it may contain false positives and misses indexed accesses
(e.g. STA $D000,X). The real answer comes from the disassembly (step C8).
"""
import collections
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cart = open(os.path.join(ROOT, "original", "Pac-Man.rom"), "rb").read()
osrom = open(os.path.join(ROOT, "original", "Atari OS Rev B (19xx)(Atari)(NTSC)[400-800].rom"), "rb").read()

print("== Cartridge (maps $A000-$BFFF, %d bytes) ==" % len(cart))
t = cart[-6:]
print("$BFFA RUN  = $%04X" % (t[0] | t[1] << 8))
print("$BFFC cart-present byte = $%02X (0 = cartridge present)" % t[2])
print("$BFFD option byte       = $%02X (bit2 = boot/run cartridge, bit0 = boot disk)" % t[3])
print("$BFFE INIT = $%04X" % (t[4] | t[5] << 8))

print("\n== OS Rev B (maps $D800-$FFFF, %d bytes) ==" % len(osrom))
w = lambda a: osrom[a - 0xD800] | osrom[a - 0xD800 + 1] << 8
for n, a in (("NMI", 0xFFFA), ("RESET", 0xFFFC), ("IRQ", 0xFFFE)):
    print("$%04X %-6s -> $%04X" % (a, n, w(a)))
names = "DISKIV DSKINV CIOV SIOV SETVBV SYSVBV XITVBV SIOINV SENDEV INTINV CIOINV BLKBDV WARMSV COLDSV RBLOKV CSOPIV".split()
for k, n in enumerate(names):
    a = 0xE450 + 3 * k
    print("$%04X %-7s JMP $%04X" % (a, n, w(a + 1)))

print("\n== Heuristic references from the Pac-Man ROM (address: count, first sites) ==")
ops = {0x8D: "STA", 0x8E: "STX", 0x8C: "STY", 0xAD: "LDA", 0xAE: "LDX", 0xAC: "LDY",
       0x20: "JSR", 0x4C: "JMP", 0xEE: "INC", 0xCE: "DEC", 0x2C: "BIT", 0xCD: "CMP"}
hits = collections.defaultdict(list)
for i in range(len(cart) - 2):
    if cart[i] in ops:
        a = cart[i + 1] | cart[i + 2] << 8
        if 0xD000 <= a <= 0xD4FF or 0xE450 <= a <= 0xE47F or 0x0200 <= a <= 0x022B:
            hits[a].append((0xA000 + i, ops[cart[i]]))
for a in sorted(hits):
    print("$%04X %2d  %s" % (a, len(hits[a]), " ".join("%04X:%s" % x for x in hits[a][:6])))
