// OV-64: the static worst case of the vertical-blank handler with SETS OF VALUES for the four ghost-state bytes ($CE-$D1).
// A port of tools/absint6502.py (the abstract 6502 of docs/34) and tools/static_wcet.py (the longest path), in C++, with one change: a ghost-state byte is a SET of possible values (256 bits), not one value or unknown.
// A load of a ghost byte with a set of several values gives the accumulator a TABLE (value of A for every value of the byte); the flags that the following instructions set are TABLES too (the values for which a flag is 1).
// A branch on such a flag splits the set of the byte into the values that take it and the values that do not: on each side the byte is narrowed.  So two tests of one byte in one frame cannot disagree, and a ghost
// cannot be an eaten ghost in one loop and a chasing ghost in the next.  Nothing is stored but 128-bit hashes of the states (the longest path is found by a depth-first search with memoisation), so the memory is 24 bytes a state.
// Usage: wcet_sets <input.txt>   (written by tools/wcet_sets.py)
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>
#include <chrono>
using namespace std;

enum Kind : uint8_t { UNK = 0, CONST = 1, SYM = 2, SETV = 3 };
enum Op : uint8_t { O_LDA, O_LDX, O_LDY, O_STA, O_STX, O_STY, O_TAX, O_TAY, O_TXA, O_TYA, O_TXS, O_INX, O_INY, O_DEX, O_DEY, O_INC, O_DEC, O_AND, O_ORA, O_EOR, O_ADC, O_SBC, O_CMP, O_CPX, O_CPY, O_BIT, O_ASL, O_LSR, O_ROL, O_ROR, O_CLC, O_SEC, O_CLD, O_SED, O_CLI, O_SEI, O_NOP, O_PHA, O_PHP, O_PLA, O_PLP, O_BPL, O_BMI, O_BVC, O_BVS, O_BCC, O_BCS, O_BNE, O_BEQ, O_JMP, O_JSR, O_RTS, O_RTI, O_BAD };
enum Mode : uint8_t { M_IMM, M_ZP, M_ZPX, M_ZPY, M_ABS, M_ABX, M_ABY, M_IZX, M_IZY, M_IMP, M_ACC, M_REL, M_IND };

struct Ins { uint8_t len = 0; Op op = O_BAD; Mode mode = M_IMP; int32_t arg = -1; bool ok = false; };
static Ins INS[65536];
static uint8_t ROMB[65536];
static int16_t TABLE[65536];                 // -1: none
static uint8_t PRES[65536];
static bool ISFUNC[65536];

struct Bits { uint64_t w[4]; };
static inline bool bget(const Bits& b, int i) { return (b.w[i >> 6] >> (i & 63)) & 1; }
static inline void bset(Bits& b, int i) { b.w[i >> 6] |= 1ull << (i & 63); }
static inline Bits bzero() { Bits b; memset(&b, 0, sizeof b); return b; }
static inline int bcount(const Bits& b) { return __builtin_popcountll(b.w[0]) + __builtin_popcountll(b.w[1]) + __builtin_popcountll(b.w[2]) + __builtin_popcountll(b.w[3]); }
static inline Bits band(const Bits& a, const Bits& b) { Bits r; for (int i = 0; i < 4; i++) r.w[i] = a.w[i] & b.w[i]; return r; }
static inline bool beq(const Bits& a, const Bits& b) { return memcmp(&a, &b, sizeof a) == 0; }
static inline int bfirst(const Bits& b) { for (int i = 0; i < 256; i++) if (bget(b, i)) return i; return -1; }

struct Flag { Kind k = UNK; uint8_t c = 0; uint8_t g = 0; Bits b{}; };     // SYM: 1 for the values in b of ghost g
struct RegA { Kind k = UNK; uint8_t c = 0; uint8_t g = 0; uint8_t tab[256]; };
struct Reg { Kind k = UNK; uint8_t c = 0; };   // SETV: one of the bytes of a table window (state.win*)
struct Meta { int16_t x = -1, y = -1, a = -1; uint8_t px = 0, py = 0, pa = 0; };
struct SEnt { uint8_t kind = 0; uint16_t ret = 0; Meta m; };              // kind 0: a pushed byte (unknown), 1: a return address

static const int NT_MAX = 16;
static const int NA_MAX = 8;
struct Cnt { uint16_t n = 0; uint8_t d0 = 0; };

struct State {
  uint16_t pc = 0;
  RegA a; Reg x, y;
  Flag fn, fz, fc, fv;
  uint8_t d = 0;                              // decimal flag: 0, 1, 2 unknown
  Bits wa, wx, wy;                            // the table windows of an A, X, Y of kind SETV (they live for one instruction)
  uint8_t cr_reg = 0, cr_imm = 0, cr_kind = 0; // compare record: reg 1 a, 2 x, 3 y; kind 0 'z', 1 'c'
  int16_t T[NT_MAX];
  Bits gs[4];
  uint8_t sp = 0;
  SEnt stk[48];
  Cnt cnt[NA_MAX];
};

// ---- the run's configuration --------------------------------------------------------------------------------------------------------------------------------------------------------------------------
static vector<int> TRACK;                    // followed zero-page addresses
static int TIDX[256];
static vector<int> ANN_PC, ANN_BOUND;
static map<int, int> ANN_INDEX;
static Bits DOMAIN;
static bool CORRELATE = true;
static long LIMIT = 20000000;
static int GHOST_BASE = 0xCE;
static bool GHOSTS_ON = true;

struct Succ { State s; int cost; bool exitp; };

static int GHOST_N = 4;
static inline bool isGhostAddr(int addr) { return addr >= GHOST_BASE && addr < GHOST_BASE + GHOST_N; }

// ---- canonical form -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
static void setConstFlag(Flag& f, int v) { f.k = CONST; f.c = v; f.g = 0; f.b = bzero(); }
static void setUnkFlag(Flag& f) { f.k = UNK; f.c = 0; f.g = 0; f.b = bzero(); }

// narrow: the set of ghost g has changed; make the tables and flags that depend on it consistent; false: the set is empty (the state cannot happen)
static bool normalize(State& s) {
  for (int g = 0; g < 4; g++) {
    if (bcount(s.gs[g]) == 0) return false;
  }
  Flag* fl[4] = { &s.fn, &s.fz, &s.fc, &s.fv };
  for (int i = 0; i < 4; i++) {
    Flag& f = *fl[i];
    if (f.k != SYM) continue;
    Bits in = band(s.gs[f.g], f.b);
    int n = bcount(in), tot = bcount(s.gs[f.g]);
    if (n == 0) setConstFlag(f, 0);
    else if (n == tot) setConstFlag(f, 1);
    else f.b = in;
  }
  if (s.a.k == SYM) {
    int g = s.a.g;
    int tot = bcount(s.gs[g]);
    if (tot == 1) { int v = bfirst(s.gs[g]); s.a.k = CONST; s.a.c = s.a.tab[v]; s.a.g = 0; memset(s.a.tab, 0, 256); }
    else {
      int first = -1; bool same = true;
      for (int v = 0; v < 256; v++) if (bget(s.gs[g], v)) { if (first < 0) first = s.a.tab[v]; else if (s.a.tab[v] != first) { same = false; break; } }
      if (same) { s.a.k = CONST; s.a.c = first; s.a.g = 0; memset(s.a.tab, 0, 256); }
      else for (int v = 0; v < 256; v++) if (!bget(s.gs[g], v)) s.a.tab[v] = 0;
    }
  }
  return true;
}

