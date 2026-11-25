"""src/asm/pacman.s is NOT in the repository.  It is the cartridge program in assembler text (it assembles to the ROM byte for byte), so it is made, on the machine of someone who owns the ROM, from
original/Pac-Man.rom by tools/make_asm.py (with the project's own names and notes, tools/labels.py): the result is exactly the same file every time.  The tools and tests that read it call path(), which makes
it first when it is not there; without the ROM they stop and say what to do.

  python -I tools/asm_source.py        makes src/asm/pacman.s (and checks the ROM is there)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASM = os.path.join(ROOT, "src", "asm", "pacman.s")
ROM = os.path.join(ROOT, "original", "Pac-Man.rom")


def path():
    """the assembler source of the cartridge program, made from the player's own ROM if it is not there yet"""
    if not os.path.exists(ASM):
        if not os.path.exists(ROM):
            raise SystemExit("src/asm/pacman.s is made from your own Pac-Man (Atari 8-bit) cartridge ROM, and none is at original/Pac-Man.rom: put the ROM there, then run python -I tools/make_asm.py")
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "make_asm.py")], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    return ASM


if __name__ == "__main__":
    print(path())
