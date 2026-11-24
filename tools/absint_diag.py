"""Diagnosis helper for tools/absint6502.py: the path (main-loop places, vertical-blank runs, followed values) to the first occurrence of a store, to see whether a store the search finds is real or an imprecision."""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import absint6502 as AB  # noqa: E402


class Witness(set):
    def __init__(self):
        super().__init__()
        self.where = {}
        self.cur = None

    def add(self, e):
        if e not in self:
            self.where[e] = self.cur
        super().add(e)


def vbi_path(m, T, target):
    """the places ($ of the instructions) of a vertical-blank run from T up to the store `target` = (addr, pc, old, new)"""
    parents = {}
    events = Witness()
    start = (AB.VBI_ENTRY, None, None, None, None, None, None, None, 0, (), T, None)
    table = {}
    work = []

    def add(st, par):
        k = m.key(st)
        r = m.regs(st)
        old = table.get(k)
        if old is None:
            table[k] = r
            parents.setdefault(k, par)
            work.append(k)
        else:
            j = m.join(old, r)
            if j != old:
                table[k] = j
                work.append(k)
    add(start, None)
    while work:
        k = work.pop()
        st = m.build(k, table[k])
        events.cur = k
        out = m.step(st, events, True)
        if target in events.where:
            path = []
            cur = events.where[target]
            while cur is not None:
                path.append(cur)
                cur = parents.get(cur)
            return [(hex(p[0]), p[2]) for p in reversed(path)]
        if out == "EXIT":
            continue
        for s2 in out:
            add(s2, k)
    return None


def main_path(m, T0, target, limit=4_000_000):
    """the chain of (main place, followed values, 'step' / 'interrupt') up to the first state in which `target` is made"""
    parents = {}
    table = {}
    work = []
    events = Witness()
    vev_seen = {}

    def add(st, par, tag):
        k = m.key(st)
        r = m.regs(st)
        old = table.get(k)
        if old is None:
            table[k] = r
            parents.setdefault(k, (par, tag))
            work.append(k)
        else:
            j = m.join(old, r)
            if j != old:
                table[k] = j
                work.append(k)
    start = (AB.MAIN_ENTRY, None, None, None, None, None, None, None, 0, (), T0, None)
    add(start, None, "start")
    while work:
        k = work.pop()
        st = m.build(k, table[k])
        events.cur = k
        out = m.step(st, events, False)
        if target in events.where:
            return trace(parents, events.where[target], m), None
        for s2 in out:
            add(s2, k, "step")
        fin, vev, _ = m.vbi(st[AB.T_IDX])
        if target in vev:
            return trace(parents, k, m), ("vbi from", st[AB.T_IDX])
        for T2 in fin:
            add(st[:AB.T_IDX] + (T2,) + st[AB.T_IDX + 1:], k, "interrupt")
        if len(table) > limit:
            break
    return None, None


def trace(parents, k, m):
    path = []
    cur = k
    while cur is not None:
        par, tag = parents.get(cur, (None, None))
        path.append((hex(cur[0]), cur[2], tag))
        cur = par
    return list(reversed(path))
