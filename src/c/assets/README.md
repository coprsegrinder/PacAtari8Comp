# assets/ - the asset blob loader (stage 80a, docs/47, docs/51)

`assets.h` / `assets.c` read `resources/pack/assets.pmab`, written by `tools/make_c_assets.py` from the asset pack (derived from the ROM, not committed; the byte format is in the generator's docstring).
The file is read through `platform/fs.c`; the parser checks the magic, the version, the schema, the checksum and every entry's bounds and never allocates. `assets_ram_image` builds the 64 KB image
with the character sets, the maze, the tables at `$0600` and the font page, equal to the RAM that `Start` builds (checked by `tests/test_c_assets.py`).
