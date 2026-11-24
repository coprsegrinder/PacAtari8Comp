"""Stage 75b: the vector file format (docs/51 section 2), the writer and a reader.  The same format is read by src/c/tests/vector.c (its header comment is the specification).
All integers are little-endian, written byte by byte.  The packed state is the World's regions in the order of src/c/core/world.c (the zero page first)."""
import struct

import core_world as W
import make_c_world as MCW

MAGIC = b"PMVEC001"
KIND_WORLD, KIND_PURE = 1, 2
STATE_SIZE = MCW.STATE_SIZE
EXTRA_ORDER = [e[0] for e in MCW.EXTRA]           # maze, status, shadow, stick, collide, pm, hpos, picbuf
EXTRA_SIZE = {e[0]: e[2] for e in MCW.EXTRA}
MAX_SEQ = 256
MAX_ARGS = 16
MAX_SUB = 8
GAP = 8                                           # two runs of changed bytes at most this far apart are one run


def pack_state(w):
    """the whole state of a World as bytes: the zero page (by address), then maze, status, shadow, stick, collide, pm, hpos, picbuf"""
    out = bytearray(0x100)
    for name, addr, n in W.FIELDS:
        v = getattr(w, name)
        if n == 1:
            out[addr] = v & 0xFF
        else:
            for k in range(n):
                out[addr + k] = v[k] & 0xFF
    for name in EXTRA_ORDER:
        v = getattr(w, name)
        assert len(v) == EXTRA_SIZE[name], name
        out += bytes(b & 0xFF for b in v)
    assert len(out) == STATE_SIZE
    return bytes(out)


def unpack_state(b):
    w = W.World()
    for name, addr, n in W.FIELDS:
        setattr(w, name, b[addr] if n == 1 else list(b[addr:addr + n]))
    k = 0x100
    for name in EXTRA_ORDER:
        setattr(w, name, list(b[k:k + EXTRA_SIZE[name]]))
        k += EXTRA_SIZE[name]
    w.pokey = []
    return w


def u8(x):
    return struct.pack("<B", x)


def u16(x):
    return struct.pack("<H", x)


def u32(x):
    return struct.pack("<I", x)


def i32(x):
    return struct.pack("<i", x)


def diff(a, b):
    """runs of the bytes of b that differ from a, as the bytes of a `diff` field"""
    runs, i, n = [], 0, len(a)
    while i < n:
        if a[i] == b[i]:
            i += 1
            continue
        j = i + 1
        last = i
        while j < n and j - last <= GAP:
            if a[j] != b[j]:
                last = j
            j += 1
        runs.append((i, last + 1))
        i = last + 1
    out = bytearray(u16(len(runs)))
    for s, e in runs:
        out += u16(s) + u16(e - s) + b[s:e]
    return bytes(out)


def apply_diff(a, d):
    out = bytearray(a)
    nruns = struct.unpack_from("<H", d, 0)[0]
    p = 2
    for _ in range(nruns):
        s, ln = struct.unpack_from("<HH", d, p)
        p += 4
        out[s:s + ln] = d[p:p + ln]
        p += ln
    return bytes(out), p


def value(x):
    """a pure argument or result: an int (bool too), a sequence of ints, or None"""
    if x is None:
        return u8(2)
    if isinstance(x, (bool, int)):
        return u8(0) + i32(int(x))
    if isinstance(x, (list, tuple)) and x and all(isinstance(e, (list, tuple)) for e in x):
        if len(x) > MAX_SUB or sum(len(e) for e in x) > MAX_SEQ or not all(isinstance(c, (bool, int)) for e in x for c in e):
            raise ValueError("sequence of sequences not representable: %r" % (x,))
        return u8(3) + u16(len(x)) + b"".join(u16(len(e)) + b"".join(i32(int(c)) for c in e) for e in x)
    if isinstance(x, (list, tuple, bytes, bytearray)):
        if len(x) > MAX_SEQ or not all(isinstance(e, (bool, int)) for e in x):
            raise ValueError("sequence not representable: %r" % (x,))
        return u8(1) + u16(len(x)) + b"".join(i32(int(e)) for e in x)
    raise ValueError("value not representable: %r" % (x,))


