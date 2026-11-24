"""A small NMOS 6502 interpreter for the Pac-Man project (stage 50): it runs routines of the ROM instruction by instruction, so that an algorithm written down as a model (Python) can be compared with the real code.

Scope: the 151 official opcodes (tools/disasm6502.py OPCODES), the decimal-mode ADC / SBC of the NMOS part (flags N, V, Z as the hardware gives them), JSR / RTS / RTI / BRK, the stack in page 1.  No timing, no interrupts,
no hardware and no OS (a JSR to $C000 or above returns at once and is recorded in `os_calls`): the memory is 64 KB of RAM with the cartridge image at $A000; a read of $D20A (POKEY RANDOM) returns the next value of a list the caller supplies; every other hardware address reads as 0 / stores into the RAM
array (no side effects).  This is enough for the pure routines (score addition, speed pacing, data expansion, junction lookup); it is NOT an Atari emulator - the behaviour of the whole game is established with Altirra.
The interpreter itself is checked in tests/test_algorithms.py: decimal addition against known NMOS results, and the data expansion of `Start` against the independent decoders of tools/decode_streams.py.
Usage (library):  m = Machine(rom_bytes);  m.call(0xB423, a=0, x=0, y=0)   # JSR-like call, returns when the routine executes its final RTS
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disasm6502 as D  # noqa: E402

RANDOM = 0xD20A
BASE = 0xA000


class Halt(Exception):
    pass


class Machine:
    def __init__(self, rom, random_values=None):
        self.mem = bytearray(65536)
        self.mem[BASE:BASE + len(rom)] = rom
        self.rom_end = BASE + len(rom)
        self.a = self.x = self.y = 0
        self.s = 0xFF
        self.pc = 0
        self.c = self.z = self.n = self.v = self.d = self.i = 0
        self.random = list(random_values or [])
        self.random_reads = []
        self.steps = 0
        self.os_calls = []
        self.trace = None

    # ---- memory ----
    def rd(self, a):
        a &= 0xFFFF
        if a == RANDOM:
            v = self.random.pop(0) if self.random else 0
            self.random_reads.append(v)
            return v
        return self.mem[a]

    def wr(self, a, v):
        a &= 0xFFFF
        if BASE <= a < self.rom_end:
            return                                   # ROM: the write is ignored
        self.mem[a] = v & 0xFF

    def rd16(self, a):
        return self.rd(a) | (self.rd((a + 1) & 0xFFFF) << 8)

    # ---- flags ----
    def p(self, brk=1):
        return self.c | self.z << 1 | self.i << 2 | self.d << 3 | brk << 4 | 1 << 5 | self.v << 6 | self.n << 7

    def set_p(self, v):
        self.c, self.z, self.i, self.d, self.v, self.n = v & 1, v >> 1 & 1, v >> 2 & 1, v >> 3 & 1, v >> 6 & 1, v >> 7 & 1

    def nz(self, v):
        self.n = (v >> 7) & 1
        self.z = 1 if (v & 0xFF) == 0 else 0
        return v & 0xFF

    def push(self, v):
        self.mem[0x100 + self.s] = v & 0xFF
        self.s = (self.s - 1) & 0xFF

    def pull(self):
        self.s = (self.s + 1) & 0xFF
        return self.mem[0x100 + self.s]

    # ---- addressing ----
    def ea(self, mode, op):
        if mode == "zp":
            return op
        if mode == "zpx":
            return (op + self.x) & 0xFF
        if mode == "zpy":
            return (op + self.y) & 0xFF
        if mode == "abs":
            return op
        if mode == "abx":
            return (op + self.x) & 0xFFFF
        if mode == "aby":
            return (op + self.y) & 0xFFFF
        if mode == "izx":
            z = (op + self.x) & 0xFF
            return self.rd(z) | (self.rd((z + 1) & 0xFF) << 8)
        if mode == "izy":
            return ((self.rd(op) | (self.rd((op + 1) & 0xFF) << 8)) + self.y) & 0xFFFF
        raise ValueError(mode)

    # ---- arithmetic ----
    def adc(self, m):
        a, c = self.a, self.c
        if self.d:
            al = (a & 0x0F) + (m & 0x0F) + c
            if al >= 0x0A:
                al = ((al + 0x06) & 0x0F) + 0x10
            r = (a & 0xF0) + (m & 0xF0) + al
            self.z = 1 if ((a + m + c) & 0xFF) == 0 else 0                # NMOS: Z from the binary sum
            self.n = (r >> 7) & 1
            self.v = 1 if ((a ^ r) & (m ^ r) & 0x80) else 0
            if r >= 0xA0:
                r += 0x60
            self.c = 1 if r >= 0x100 else 0
            self.a = r & 0xFF
        else:
            r = a + m + c
            self.v = 1 if (~(a ^ m) & (a ^ r) & 0x80) else 0
            self.c = 1 if r > 0xFF else 0
            self.a = self.nz(r)

    def sbc(self, m):
        a, c = self.a, self.c
        r = a - m - (1 - c)
        self.v = 1 if ((a ^ m) & (a ^ r) & 0x80) else 0
        if self.d:
            al = (a & 0x0F) - (m & 0x0F) - (1 - c)
            if al < 0:
                al = ((al - 0x06) & 0x0F) - 0x10
            r2 = (a & 0xF0) - (m & 0xF0) + al
            if r2 < 0:
                r2 -= 0x60
            self.c = 1 if r >= 0 else 0
            self.nz(r)
            self.a = r2 & 0xFF
        else:
            self.c = 1 if r >= 0 else 0
            self.a = self.nz(r)

    def cmp(self, reg, m):
        r = reg - m
        self.c = 1 if r >= 0 else 0
        self.nz(r)

    # ---- execution ----
    def step(self):
        pc = self.pc
        opc = self.mem[pc]
        if opc not in D.OPCODES:
            raise Halt("illegal opcode %02X at %04X" % (opc, pc))
        mn, mode = D.OPCODES[opc]
        size = D.SIZE[mode]
        op = 0
        if size == 1:
            op = self.mem[(pc + 1) & 0xFFFF]
        elif size == 2:
            op = self.mem[(pc + 1) & 0xFFFF] | (self.mem[(pc + 2) & 0xFFFF] << 8)
        self.pc = (pc + 1 + size) & 0xFFFF
        self.steps += 1
        if self.trace is not None:
            self.trace.append(pc)
        if mn in D.BRANCHES:
            cond = {"bcc": not self.c, "bcs": self.c, "beq": self.z, "bne": not self.z, "bmi": self.n, "bpl": not self.n, "bvc": not self.v, "bvs": self.v}[mn]
            if cond:
                off = op - 256 if op > 127 else op
                self.pc = (self.pc + off) & 0xFFFF
            return
        if mn in ("lda", "ldx", "ldy", "adc", "sbc", "and", "ora", "eor", "cmp", "cpx", "cpy", "bit"):
            m = op if mode == "imm" else self.rd(self.ea(mode, op) if mode not in ("abs",) else op)
            if mn == "lda":
                self.a = self.nz(m)
            elif mn == "ldx":
                self.x = self.nz(m)
            elif mn == "ldy":
                self.y = self.nz(m)
            elif mn == "adc":
                self.adc(m)
            elif mn == "sbc":
                self.sbc(m)
            elif mn == "and":
                self.a = self.nz(self.a & m)
            elif mn == "ora":
                self.a = self.nz(self.a | m)
            elif mn == "eor":
                self.a = self.nz(self.a ^ m)
            elif mn == "cmp":
                self.cmp(self.a, m)
            elif mn == "cpx":
                self.cmp(self.x, m)
            elif mn == "cpy":
                self.cmp(self.y, m)
            elif mn == "bit":
                self.z = 1 if (self.a & m) == 0 else 0
                self.n = (m >> 7) & 1
                self.v = (m >> 6) & 1
            return
        if mn in ("sta", "stx", "sty"):
            v = {"sta": self.a, "stx": self.x, "sty": self.y}[mn]
            self.wr(self.ea(mode, op) if mode != "abs" else op, v)
            return
        if mn in ("inc", "dec", "asl", "lsr", "rol", "ror"):
            if mode == "acc":
                v = self.a
            else:
                addr = self.ea(mode, op) if mode != "abs" else op
                v = self.rd(addr)
            if mn == "inc":
                r = self.nz(v + 1)
            elif mn == "dec":
                r = self.nz(v - 1)
            elif mn == "asl":
                self.c = v >> 7
                r = self.nz(v << 1)
            elif mn == "lsr":
                self.c = v & 1
                r = self.nz(v >> 1)
            elif mn == "rol":
                c = self.c
                self.c = v >> 7
                r = self.nz((v << 1) | c)
            else:
                c = self.c
                self.c = v & 1
                r = self.nz((v >> 1) | (c << 7))
            if mode == "acc":
                self.a = r
            else:
                self.wr(addr, r)
            return
        if mn == "inx":
            self.x = self.nz(self.x + 1)
        elif mn == "iny":
            self.y = self.nz(self.y + 1)
        elif mn == "dex":
            self.x = self.nz(self.x - 1)
        elif mn == "dey":
            self.y = self.nz(self.y - 1)
        elif mn == "tax":
            self.x = self.nz(self.a)
        elif mn == "tay":
            self.y = self.nz(self.a)
        elif mn == "txa":
            self.a = self.nz(self.x)
        elif mn == "tya":
            self.a = self.nz(self.y)
        elif mn == "tsx":
            self.x = self.nz(self.s)
        elif mn == "txs":
            self.s = self.x
        elif mn == "pha":
            self.push(self.a)
        elif mn == "pla":
            self.a = self.nz(self.pull())
        elif mn == "php":
            self.push(self.p(1))
        elif mn == "plp":
            self.set_p(self.pull())
        elif mn == "clc":
            self.c = 0
        elif mn == "sec":
            self.c = 1
        elif mn == "cld":
            self.d = 0
        elif mn == "sed":
            self.d = 1
        elif mn == "cli":
            self.i = 0
        elif mn == "sei":
            self.i = 1
        elif mn == "clv":
            self.v = 0
        elif mn == "nop":
            pass
        elif mn == "jmp":
            self.pc = op if mode == "abs" else (self.mem[op] | (self.mem[(op & 0xFF00) | ((op + 1) & 0xFF)] << 8))
        elif mn == "jsr":
            r = (self.pc - 1) & 0xFFFF
            self.push(r >> 8)
            self.push(r & 0xFF)
            self.pc = op
        elif mn == "rts":
            lo = self.pull()
            hi = self.pull()
            self.pc = (((hi << 8) | lo) + 1) & 0xFFFF
        elif mn == "rti":
            self.set_p(self.pull())
            lo = self.pull()
            hi = self.pull()
            self.pc = (hi << 8) | lo
        elif mn == "brk":
            raise Halt("BRK at %04X" % pc)
        else:
            raise Halt("unimplemented %s" % mn)

    SENTINEL = 0xFFF0

    def call(self, addr, a=None, x=None, y=None, limit=2000000, until=None):
        """run the routine at addr as if by JSR; returns when its final RTS executes (the stack is back at the level of the call) or when pc == until"""
        if a is not None:
            self.a = a
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        s0 = self.s
        r = (self.SENTINEL - 1) & 0xFFFF
        self.push(r >> 8)
        self.push(r & 0xFF)
        self.pc = addr
        n = 0
        while self.pc != self.SENTINEL:
            if until is not None and self.pc == until:
                return n
            if self.pc >= 0xC000:                    # an OS entry ($E45C SETVBV ...): there is no OS here, the call just returns
                self.os_calls.append(self.pc)
                lo = self.pull()
                hi = self.pull()
                self.pc = (((hi << 8) | lo) + 1) & 0xFFFF
                continue
            self.step()
            n += 1
            if n > limit:
                raise Halt("step limit at %04X" % self.pc)
        assert self.s == s0, "stack not balanced"
        return n