// the registers and flags that depend on ghost g lose that dependence (its byte has been written)
static void forget(State& s, int g) {
  Flag* fl[4] = { &s.fn, &s.fz, &s.fc, &s.fv };
  for (auto f : fl) if (f->k == SYM && f->g == g) setUnkFlag(*f);
  if (s.a.k == SYM && s.a.g == g) { s.a.k = UNK; s.a.c = 0; s.a.g = 0; memset(s.a.tab, 0, 256); }
}

static void collapseA(State& s) { if (s.a.k == SYM) { s.a.k = UNK; s.a.c = 0; s.a.g = 0; memset(s.a.tab, 0, 256); } }

// ---- hashing ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
struct H128 { uint64_t a, b; bool operator==(const H128& o) const { return a == o.a && b == o.b; } };
static inline uint64_t mix(uint64_t h, uint64_t v) { h ^= v + 0x9e3779b97f4a7c15ull + (h << 6) + (h >> 2); h *= 0xff51afd7ed558ccdull; h ^= h >> 33; return h; }
static void ser(const State& s, vector<uint8_t>& o) {
  o.clear();
  auto p8 = [&](uint8_t v) { o.push_back(v); };
  auto p16 = [&](uint16_t v) { o.push_back(v & 255); o.push_back(v >> 8); };
  auto pf = [&](const Flag& f) { p8(f.k); if (f.k == CONST) p8(f.c); else if (f.k == SYM) { p8(f.g); for (int i = 0; i < 4; i++) for (int j = 0; j < 8; j++) p8((f.b.w[i] >> (8 * j)) & 255); } };
  p16(s.pc);
  p8(s.a.k); if (s.a.k == CONST) p8(s.a.c); else if (s.a.k == SETV) for (int i = 0; i < 4; i++) p16(s.wa.w[i] & 0xFFFF), p16((s.wa.w[i] >> 16) & 0xFFFF), p16((s.wa.w[i] >> 32) & 0xFFFF), p16((s.wa.w[i] >> 48) & 0xFFFF); else if (s.a.k == SYM) { p8(s.a.g); for (int i = 0; i < 256; i++) p8(s.a.tab[i]); }
  p8(s.x.k); if (s.x.k == CONST) p8(s.x.c); else if (s.x.k == SETV) for (int i = 0; i < 4; i++) p16(s.wx.w[i] & 0xFFFF), p16((s.wx.w[i] >> 16) & 0xFFFF), p16((s.wx.w[i] >> 32) & 0xFFFF), p16((s.wx.w[i] >> 48) & 0xFFFF);
  p8(s.y.k); if (s.y.k == CONST) p8(s.y.c); else if (s.y.k == SETV) for (int i = 0; i < 4; i++) p16(s.wy.w[i] & 0xFFFF), p16((s.wy.w[i] >> 16) & 0xFFFF), p16((s.wy.w[i] >> 32) & 0xFFFF), p16((s.wy.w[i] >> 48) & 0xFFFF);
  pf(s.fn); pf(s.fz); pf(s.fc); pf(s.fv);
  p8(s.d); p8(s.cr_reg); if (s.cr_reg) { p8(s.cr_imm); p8(s.cr_kind); }
  for (size_t i = 0; i < TRACK.size(); i++) p16((uint16_t)s.T[i]);
  for (int g = 0; g < 4; g++) for (int i = 0; i < 4; i++) for (int j = 0; j < 8; j++) p8((s.gs[g].w[i] >> (8 * j)) & 255);
  p8(s.sp);
  for (int i = 0; i < s.sp; i++) { const SEnt& e = s.stk[i]; p8(e.kind); if (e.kind) { p16(e.ret); p16((uint16_t)e.m.x); p16((uint16_t)e.m.y); p16((uint16_t)e.m.a); p8(e.m.px); p8(e.m.py); p8(e.m.pa); } }
  for (size_t i = 0; i < ANN_PC.size(); i++) { p16(s.cnt[i].n); if (s.cnt[i].n) p8(s.cnt[i].d0); }
}
static H128 hashState(const State& s) {
  static vector<uint8_t> buf;
  ser(s, buf);
  uint64_t h1 = 0xcbf29ce484222325ull, h2 = 0x9ae16a3b2f90404full;
  size_t i = 0;
  for (; i + 8 <= buf.size(); i += 8) { uint64_t v; memcpy(&v, &buf[i], 8); h1 = mix(h1, v); h2 = mix(h2 ^ 0x1234567, v * 0x9E3779B97F4A7C15ull + i); }
  uint64_t t = 0; int k = 0;
  for (; i < buf.size(); i++, k++) t |= (uint64_t)buf[i] << (8 * k);
  h1 = mix(h1, t ^ buf.size()); h2 = mix(h2, t + buf.size() * 31);
  if (h1 == 0 && h2 == 0) h1 = 1;
  return { h1, h2 };
}

// ---- cycles -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
static int cost(int pc, int nextpc, const State* st) {
  const Ins& i = INS[pc];
  Op m = i.op;
  bool br = (m >= O_BPL && m <= O_BEQ);
  if (br) { if (nextpc == pc + i.len) return 2; return 3 + (((pc + i.len) >> 8) != (nextpc >> 8) ? 1 : 0); }
  if (m == O_JSR || m == O_RTS || m == O_RTI) return 6;
  if (m == O_JMP) return i.mode == M_ABS ? 3 : 5;
  if (m == O_PHA || m == O_PHP) return 3;
  if (m == O_PLA || m == O_PLP) return 4;
  bool rmw = (m == O_ASL || m == O_LSR || m == O_ROL || m == O_ROR || m == O_INC || m == O_DEC);
  if (rmw && i.mode != M_ACC) { switch (i.mode) { case M_ZP: return 5; case M_ZPX: return 6; case M_ABS: return 6; case M_ABX: return 7; default: return 6; } }
  if (m == O_STA || m == O_STX || m == O_STY) { switch (i.mode) { case M_ZP: return 3; case M_ZPX: case M_ZPY: case M_ABS: return 4; case M_ABX: case M_ABY: return 5; case M_IZX: case M_IZY: return 6; default: return 4; } }
  int c;
  switch (i.mode) { case M_IMM: c = 2; break; case M_ZP: c = 3; break; case M_ZPX: case M_ZPY: case M_ABS: case M_ABX: case M_ABY: c = 4; break; case M_IZX: c = 6; break; case M_IZY: c = 5; break; default: c = 2; }
  bool rd = (m == O_LDA || m == O_LDX || m == O_LDY || m == O_ADC || m == O_SBC || m == O_AND || m == O_ORA || m == O_EOR || m == O_CMP || m == O_CPX || m == O_CPY || m == O_BIT);
  if (rd && (i.mode == M_ABX || i.mode == M_ABY)) {                // a page crossing: exact when the index is known, else possible unless the table starts on a page
    bool known = st && ((i.mode == M_ABX) ? st->x.k == CONST : st->y.k == CONST);
    int idx = known ? ((i.mode == M_ABX) ? st->x.c : st->y.c) : -1;
    if (known) { if ((i.arg & 0xFF) + idx > 0xFF) c += 1; }
    else if (i.arg & 0xFF) c += 1;
  }
  if (rd && i.mode == M_IZY) c += 1;
  return c;
}

