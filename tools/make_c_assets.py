"""Stage 80a: writes the asset blob of the C port, resources/pack/assets.pmab (derived from the ROM through tools/asset_pack.py; git-ignored like the pack).
The blob is the pack (docs/47, schema 2) in a defined little-endian byte format that src/c/assets/assets.c reads:

  header   4 bytes  "PMAB"
           u16      format version (1)
           u16      pack schema (2)
           u16      number of entries
           u16      0 (reserved)
           32 bytes sha256 of the ROM the blob was derived from
  entry    u8       length n of the name (1-63)
           n bytes  name, ASCII 0x21-0x7E
           u8       kind: 0 = ROM region (addr = its ROM address), 1 = text, ANTIC mode 2 codes, 2 = text, ANTIC mode 6 codes,
                    3 = RAM image part (addr = where `Start` or the OS leaves it in RAM),
                    4 = ROM window (addr = the ROM address of its first byte; the whole window, code bytes included, because the core indexes past the end of a table)
           u32      addr
           u32      size
           size bytes
  trailer  u32      FNV-1a (32 bit) of every byte before it

Entries, in this order: the five RAM image parts (charset.game $3000, charset.title $1808, maze $0800, ram_0600 $0600 (512 bytes), font $E000), the ROM window rom_ba00 ($BA00-$BFFF), then region.<name> for each of the 79 regions of the pack (all 2,246
non-code bytes of the ROM, in the order of the pack).  Everything else (sprites, texts, tunes, colours, tables, display lists) is a region: the C side looks it up by name.
Usage: python -I tools/make_c_assets.py [--out resources/pack/assets.pmab]"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import asset_pack as AP  # noqa: E402
import decode_streams as S  # noqa: E402

MAGIC = b"PMAB"
VERSION = 1
KIND_REGION, KIND_TEXT2, KIND_TEXT6, KIND_RAM, KIND_ROM_WINDOW = 0, 1, 2, 3, 4
DEFAULT_OUT = os.path.join(ROOT, "resources", "pack", "assets.pmab")


def fnv1a(data):
    h = 0x811C9DC5
    for b in data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def entries(P):
    """-> [(name, kind, addr, bytes)]"""
    img = AP.ram_image(P)                       # the reference loader's image: the parts are cut out of it
    out = [("charset.game", KIND_RAM, 0x3000, bytes(img[0x3000:0x3000 + len(P["charsets"]["game"]["rows"]) * 8])),
           ("charset.title", KIND_RAM, 0x1808, bytes(img[0x1808:0x1808 + len(P["charsets"]["title"]["rows"]) * 8])),
           ("maze", KIND_RAM, 0x0800, bytes(c for row in P["maze"]["codes"] for c in row)),
           ("ram_0600", KIND_RAM, 0x0600, bytes(S.split_nibbles(0xBE95)[0])),            # all 512 nibbles `Start` writes at $0600-$07FF
           ("font", KIND_RAM, 0xE000, bytes.fromhex("".join(P["font"]["rows"]))),
           ("rom_ba00", KIND_ROM_WINDOW, 0xBA00, bytes(S.ROM[0x1A00:0x2000]))]          # the ROM window $BA00-$BFFF the core indexes into (tables, pictures, and the code bytes between)
    kinds = {n: k for _, _, k, n, _ in AP.labels.DATA}
    for r in P["regions"]:
        k = {"text6": KIND_TEXT6, "text": KIND_TEXT2}.get(kinds.get(r["name"]), KIND_REGION)
        out.append(("region." + r["name"], k, int(r["addr"], 16), bytes.fromhex(r["bytes"])))
    return out


def blob(P):
    es = entries(P)
    b = bytearray(MAGIC)
    b += struct.pack("<HHHH", VERSION, P["schema"], len(es), 0)
    b += bytes.fromhex(P["rom"]["sha256"])
    seen = set()
    for name, kind, addr, data in es:
        raw = name.encode("ascii")
        assert 1 <= len(raw) <= 63 and all(0x21 <= c <= 0x7E for c in raw) and name not in seen, name
        seen.add(name)
        b += struct.pack("<B", len(raw)) + raw + struct.pack("<BII", kind, addr, len(data)) + data
    b += struct.pack("<I", fnv1a(b))
    return bytes(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()
    data = blob(AP.build())
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "wb") as fh:
        fh.write(data)
    print("wrote %s: %d bytes, %d entries" % (os.path.relpath(a.out, ROOT), len(data), struct.unpack_from("<H", data, 8)[0]))


if __name__ == "__main__":
    main()
