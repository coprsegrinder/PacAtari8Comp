# audio/ - the sound of the game (stage 80c, docs/22, docs/44)

`pokey.[ch]`: the POKEY chip as the game uses it, from register writes WITH CYCLES to PCM (a forward, event-driven model of what Altirra's renderer does; every rule from docs/22), NTSC.
`audio.[ch]` + `write_clock.[ch]`: the front end of the port: `audio_frame(World)` takes the log of the sound-chip writes of one frame (`World.pokey_*`), gives the writes their cycles inside the frame
(the core knows none: first write 40 cycles after the frame start, 9 cycles apart, measured by `tools/measure_write_clock.py`), runs the chip and returns the frame's PCM (float, mono).
Checked against Altirra's recordings by `tools/check_audio_c.py` / `tests/test_audio.py`; `tests/audio_selftest.c` (ctest) checks pitch, level, mixer, front end. See OPEN-VERIFICATION.md C-115.