class SetWriter:
    def __init__(self, path, kind, name, base=None):
        self.f = open(path, "wb")
        self.kind = kind
        self.base = base
        self.count = 0
        nm = name.encode("ascii")
        self.f.write(MAGIC + u8(kind) + u16(len(nm)) + nm + u32(STATE_SIZE if kind == KIND_WORLD else 0))
        self.count_at = self.f.tell()
        self.f.write(u32(0))
        if kind == KIND_WORLD:
            assert len(base) == STATE_SIZE
            self.f.write(base)

    def world(self, args, rnd, ret, before, after, pokey):
        assert len(args) <= MAX_ARGS and len(rnd) < 65536 and len(pokey) <= MCW.POKEY_MAX
        b = bytearray(u8(len(args)))
        for a in args:
            b += i32(a)
        b += u16(len(rnd)) + bytes(rnd)
        b += u8(0 if ret is None else 1) + i32(0 if ret is None else ret)
        b += diff(self.base, before) + diff(before, after)
        b += u16(len(pokey))
        for a, v in pokey:
            b += u16(a) + u8(v & 0xFF)
        self.f.write(b)
        self.count += 1

    def pure(self, args, result):
        assert len(args) <= MAX_ARGS
        b = bytearray(u8(len(args)))
        for a in args:
            b += value(a)
        b += value(result)
        self.f.write(b)
        self.count += 1

    def close(self):
        self.f.seek(self.count_at)
        self.f.write(u32(self.count))
        self.f.close()


def read_set(path):
    """a reader for the tests: (kind, name, count, records); a world record is a dict with args, rnd, ret, before, after, pokey"""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != MAGIC:
        raise ValueError("bad magic")
    kind = data[8]
    nl = struct.unpack_from("<H", data, 9)[0]
    name = data[11:11 + nl].decode("ascii")
    p = 11 + nl
    ss, count = struct.unpack_from("<II", data, p)
    p += 8
    recs = []
    base = None
    if kind == KIND_WORLD:
        base = data[p:p + ss]
        p += ss
    for _ in range(count):
        if kind == KIND_WORLD:
            na = data[p]
            p += 1
            args = list(struct.unpack_from("<%di" % na, data, p))
            p += 4 * na
            nr = struct.unpack_from("<H", data, p)[0]
            p += 2
            rnd = list(data[p:p + nr])
            p += nr
            has, ret = struct.unpack_from("<Bi", data, p)
            p += 5
            before, q = apply_diff(base, data[p:])
            p += q
            after, q = apply_diff(before, data[p:])
            p += q
            npk = struct.unpack_from("<H", data, p)[0]
            p += 2
            pk = [struct.unpack_from("<HB", data, p + 3 * k) for k in range(npk)]
            p += 3 * npk
            recs.append({"args": args, "rnd": rnd, "ret": ret if has else None, "before": before, "after": after, "pokey": pk})
        else:
            na = data[p]
            p += 1
            vals = []
            for _ in range(na + 1):
                tag = data[p]
                p += 1
                if tag == 0:
                    vals.append(struct.unpack_from("<i", data, p)[0])
                    p += 4
                elif tag == 1:
                    n = struct.unpack_from("<H", data, p)[0]
                    p += 2
                    vals.append(list(struct.unpack_from("<%di" % n, data, p)))
                    p += 4 * n
                elif tag == 3:
                    ns = struct.unpack_from("<H", data, p)[0]
                    p += 2
                    subs = []
                    for _ in range(ns):
                        n = struct.unpack_from("<H", data, p)[0]
                        p += 2
                        subs.append(list(struct.unpack_from("<%di" % n, data, p)))
                        p += 4 * n
                    vals.append(subs)
                else:
                    vals.append(None)
            recs.append({"args": vals[:-1], "result": vals[-1]})
    if p != len(data):
        raise ValueError("trailing bytes")
    return kind, name, count, recs