// ---- memory model -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
// effective address of an operand: -1 unknown
static int effAddr(const State& s, const Ins& i) {
  switch (i.mode) {
    case M_ZP: return i.arg;
    case M_ABS: return i.arg;
    case M_ZPX: return s.x.k == CONST ? ((i.arg + s.x.c) & 255) : -1;
    case M_ZPY: return s.y.k == CONST ? ((i.arg + s.y.c) & 255) : -1;
    case M_ABX: return s.x.k == CONST ? (i.arg + s.x.c) : -1;
    case M_ABY: return s.y.k == CONST ? (i.arg + s.y.c) : -1;
    default: return -1;
  }
}

// value of a memory operand read: CONST / UNK.  (a ghost byte with several values is UNK here; `lda` handles it separately)
static Reg readMem(const State& s, const Ins& i) {
  Reg r;
  if (i.mode == M_IMM) { r.k = CONST; r.c = i.arg; return r; }
  int a = effAddr(s, i);
  if (a < 0) return r;
  if (a < 256 && TIDX[a] >= 0) { int16_t v = s.T[TIDX[a]]; if (v >= 0) { r.k = CONST; r.c = v; } return r; }
  if (a < 256 && isGhostAddr(a)) { const Bits& b = s.gs[a - GHOST_BASE]; if (bcount(b) == 1) { r.k = CONST; r.c = bfirst(b); } return r; }
  if (a >= 0xA000 && a < 0xC000) { r.k = CONST; r.c = ROMB[a]; return r; }
  if (a >= 0x0600 && a <= 0x07FF) { if (TABLE[a] >= 0) { r.k = CONST; r.c = TABLE[a]; } return r; }
  return r;
}

static void havocAll(State& s) {
  for (size_t i = 0; i < TRACK.size(); i++) s.T[i] = -1;
  for (int g = 0; g < 4; g++) { s.gs[g] = DOMAIN; forget(s, g); }
}

// write a value (CONST / UNK / set image) to a memory operand
static void writeMem(State& s, const Ins& i, Reg val, const Bits* image) {
  int a;
  switch (i.mode) {
    case M_ZP: case M_ABS: a = i.arg; break;
    case M_ZPX: a = s.x.k == CONST ? ((i.arg + s.x.c) & 255) : -2; break;
    case M_ABX: a = s.x.k == CONST ? i.arg + s.x.c : -2; break;
    case M_ABY: a = s.y.k == CONST ? i.arg + s.y.c : -2; break;
    case M_ZPY: a = s.y.k == CONST ? ((i.arg + s.y.c) & 255) : -2; break;
    default: return;                        // izx/izy: RAM pages, never a followed byte
  }
  if (a == -2) { if (i.mode == M_ZPX || i.mode == M_ZPY || i.arg < 0x100) havocAll(s); return; }
  if (a < 256 && TIDX[a] >= 0) { s.T[TIDX[a]] = val.k == CONST ? val.c : -1; return; }
  if (a < 256 && isGhostAddr(a)) {
    int g = a - GHOST_BASE;
    if (image) s.gs[g] = *image; else if (val.k == CONST) { s.gs[g] = bzero(); bset(s.gs[g], val.c); } else s.gs[g] = DOMAIN;
    forget(s, g);
    return;
  }
}

static inline void setNZ(State& s, int v) { setConstFlag(s.fn, v >> 7); setConstFlag(s.fz, v == 0); }
static inline void unkNZ(State& s) { setUnkFlag(s.fn); setUnkFlag(s.fz); }
static inline void clearCr(State& s) { s.cr_reg = 0; }
static inline void setA(State& s, Reg r) { s.a.k = r.k; s.a.c = r.c; s.a.g = 0; memset(s.a.tab, 0, 256); }

// flags from a table of results over the set of ghost g
static void symFlagsFromTab(State& s, int g, const uint8_t* tab) {
  Flag n, z; n.k = SYM; n.g = g; n.b = bzero(); z = n;
  for (int v = 0; v < 256; v++) if (bget(s.gs[g], v)) { if (tab[v] & 0x80) bset(n.b, v); if (tab[v] == 0) bset(z.b, v); }
  s.fn = n; s.fz = z;
}

static void unkResult(State& s, int reg) {          // a result nobody knows: the flags are unknown, with the record that zero means the register is zero
  unkNZ(s);
  s.cr_reg = reg; s.cr_imm = 0; s.cr_kind = 0;
}

static int depthOf(const State& s) { return s.sp; }

