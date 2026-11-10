"""Step C11 (data formats): software model of the three decompressors in Start and ExpandData.

Formats were read from the code at $A3BA (stream type A), $A40A (nibble split) and $A668 (ExpandData,
table-driven, type B). Usage:  python -I tools/decode_streams.py   -> prints extents and output sizes.
Read-only.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(os.path.dirname(HERE), "original", "Pac-Man.rom"), "rb") as fh:
    ROM = fh.read()
BASE = 0xA000
rd = lambda a: ROM[a - BASE]


def decode_a(src):
    """Type A (code $A3BA).  c<$80: literal c.  $80-$BF: repeat next byte (c&$3F)+1 times.
    $C0-$FE: 3 bytes out = (c&$3F), hi nibble, lo nibble of next byte (2 bytes in).  $FF: end.
    Returns (output bytes, address after the $FF terminator)."""
    out, a = bytearray(), src
    while True:
        c = rd(a)
        if c < 0x80:
            out.append(c)
            a += 1
        elif c == 0xFF:
            return bytes(out), a + 1
        elif c < 0xC0:
            out += bytes([rd(a + 1)]) * ((c & 0x3F) + 1)
            a += 2
        else:
            b = rd(a + 1)
            out += bytes([c & 0x3F, b >> 4, b & 0x0F])
            a += 2


TABLE = BASE + 0x1D7A  # D_BD7A: 64 byte values


def decode_b(src):
    """Type B (ExpandData, $A668).  c<$40: output table[c].  c>=$40: output table[c&$3F] (c>>6)+1 times.
    $FF: end.  Returns (output bytes, address after the $FF terminator)."""
    out, a = bytearray(), src
    while True:
        c = rd(a)
        if c == 0xFF:
            return bytes(out), a + 1
        out += bytes([rd(TABLE + (c & 0x3F))]) * ((c >> 6) + 1)
        a += 1


def split_nibbles(src, n=256):
    """Code at $A40A: each source byte gives high nibble then low nibble (n bytes -> 2n bytes)."""
    out = bytearray()
    for i in range(n):
        b = rd(src + i)
        out += bytes([b >> 4, b & 0x0F])
    return bytes(out), src + n


def dump(outdir):
    """Write the decoded RAM images to `outdir` (resources/ is not committed: derived from the ROM)."""
    os.makedirs(outdir, exist_ok=True)
    for fname, data in (("charset_3000.bin", decode_b(0xA003)[0]), ("maze_0800.bin", decode_a(0xA1E1)[0]),
                        ("title_charset_1808.bin", decode_b(0xBE13)[0]),
                        ("nibbles_0600.bin", split_nibbles(0xBE95)[0])):
        with open(os.path.join(outdir, fname), "wb") as fh:
            fh.write(data)
        print("wrote", fname, len(data), "bytes")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        dump(os.path.join(os.path.dirname(HERE), "resources", "decoded"))
        raise SystemExit
    for name, fn, src, dst in (("typeB -> $3000", decode_b, 0xA003, 0x3000),
                               ("typeA -> $0800", decode_a, 0xA1E1, 0x0800),
                               ("typeB -> $1808", decode_b, 0xBE13, 0x1808)):
        out, end = fn(src)
        print("%-16s src $%04X-$%04X (%d bytes) -> %d bytes at $%04X-$%04X" % (
            name, src, end - 1, end - src, len(out), dst, dst + len(out) - 1))
    out, end = split_nibbles(0xBE95)
    print("nibbles -> $0600  src $BE95-$%04X (256 bytes) -> %d bytes at $0600-$07FF" % (end - 1, len(out)))