# ------------------------------------------------------------------------------------------------ kind 3: collision scenes (stage 77a)
KIND_SCENE = 3
SCENE_CELLS = 920
SCENE_CHARSET = 1024
MODE_ALONE, MODE_RESET, MODE_CARRY, MODE_SET = 0, 1, 2, 3
# a scene record: mode:u8 (0 no latch: the registers of the scene alone; 1 the latch is cleared, then the scene is ORed in; 2 the scene is ORed into the latch the C made in the previous record; 3 the latch is set to
# latch_in, then the scene is ORed in)  mask:u16 (bit i: register i is compared; 0 = the record only moves the latch)  diff(cells from the header's cells, 920 bytes)  hpos:u8[8]
# five pages, each diff(zero page)  [mode 3: latch_in:u8[16]]  expected:u8[16]
# the file: the common header with kind 3 and state size 0, then charset:u8[1024] and the base cells:u8[920] after the count


class SceneWriter:
    def __init__(self, path, name, charset, cells):
        assert len(charset) == SCENE_CHARSET and len(cells) == SCENE_CELLS
        self.f = open(path, "wb")
        self.cells = bytes(cells)
        self.count = 0
        nm = name.encode("ascii")
        self.f.write(MAGIC + u8(KIND_SCENE) + u16(len(nm)) + nm + u32(0))
        self.count_at = self.f.tell()
        self.f.write(u32(0) + bytes(charset) + self.cells)

    def scene(self, mode, mask, cells, hpos, pages, expected, latch_in=None):
        assert len(hpos) == 8 and len(pages) == 5 and len(expected) == 16
        b = bytearray(u8(mode) + u16(mask))
        b += diff(self.cells, bytes(cells))
        b += bytes(hpos)
        zero = bytes(256)
        for pg in pages:
            assert len(pg) == 256
            b += diff(zero, bytes(pg))
        if mode == MODE_SET:
            b += bytes(latch_in)
        b += bytes(expected)
        self.f.write(b)
        self.count += 1

    def close(self):
        self.f.seek(self.count_at)
        self.f.write(u32(self.count))
        self.f.close()


def read_scene_set(path):
    """-> (name, charset, base cells, records); a record is a dict mode, mask, cells, hpos, pages, latch_in, expected"""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != MAGIC or data[8] != KIND_SCENE:
        raise ValueError("not a scene set")
    nl = struct.unpack_from("<H", data, 9)[0]
    name = data[11:11 + nl].decode("ascii")
    p = 11 + nl + 4
    count = struct.unpack_from("<I", data, p)[0]
    p += 4
    charset = data[p:p + SCENE_CHARSET]
    p += SCENE_CHARSET
    base_cells = data[p:p + SCENE_CELLS]
    p += SCENE_CELLS
    recs = []
    for _ in range(count):
        mode = data[p]
        mask = struct.unpack_from("<H", data, p + 1)[0]
        p += 3
        cells, q = apply_diff(base_cells, data[p:])
        p += q
        hpos = list(data[p:p + 8])
        p += 8
        pages = []
        for _ in range(5):
            pg, q = apply_diff(bytes(256), data[p:])
            p += q
            pages.append(pg)
        latch_in = None
        if mode == MODE_SET:
            latch_in = list(data[p:p + 16])
            p += 16
        expected = list(data[p:p + 16])
        p += 16
        recs.append({"mode": mode, "mask": mask, "cells": cells, "hpos": hpos, "pages": pages, "latch_in": latch_in, "expected": expected})
    if p != len(data):
        raise ValueError("trailing bytes")
    return name, charset, base_cells, recs