// the successor states of one instruction; returns false for an exit through the OS (the jump to XITVBV)
static bool step(const State& st0, vector<Succ>& out, bool& exitp) {
  out.clear(); exitp = false;
  const Ins& I = INS[st0.pc];
  State stc = st0;
  if (I.op != O_CMP && I.op != O_CPX && I.op != O_CPY) {              // a window lives for one instruction: only a compare uses it
    if (stc.a.k == SETV) { stc.a.k = UNK; stc.a.c = 0; }
    if (stc.x.k == SETV) { stc.x.k = UNK; stc.x.c = 0; }
    if (stc.y.k == SETV) { stc.y.k = UNK; stc.y.c = 0; }
  }
  const State& st = stc;
  if (!I.ok) { fprintf(stderr, "no instruction at %04X\n", st.pc); exit(2); }
  int pc = st.pc, nxt = pc + I.len;
  State s = st;
  s.pc = nxt;
  Op m = I.op;
  auto emit = [&](State& r) { if (!normalize(r)) return; Succ c; c.s = r; c.cost = cost(pc, r.pc, &st); c.exitp = false; out.push_back(c); };
  switch (m) {
    case O_LDA: case O_LDX: case O_LDY: {
      int addr = effAddr(st, I);
      bool symRead = (m == O_LDA && CORRELATE && addr >= 0 && addr < 256 && isGhostAddr(addr) && bcount(st.gs[addr - GHOST_BASE]) > 1 && I.mode != M_IMM);
      if (symRead) {
        int g = addr - GHOST_BASE;
        s.a.k = SYM; s.a.g = g; memset(s.a.tab, 0, 256);
        for (int v = 0; v < 256; v++) if (bget(st.gs[g], v)) s.a.tab[v] = v;
        symFlagsFromTab(s, g, s.a.tab);
        clearCr(s);
        emit(s); return true;
      }
      Reg val = readMem(st, I);
      Bits win = bzero(); bool setv = false;
      if (addr < 0 && (I.mode == M_ABX || I.mode == M_ABY)) {         // an indexed read of a table with an unknown index: one of the bytes of the 256-byte window
        int base = I.arg; bool ok = false;
        if (base >= 0xA000 && base + 255 < 0xC000) { for (int k = 0; k < 256; k++) bset(win, ROMB[base + k]); ok = true; }
        else if (base >= 0x0600 && base + 255 <= 0x07FF) { ok = true; for (int k = 0; k < 256; k++) { if (TABLE[base + k] < 0) { ok = false; break; } bset(win, TABLE[base + k]); } }
        if (ok) { if (bcount(win) == 1) { val.k = CONST; val.c = bfirst(win); } else { val.k = SETV; setv = true; } }
      }
      if (m == O_LDA) { setA(s, val); if (setv) s.wa = win; } else if (m == O_LDX) { s.x = val; if (setv) s.wx = win; } else { s.y = val; if (setv) s.wy = win; }
      if (val.k == CONST) { setNZ(s, val.c); clearCr(s); }
      else if (setv) {
        setUnkFlag(s.fn);
        if (!bget(win, 0)) { setConstFlag(s.fz, 0); clearCr(s); } else { setUnkFlag(s.fz); s.cr_reg = (m == O_LDA ? 1 : m == O_LDX ? 2 : 3); s.cr_imm = 0; s.cr_kind = 0; }
      }
      else { unkNZ(s); s.cr_reg = (m == O_LDA ? 1 : m == O_LDX ? 2 : 3); s.cr_imm = 0; s.cr_kind = 0; }
      emit(s); return true;
    }
    case O_STA: case O_STX: case O_STY: {
      Reg val;
      const Bits* image = nullptr; Bits img;
      if (m == O_STA) {
        if (st.a.k == SYM) {
          // the image of the set under the table
          img = bzero();
          for (int v = 0; v < 256; v++) if (bget(st.gs[st.a.g], v)) bset(img, st.a.tab[v]);
          image = &img; val.k = UNK;
        } else { val.k = st.a.k; val.c = st.a.c; }
      } else val = (m == O_STX) ? st.x : st.y;
      writeMem(s, I, val, image);
      // A stays what it was; if it was stored into a ghost byte its table still describes the OLD byte, which was just forgotten when that byte is the one it came from
      emit(s); return true;
    }
    case O_TAX: case O_TAY: case O_TXA: case O_TYA: {
      if (m == O_TAX || m == O_TAY) {
        Reg r;
        if (st.a.k == SYM) { r.k = UNK; symFlagsFromTab(s, st.a.g, st.a.tab); clearCr(s); }
        else { r.k = st.a.k; r.c = st.a.c; if (r.k == CONST) { setNZ(s, r.c); clearCr(s); } else { unkNZ(s); s.cr_reg = (m == O_TAX ? 2 : 3); s.cr_imm = 0; s.cr_kind = 0; } }
        if (m == O_TAX) s.x = r; else s.y = r;
      } else {
        Reg r = (m == O_TXA) ? st.x : st.y;
        setA(s, r);
        if (r.k == CONST) { setNZ(s, r.c); clearCr(s); } else { unkNZ(s); s.cr_reg = 1; s.cr_imm = 0; s.cr_kind = 0; }
      }
      emit(s); return true;
    }
    case O_TXS: s.sp = 0; emit(s); return true;
    case O_INX: case O_DEX: case O_INY: case O_DEY: {
      Reg r = (m == O_INX || m == O_DEX) ? st.x : st.y;
      int dlt = (m == O_INX || m == O_INY) ? 1 : -1;
      if (r.k == CONST) { r.c = (r.c + dlt) & 255; setNZ(s, r.c); clearCr(s); }
      else { r.k = UNK; unkNZ(s); s.cr_reg = (m == O_INX || m == O_DEX) ? 2 : 3; s.cr_imm = 0; s.cr_kind = 0; }
      if (m == O_INX || m == O_DEX) s.x = r; else s.y = r;
      emit(s); return true;
    }
    case O_INC: case O_DEC: {
      int dlt = m == O_INC ? 1 : -1;
      int addr = effAddr(st, I);
      if (addr >= 0 && addr < 256 && isGhostAddr(addr) && bcount(st.gs[addr - GHOST_BASE]) > 1) {
        int g = addr - GHOST_BASE;
        Bits img = bzero();
        for (int v = 0; v < 256; v++) if (bget(st.gs[g], v)) bset(img, (v + dlt) & 255);
        Reg u; u.k = UNK;
        writeMem(s, I, u, &img);
        unkNZ(s); clearCr(s);
        emit(s); return true;
      }
      Reg cur = readMem(st, I);
      Reg val; val.k = UNK;
      if (cur.k == CONST) { val.k = CONST; val.c = (cur.c + dlt) & 255; }
      writeMem(s, I, val, nullptr);
      if (val.k == CONST) setNZ(s, val.c); else unkNZ(s);
      clearCr(s);
      emit(s); return true;
    }
    case O_AND: case O_ORA: case O_EOR: {
      Reg mv = readMem(st, I);
      if (st.a.k == SYM && mv.k == CONST) {
        int g = st.a.g;
        for (int v = 0; v < 256; v++) if (bget(st.gs[g], v)) s.a.tab[v] = m == O_AND ? (st.a.tab[v] & mv.c) : m == O_ORA ? (st.a.tab[v] | mv.c) : (st.a.tab[v] ^ mv.c);
        symFlagsFromTab(s, g, s.a.tab); clearCr(s);
        emit(s); return true;
      }
      collapseA(s);
      Reg a; a.k = st.a.k == SYM ? UNK : st.a.k; a.c = st.a.c;
      Reg r; r.k = UNK;
      if (m == O_AND && ((mv.k == CONST && mv.c == 0) || (a.k == CONST && a.c == 0))) { r.k = CONST; r.c = 0; }
      else if (m == O_ORA && ((mv.k == CONST && mv.c == 0xFF) || (a.k == CONST && a.c == 0xFF))) { r.k = CONST; r.c = 0xFF; }
      else if (a.k == CONST && mv.k == CONST) { r.k = CONST; r.c = m == O_AND ? (a.c & mv.c) : m == O_ORA ? (a.c | mv.c) : (a.c ^ mv.c); }
      setA(s, r);
      if (r.k == CONST) { setNZ(s, r.c); clearCr(s); } else unkResult(s, 1);
      emit(s); return true;
    }
    case O_ADC: case O_SBC: {
      Reg mv = readMem(st, I);
      if (st.a.k == SYM && mv.k == CONST && st.fc.k == CONST && st.d == 0) {
        int g = st.a.g, c = st.fc.c;
        Flag cf, vf; cf.k = SYM; cf.g = g; cf.b = bzero(); vf = cf;
        for (int v = 0; v < 256; v++) if (bget(st.gs[g], v)) {
          int a = st.a.tab[v], r, cc, vv;
          if (m == O_ADC) { r = a + mv.c + c; cc = r > 0xFF; vv = ((~(a ^ mv.c)) & (a ^ r) & 0x80) != 0; }
          else { r = a - mv.c - (1 - c); cc = r >= 0; vv = ((a ^ mv.c) & (a ^ r) & 0x80) != 0; }
          s.a.tab[v] = r & 0xFF;
          if (cc) bset(cf.b, v);
          if (vv) bset(vf.b, v);
        }
        symFlagsFromTab(s, g, s.a.tab); s.fc = cf; s.fv = vf; clearCr(s);
        emit(s); return true;
      }
      collapseA(s);
      Reg a; a.k = st.a.k == SYM ? UNK : st.a.k; a.c = st.a.c;
      if (a.k != CONST || mv.k != CONST || st.fc.k != CONST || st.d != 0) {
        Reg u; u.k = UNK; setA(s, u); unkNZ(s); setUnkFlag(s.fc); setUnkFlag(s.fv); clearCr(s);
        emit(s); return true;
      }
      int r, cc, vv, c = st.fc.c;
      if (m == O_ADC) { r = a.c + mv.c + c; cc = r > 0xFF; vv = ((~(a.c ^ mv.c)) & (a.c ^ r) & 0x80) != 0; }
      else { r = a.c - mv.c - (1 - c); cc = r >= 0; vv = ((a.c ^ mv.c) & (a.c ^ r) & 0x80) != 0; }
      r &= 0xFF;
      Reg rr; rr.k = CONST; rr.c = r; setA(s, rr);
      setNZ(s, r); setConstFlag(s.fc, cc); setConstFlag(s.fv, vv); clearCr(s);
      emit(s); return true;
    }
    case O_CMP: case O_CPX: case O_CPY: {
      Reg mv = readMem(st, I);
      if (m == O_CMP && st.a.k == SYM && mv.k == CONST) {
        int g = st.a.g;
        Flag cf; cf.k = SYM; cf.g = g; cf.b = bzero();
        uint8_t tab[256]; memset(tab, 0, 256);
        for (int v = 0; v < 256; v++) if (bget(st.gs[g], v)) { int r = (st.a.tab[v] - mv.c) & 255; tab[v] = r; if (st.a.tab[v] >= mv.c) bset(cf.b, v); }
        symFlagsFromTab(s, g, tab); s.fc = cf; clearCr(s);
        emit(s); return true;
      }
      Reg reg = m == O_CMP ? (st.a.k == SYM ? Reg() : Reg{st.a.k, st.a.c}) : (m == O_CPX ? st.x : st.y);
      if (reg.k == SETV) {
        const Bits& w = m == O_CMP ? st.wa : (m == O_CPX ? st.wx : st.wy);
        auto settle = [&]() { if (s.a.k == SETV) { s.a.k = UNK; s.a.c = 0; } if (s.x.k == SETV) { s.x.k = UNK; s.x.c = 0; } if (s.y.k == SETV) { s.y.k = UNK; s.y.c = 0; } };
        settle();
        unkNZ(s); setUnkFlag(s.fc); clearCr(s);
        if (mv.k == CONST) {
          if (!bget(w, mv.c)) {
            bool allGe = true, allLt = true;
            for (int v = 0; v < 256; v++) if (bget(w, v)) { if (v >= mv.c) allLt = false; else allGe = false; }
            setConstFlag(s.fz, 0);
            if (allGe) setConstFlag(s.fc, 1); else if (allLt) setConstFlag(s.fc, 0);
          } else if (I.mode == M_IMM || I.mode == M_ZP || I.mode == M_ABS) { s.cr_reg = (m == O_CMP ? 1 : m == O_CPX ? 2 : 3); s.cr_imm = mv.c; s.cr_kind = 1; }
        }
        emit(s); return true;
      }
      if (reg.k == CONST && mv.k == CONST) {
        int r = (reg.c - mv.c) & 255;
        setConstFlag(s.fn, r >> 7); setConstFlag(s.fz, r == 0); setConstFlag(s.fc, reg.c >= mv.c); clearCr(s);
      } else {
        unkNZ(s); setUnkFlag(s.fc); clearCr(s);
        if (reg.k == UNK && st.a.k != SYM && I.mode == M_IMM) { s.cr_reg = (m == O_CMP ? 1 : m == O_CPX ? 2 : 3); s.cr_imm = I.arg; s.cr_kind = 1; }
      }
      emit(s); return true;
    }
    case O_BIT: {
      Reg mv = readMem(st, I);
      if (st.a.k == SYM && mv.k == CONST) {
        int g = st.a.g;
        Flag z; z.k = SYM; z.g = g; z.b = bzero();
        for (int v = 0; v < 256; v++) if (bget(st.gs[g], v) && ((st.a.tab[v] & mv.c) == 0)) bset(z.b, v);
        s.fz = z; setConstFlag(s.fn, mv.c >> 7); setConstFlag(s.fv, (mv.c >> 6) & 1); clearCr(s);
        emit(s); return true;
      }
      if (mv.k == UNK) {
        setUnkFlag(s.fn); setUnkFlag(s.fv);
        if (st.a.k == CONST && st.a.c == 0) setConstFlag(s.fz, 1); else setUnkFlag(s.fz);
        clearCr(s);
      } else {
        setConstFlag(s.fn, mv.c >> 7); setConstFlag(s.fv, (mv.c >> 6) & 1);
        if (st.a.k == CONST) setConstFlag(s.fz, (st.a.c & mv.c) == 0); else setUnkFlag(s.fz);
        clearCr(s);
      }
      emit(s); return true;
    }
    case O_ASL: case O_LSR: case O_ROL: case O_ROR: {
      bool acc = I.mode == M_ACC;
      if (acc && st.a.k == SYM && (m == O_ASL || m == O_LSR || st.fc.k == CONST)) {
        int g = st.a.g, c = st.fc.c;
        Flag cf; cf.k = SYM; cf.g = g; cf.b = bzero();
        for (int v = 0; v < 256; v++) if (bget(st.gs[g], v)) {
          int cur = st.a.tab[v], val, cc;
          if (m == O_ASL) { val = (cur << 1) & 255; cc = cur >> 7; }
          else if (m == O_LSR) { val = cur >> 1; cc = cur & 1; }
          else if (m == O_ROL) { val = ((cur << 1) | c) & 255; cc = cur >> 7; }
          else { val = (cur >> 1) | (c << 7); cc = cur & 1; }
          s.a.tab[v] = val;
          if (cc) bset(cf.b, v);
        }
        symFlagsFromTab(s, g, s.a.tab); s.fc = cf; clearCr(s);
        emit(s); return true;
      }
      int addr = acc ? -1 : effAddr(st, I);
      if (!acc && addr >= 0 && addr < 256 && isGhostAddr(addr) && bcount(st.gs[addr - GHOST_BASE]) > 1) {
        int g = addr - GHOST_BASE;
        Bits img = bzero();
        for (int v = 0; v < 256; v++) if (bget(st.gs[g], v)) {
          if ((m == O_ROL || m == O_ROR) && st.fc.k != CONST) { img = DOMAIN; break; }
          int c = st.fc.k == CONST ? st.fc.c : 0, val;
          if (m == O_ASL) val = (v << 1) & 255; else if (m == O_LSR) val = v >> 1; else if (m == O_ROL) val = ((v << 1) | c) & 255; else val = (v >> 1) | (c << 7);
          bset(img, val);
        }
        Reg u; u.k = UNK;
        writeMem(s, I, u, &img);
        unkNZ(s); setUnkFlag(s.fc); clearCr(s);
        emit(s); return true;
      }
      Reg cur = acc ? (st.a.k == SYM ? Reg() : Reg{st.a.k, st.a.c}) : readMem(st, I);
      Reg val; val.k = UNK; int cc = -1;
      if (cur.k == CONST && !((m == O_ROL || m == O_ROR) && st.fc.k != CONST)) {
        int c = st.fc.k == CONST ? st.fc.c : 0;
        val.k = CONST;
        if (m == O_ASL) { val.c = (cur.c << 1) & 255; cc = cur.c >> 7; }
        else if (m == O_LSR) { val.c = cur.c >> 1; cc = cur.c & 1; }
        else if (m == O_ROL) { val.c = ((cur.c << 1) | c) & 255; cc = cur.c >> 7; }
        else { val.c = (cur.c >> 1) | (c << 7); cc = cur.c & 1; }
      }
      if (acc) { collapseA(s); setA(s, val); } else writeMem(s, I, val, nullptr);
      if (val.k == CONST) { setNZ(s, val.c); setConstFlag(s.fc, cc); } else { unkNZ(s); setUnkFlag(s.fc); }
      clearCr(s);
      emit(s); return true;
    }
    case O_CLC: setConstFlag(s.fc, 0); emit(s); return true;
    case O_SEC: setConstFlag(s.fc, 1); emit(s); return true;
    case O_CLD: s.d = 0; emit(s); return true;
    case O_SED: s.d = 1; emit(s); return true;
    case O_CLI: case O_SEI: case O_NOP: emit(s); return true;
    case O_PHA: case O_PHP: { if (s.sp >= 47) { fprintf(stderr, "stack overflow\n"); exit(2); } s.stk[s.sp].kind = 0; s.sp++; emit(s); return true; }
    case O_PLA: {
      if (s.sp) s.sp--;
      collapseA(s); Reg u; u.k = UNK; setA(s, u); unkNZ(s); clearCr(s);
      emit(s); return true;
    }
    case O_PLP: { if (s.sp) s.sp--; unkNZ(s); setUnkFlag(s.fc); setUnkFlag(s.fv); s.d = 2; clearCr(s); emit(s); return true; }
    case O_BPL: case O_BMI: case O_BVC: case O_BVS: case O_BCC: case O_BCS: case O_BNE: case O_BEQ: {
      const Flag* f; int want; char which;
      switch (m) {
        case O_BPL: f = &st.fn; want = 0; which = 'n'; break; case O_BMI: f = &st.fn; want = 1; which = 'n'; break;
        case O_BVC: f = &st.fv; want = 0; which = 'v'; break; case O_BVS: f = &st.fv; want = 1; which = 'v'; break;
        case O_BCC: f = &st.fc; want = 0; which = 'c'; break; case O_BCS: f = &st.fc; want = 1; which = 'c'; break;
        case O_BNE: f = &st.fz; want = 0; which = 'z'; break; default: f = &st.fz; want = 1; which = 'z'; break;
      }
      int target = I.arg;
      State tk = st, fl = st;
      tk.pc = target; fl.pc = nxt;
      clearCr(tk); clearCr(fl);
      if (f->k == CONST) { State r = (f->c == want) ? tk : fl; emit(r); return true; }
      if (f->k == SYM) {
        int g = f->g;
        Bits yes = band(st.gs[g], f->b), no = st.gs[g];
        for (int i = 0; i < 4; i++) no.w[i] &= ~f->b.w[i];
        State& takenS = tk; State& fallS = fl;
        // the values with the flag set take the branch when want = 1
        takenS.gs[g] = want ? yes : no; fallS.gs[g] = want ? no : yes;
        emit(takenS); emit(fallS);
        return true;
      }
      // unknown flag: both ways; the compare record names what the register is on the equal path
      Flag* tf[4] = { &tk.fn, &tk.fz, &tk.fc, &tk.fv }; Flag* ff[4] = { &fl.fn, &fl.fz, &fl.fc, &fl.fv };
      int fi = which == 'n' ? 0 : which == 'z' ? 1 : which == 'c' ? 2 : 3;
      if (st.cr_reg && which == 'z') {
        State& eq = (m == O_BEQ) ? tk : fl; State& ne = (m == O_BEQ) ? fl : tk;
        Reg r; r.k = CONST; r.c = st.cr_imm;
        if (st.cr_reg == 1) { setA(eq, r); } else if (st.cr_reg == 2) eq.x = r; else eq.y = r;
        setConstFlag(eq.fz, 1);
        setConstFlag(eq.fn, (st.cr_kind == 1 || st.cr_imm < 0x80) ? 0 : 1);
        if (st.cr_kind == 1) setConstFlag(eq.fc, 1);
        setConstFlag(ne.fz, 0);
      } else {
        setConstFlag(*tf[fi], want); setConstFlag(*ff[fi], 1 - want);
      }
      emit(tk); emit(fl);
      return true;
    }
    case O_JMP: {
      if (I.arg >= 0xC000) { exitp = true; return false; }
      State r = st; r.pc = I.arg; emit(r); return true;
    }
    case O_JSR: {
      int tgt = I.arg;
      if (tgt >= 0xC000) {
        State r = s;
        collapseA(r); Reg u; u.k = UNK; setA(r, u); r.x = u; r.y = u;
        setUnkFlag(r.fn); setUnkFlag(r.fz); setUnkFlag(r.fc); setUnkFlag(r.fv); clearCr(r);
        emit(r); return true;
      }
      if (s.sp >= 47) { fprintf(stderr, "stack overflow\n"); exit(2); }
      SEnt& e = s.stk[s.sp++];
      e.kind = 1; e.ret = nxt - 1;
      uint8_t pr = PRES[tgt];
      e.m.pa = pr & 1; e.m.px = (pr >> 1) & 1; e.m.py = (pr >> 2) & 1;
      e.m.x = (e.m.px && st.x.k == CONST) ? st.x.c : -1;
      e.m.y = (e.m.py && st.y.k == CONST) ? st.y.c : -1;
      e.m.a = (e.m.pa && st.a.k == CONST) ? st.a.c : -1;
      State r = s; r.pc = tgt;
      emit(r); return true;
    }
    case O_RTS: {
      if (s.sp == 0 && getenv("RTS_EXIT")) return true;                    // a routine entered directly in a test: its return ends the run
      if (s.sp == 0 || s.stk[s.sp - 1].kind != 1) { fprintf(stderr, "rts without a return address at %04X\n", pc); exit(2); }
      SEnt e = s.stk[--s.sp];
      State r = s; r.pc = e.ret + 1;
      if (e.m.px) { if (e.m.x >= 0) { r.x.k = CONST; r.x.c = e.m.x; } else { r.x.k = UNK; r.x.c = 0; } }
      if (e.m.py) { if (e.m.y >= 0) { r.y.k = CONST; r.y.c = e.m.y; } else { r.y.k = UNK; r.y.c = 0; } }
      if (e.m.pa) { collapseA(r); if (e.m.a >= 0) { r.a.k = CONST; r.a.c = e.m.a; } else { r.a.k = UNK; r.a.c = 0; } }
      clearCr(r);
      emit(r); return true;
    }
    default: fprintf(stderr, "instruction %d at %04X not modelled\n", (int)m, pc); exit(2);
  }
  return false;
}

