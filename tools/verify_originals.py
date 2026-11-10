"""Verify the original materials against docs/original-manifest.txt.

Usage (from the project root):  python -I tools/verify_originals.py
Exit code 0 = all files present and identical; 1 = a problem was found.
Read-only: this script never modifies any file.
"""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "docs", "original-manifest.txt")


def main():
    ok = True
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            digest, size, path = line.split("  ", 2)
            full = os.path.join(ROOT, *path.split("/"))
            if not os.path.isfile(full):
                print("MISSING  ", path)
                ok = False
                continue
            data = open(full, "rb").read()
            good = hashlib.sha256(data).hexdigest() == digest and len(data) == int(size)
            print("OK       " if good else "MISMATCH ", path)
            ok = ok and good
    print("ALL OK" if ok else "PROBLEMS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
