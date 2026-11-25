# src/asm

**The assembler source of the cartridge program is not stored here.** `pacman.s` is the original program in text (annotated 6502 assembly that reassembles byte for byte to the ROM), so it is **made from your own ROM**, on your machine, and is never part of the repository (it is in `.gitignore`):

```
python -I tools/make_asm.py       # reads original/Pac-Man.rom, writes src/asm/pacman.s (and pacman.cfg)
python -I tools/build_rom.py      # assembles it with ca65 / ld65 and checks it is byte-identical to the ROM
```

The result is a function of the ROM and of this project's own names and notes (`tools/labels.py`): the same file every time (checked). The tools and tests that read it call `tools/asm_source.py`, which makes it when it is not there; without the ROM they stop and say what to do.

`pacman.cfg` is the linker layout (where the 8,192 bytes go): it is this project's own and is tracked.