// the loop bounds (ANNOT of tools/static_wcet.py): counted per call of the routine; returns false when the bound is exceeded
static bool countAnnot(State& s) {
  auto it = ANN_INDEX.find(s.pc);
  if (it == ANN_INDEX.end()) return true;
  int k = it->second;
  Cnt& c = s.cnt[k];
  if (c.n == 0) { c.n = 1; c.d0 = depthOf(s); } else c.n++;
  return c.n <= ANN_BOUND[k];
}
static void releaseAnnot(State& s) {
  for (size_t k = 0; k < ANN_PC.size(); k++) if (s.cnt[k].n && depthOf(s) < s.cnt[k].d0) { s.cnt[k].n = 0; s.cnt[k].d0 = 0; }
}

// ---- the table of results -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
struct Table {
  vector<H128> keys; vector<int32_t> vals; size_t n = 0, mask = 0;
  static constexpr int32_t EMPTY = INT32_MIN, INPROG = INT32_MIN + 1, NEG = INT32_MIN + 2;
  Table() { resize(1 << 20); }
  void resize(size_t cap) {
    vector<H128> ok; vector<int32_t> ov; ok.swap(keys); ov.swap(vals);
    keys.assign(cap, H128{0, 0}); vals.assign(cap, EMPTY); mask = cap - 1; n = 0;
    for (size_t i = 0; i < ok.size(); i++) if (ok[i].a || ok[i].b) { size_t j = ok[i].a & mask; while (keys[j].a || keys[j].b) j = (j + 1) & mask; keys[j] = ok[i]; vals[j] = ov[i]; n++; }
  }
  int32_t* find(const H128& h, bool create) {
    size_t j = h.a & mask;
    while (keys[j].a || keys[j].b) { if (keys[j] == h) return &vals[j]; j = (j + 1) & mask; }
    if (!create) return nullptr;
    if ((n + 1) * 10 > keys.size() * 7) { resize(keys.size() * 2); j = h.a & mask; while (keys[j].a || keys[j].b) j = (j + 1) & mask; }
    keys[j] = h; vals[j] = EMPTY; n++;
    return &vals[j];
  }
};

