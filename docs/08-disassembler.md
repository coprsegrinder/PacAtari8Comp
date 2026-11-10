# 08 – Disassembler (Step C8)

Written 2026-11-10. Covers checklist stages 21–22 (disassembler built and validated).

## Tool
`tools/disasm6502.py` – own 6502 disassembler in Python (no dependencies).
- Decodes the 151 official NMOS 6502 opcodes; anything else is reported as data.
- Output is **ca65 syntax**, so the listing can be reassembled directly in step C10. Absolute operands
  below $0100 are written `a:$00xx` and zero-page operands `z:$xx`, which forces the original encoding
  (ca65 would otherwise pick the shorter form and the rebuild would not be byte-exact).
- Two modes: recursive descent from given entry points (`--entry`), or linear sweep (`--linear`).
- Recursive descent follows branches, JSR and JMP abs; it stops at RTS/RTI/BRK/JMP. It does NOT follow
  indirect jumps, jump tables or addresses stored for later use (interrupt vectors installed by code).
  Those must be supplied as extra entries once found.
- Read-only: it never modifies its input.

## Validation (`tests/test_disasm6502.py`, run with `python -I tests/test_disasm6502.py`)
- Opcode table has exactly 151 entries, no duplicates.
- Known-instruction, signed-branch, illegal/truncated-opcode and tracing cases.
- **Round trip against the real assembler:** every official opcode, with three operand patterns each
  (453 instructions, including operands with a zero high byte), is disassembled, reassembled by ca65 and
  linked by ld65 at $A000; the bytes are identical to the input. This checks the opcode/mode table
  independently of my own code. Result: 5 tests, all pass.

## First measurements on Pac-Man.rom (not a deliverable yet)
- Recursive descent from RUN ($A386) and INIT ($A6B4) alone reaches 517 instructions, 1,111 bytes
  (13.6% of the ROM), with 92 branch/call targets. This is expected to be low: the game runs from
  interrupt handlers and tables that this pass cannot see.
- A linear sweep decodes 3,870 instructions and leaves 567 bytes undecodable, but a linear sweep
  cannot tell code from data, so it is only a cross-check.
- No full listing has been committed yet; that is step C9.

## Known limits
- Undocumented opcodes are not decoded; if the ROM turns out to use any, they will show as data until added.
- Labels are generated as `Lxxxx` for code targets only; naming is a later step (C11/D).