struct Frame { State s; vector<Succ> succ; size_t i = 0; int32_t best = Table::NEG; H128 h; int costIn = 0; };

static void readInput(const char* path, State& start, int& entry) {
  ifstream in(path);
  if (!in) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
  string w;
  memset(TIDX, -1, sizeof TIDX);
  for (int i = 0; i < 65536; i++) TABLE[i] = -1;
  static map<string, Op> OPS = { {"lda", O_LDA}, {"ldx", O_LDX}, {"ldy", O_LDY}, {"sta", O_STA}, {"stx", O_STX}, {"sty", O_STY}, {"tax", O_TAX}, {"tay", O_TAY}, {"txa", O_TXA}, {"tya", O_TYA}, {"txs", O_TXS}, {"inx", O_INX}, {"iny", O_INY}, {"dex", O_DEX}, {"dey", O_DEY}, {"inc", O_INC}, {"dec", O_DEC}, {"and", O_AND}, {"ora", O_ORA}, {"eor", O_EOR}, {"adc", O_ADC}, {"sbc", O_SBC}, {"cmp", O_CMP}, {"cpx", O_CPX}, {"cpy", O_CPY}, {"bit", O_BIT}, {"asl", O_ASL}, {"lsr", O_LSR}, {"rol", O_ROL}, {"ror", O_ROR}, {"clc", O_CLC}, {"sec", O_SEC}, {"cld", O_CLD}, {"sed", O_SED}, {"cli", O_CLI}, {"sei", O_SEI}, {"nop", O_NOP}, {"pha", O_PHA}, {"php", O_PHP}, {"pla", O_PLA}, {"plp", O_PLP}, {"bpl", O_BPL}, {"bmi", O_BMI}, {"bvc", O_BVC}, {"bvs", O_BVS}, {"bcc", O_BCC}, {"bcs", O_BCS}, {"bne", O_BNE}, {"beq", O_BEQ}, {"jmp", O_JMP}, {"jsr", O_JSR}, {"rts", O_RTS}, {"rti", O_RTI} };
  static map<string, Mode> MODES = { {"imm", M_IMM}, {"zp", M_ZP}, {"zpx", M_ZPX}, {"zpy", M_ZPY}, {"abs", M_ABS}, {"abx", M_ABX}, {"aby", M_ABY}, {"izx", M_IZX}, {"izy", M_IZY}, {"imp", M_IMP}, {"acc", M_ACC}, {"rel", M_REL}, {"ind", M_IND} };
  start = State();
  start.a.k = UNK; memset(start.a.tab, 0, 256);
  for (int i = 0; i < NT_MAX; i++) start.T[i] = -1;
  for (int g = 0; g < 4; g++) start.gs[g] = bzero();
  vector<int> trackInit;
  while (in >> w) {
    if (w == "INS") { int n; in >> n; for (int i = 0; i < n; i++) { int pc, len, arg; string m, md; in >> pc >> len >> m >> md >> arg; Ins& I = INS[pc]; I.len = len; I.ok = true; I.arg = arg; I.mode = MODES.count(md) ? MODES[md] : M_IMP; if (!OPS.count(m)) { fprintf(stderr, "mnemonic %s\n", m.c_str()); exit(2); } I.op = OPS[m]; } }
    else if (w == "TAB") { int n; in >> n; for (int i = 0; i < n; i++) { int a, v; in >> a >> v; TABLE[a] = v; } }
    else if (w == "PRES") { int n; in >> n; for (int i = 0; i < n; i++) { int e, mk; in >> e >> mk; PRES[e] = mk; ISFUNC[e] = true; } }
    else if (w == "ENTRY") { in >> hex >> entry >> dec; }
    else if (w == "TRACK") { int n; in >> n; for (int i = 0; i < n; i++) { int a, v; in >> a >> v; TIDX[a] = TRACK.size(); TRACK.push_back(a); trackInit.push_back(v); } }
    else if (w == "DOMAIN") { int n; in >> n; DOMAIN = bzero(); for (int i = 0; i < n; i++) { int v; in >> v; bset(DOMAIN, v); } }
    else if (w == "GHOST") { int g, n; in >> g >> n; start.gs[g] = bzero(); for (int i = 0; i < n; i++) { int v; in >> v; bset(start.gs[g], v); } }
    else if (w == "ANNOT") { int n; in >> n; for (int i = 0; i < n; i++) { int pc, b; in >> pc >> b; ANN_INDEX[pc] = ANN_PC.size(); ANN_PC.push_back(pc); ANN_BOUND.push_back(b); } }
    else if (w == "LIMIT") { in >> LIMIT; }
    else if (w == "CORRELATE") { int v; in >> v; CORRELATE = v != 0; }
    else if (w == "GHOSTS") { int v; in >> v; GHOSTS_ON = v != 0; if (!GHOSTS_ON) GHOST_BASE = 0x1000; }
    else if (w == "GHOSTN") { in >> GHOST_N; }
    else if (w == "ROMFILE") { string f; getline(in, f); size_t b0 = f.find_first_not_of(" "); f = f.substr(b0); while (!f.empty() && (f.back() == 13 || f.back() == 32)) f.pop_back(); ifstream r(f, ios::binary); if (!r) { fprintf(stderr, "cannot open the ROM %s\n", f.c_str()); exit(2); } vector<char> b((istreambuf_iterator<char>(r)), istreambuf_iterator<char>()); for (size_t i = 0; i < b.size(); i++) ROMB[0xA000 + i] = (uint8_t)b[i]; }
  }
  for (size_t i = 0; i < trackInit.size(); i++) start.T[i] = trackInit[i];
  start.pc = entry;
  start.d = 0;
}

int main(int argc, char** argv) {
  if (argc < 2) { fprintf(stderr, "usage: wcet_sets input.txt\n"); return 2; }
  State start; int entry = 0xA5FD;
  readInput(argv[1], start, entry);
  Table memo;
  vector<Frame> stack;
  set<int> cycleHeads;
  long states = 0;
  int pruned = 0;
  H128 h0{0, 0};
  static long pcCount[65536];
  auto t0 = chrono::steady_clock::now();
  auto expand = [&](Frame& f) {
    bool ex = false;
    vector<Succ> raw;
    step(f.s, raw, ex);
    if (ex) { Succ c; c.s = f.s; c.cost = (INS[f.s.pc].op == O_JMP) ? 3 : cost(f.s.pc, 0xFFFF, &f.s); c.exitp = true; f.succ.push_back(c); return; }
    for (auto& r : raw) {
      State n = r.s;
      releaseAnnot(n);
      // the bound counts the executions of the instruction at the PC of the state that executes it
      Succ c; c.s = n; c.cost = r.cost; c.exitp = false; f.succ.push_back(c);
    }
  };
  // the annotated instruction is counted when it is executed: do it on the state before the step
  {
    Frame f; f.s = start; f.h = hashState(f.s); h0 = f.h;
    bool ok = countAnnot(f.s);
    int32_t* v = memo.find(f.h, true); *v = Table::INPROG; states++;
    if (ok) expand(f);
    stack.push_back(std::move(f));
  }
  while (!stack.empty()) {
    Frame& f = stack.back();
    if (f.i < f.succ.size()) {
      Succ& c = f.succ[f.i++];
      if (c.exitp) { if (c.cost > f.best) f.best = c.cost; continue; }
      State n = c.s;
      H128 h = hashState(n);
      int32_t* v = memo.find(h, true);
      if (*v == Table::EMPTY) {
        *v = Table::INPROG; states++; pcCount[n.pc]++;
        if (states % 1000000 == 0) { auto t = chrono::steady_clock::now(); fprintf(stderr, "states %ld  %.0f s\n", states, chrono::duration<double>(t - t0).count()); }
        if (states > LIMIT) { printf("LIMIT %ld states reached\n", states); return 3; }
        Frame nf; nf.s = n; nf.h = h; nf.costIn = c.cost;
        bool ok = countAnnot(nf.s);
        if (ok) expand(nf); else pruned++;
        stack.push_back(std::move(nf));
      } else if (*v == Table::INPROG) { cycleHeads.insert(n.pc); }
      else if (*v != Table::NEG) { int cand = c.cost + *v; if (cand > f.best) f.best = cand; }
    } else {
      int32_t best = f.best; H128 h = f.h; int cin = f.costIn;
      stack.pop_back();
      int32_t* v = memo.find(h, true); *v = best;
      if (!stack.empty() && best != Table::NEG) { Frame& p = stack.back(); int cand = cin + best; if (cand > p.best) p.best = cand; }
    }
  }
  printf("states %ld pruned %d\n", states, pruned);
  if (!cycleHeads.empty()) { printf("cycles at:"); for (int pc : cycleHeads) printf(" %04X", pc); printf("\n"); }
  int32_t* rv = memo.find(h0, false);
  if (rv && *rv != Table::NEG && *rv != Table::INPROG && *rv != Table::EMPTY) printf("longest %d\n", *rv); else printf("longest none\n");
  if (getenv("PCDUMP")) { FILE* f = fopen(getenv("PCDUMP"), "w"); for (int i = 0; i < 65536; i++) if (pcCount[i]) fprintf(f, "%04X %ld\n", i, pcCount[i]); fclose(f); }
  return cycleHeads.empty() ? 0 : 1;
}
