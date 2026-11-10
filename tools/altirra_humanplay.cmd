# Altirra debugger commands for a HUMAN-PLAYED test of high levels (docs/14-levels.md, "Limit"): you play at normal speed, Pac-Man cannot be killed, the game starts at level @@LEVEL@@ (zero-based counter).
# TEST AIDS (emulated machine only, ROM untouched): start level poked right after the start levels ($ADFD); the death routine is skipped ($A923 -> $A936, same invulnerability as the sweeps).
# Extra evidence for the catch question (docs/18, 'Catches while the frightened phase runs'): CAUGHT (all four ghost states, phase), GHOST_EATEN, PELLET and every GhostState write (ST), so  python -I tools/analyze_catch_log.py <log>  works on a human game.
# NOTHING else is changed: no level-complete flag, no teleports, no dot or pellet pokes - you eat all dots yourself, the game advances levels by its own code.
# Run:  powershell -ExecutionPolicy Bypass -File tools\play_level_test.ps1 -StartLevel 15     then  python -I tools/analyze_levels_log.py F:\Ports\play-level.txt
bp -n a504 "r pc $a537; bc 0"
bp -n adfd "eb $30 @@HEX@@; eb $31 @@HEX@@"
bp -n a923 "r pc $a936"
bt a923 "CAUGHT ghost=%d g0=$%02X g1=$%02X g2=$%02X g3=$%02X FC=%d FD=%d pacx=%d pacy=%d frame=%d" x db($ce) db($cf) db($d0) db($d1) db($fc) db($fd) db($8e) db($89) @frame
bt a888 "ST site=A888 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt afa0 "ST site=AFA0 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b40a "ST site=B40A ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b626 "ST site=B626 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b6d0 "ST site=B6D0 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b756 "ST site=B756 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b764 "ST site=B764 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b853 "ST site=B853 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b895 "ST site=B895 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b8c7 "ST site=B8C7 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt b8ed "ST site=B8ED ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt bab9 "ST site=BAB9 ghost=%d old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" x db($ce+x) db($34)+256*db($36) db($ad) db($ca+x) db($8a+x) db($85+x) db($fd) @frame
bt a800 "ST site=A800 ghost=0 old=$%02X dots=%d chase=%d gtimer=%d x=%d y=%d fright=%d frame=%d" db($ce) db($34)+256*db($36) db($ad) db($ca) db($8a) db($85) db($fd) @frame
bt a886 "GHOST_EATEN ghost=%d frame=%d" x @frame
bt b3de "PELLET frame=%d" @frame
bt a82f "TICK frame=%d" @frame
bt ac7e "LEVEL_ADVANCE level_p1=%d level_p2=%d frame=%d" db($30) db($31) @frame
bt b5c4 "MOVE_DELAY ent=%d delay=%d cycle=%d level=%d" x db($b5+x) db($b0+x) db($30)
bt b3ff "FRIGHT_TIME level=%d FD=$%02X" db($30) db($fd)
bt af77 "FRIGHT_END_CHECK level=%d table=%d FC=%d FD=%d" db($30) db($672+x) db($fc) db($fd)
bt b677 "BONUS_APPEARS level=%d glyph=$%02X,$%02X" db($30) db($df3) db($df4)
bt a95a "BONUS_GLYPHS level=%d g=$%02X $%02X $%02X $%02X $%02X" db($30) db($df1) db($df2) db($df3) db($df4) db($df5)
bt a989 "BONUS_SCORE level=%d thousands=%d hundreds=%d" db($30) db($96) db($97)
bt ad0d "INDICATOR level=%d row=$%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X" db($30) db($f86) db($f87) db($f88) db($f89) db($f8a) db($f8b) db($f8c) db($f8d) db($f8e) db($f8f) db($f90) db($f91) db($f92) db($f93)
bt ae3c "RELEASE_TIMERS level=%d t1=$%02X t2=$%02X t3=$%02X frame=%d" db($30) db($cb) db($cc) db($cd) @frame
bt b758 "RELEASE ghost=%d state=$%02X frame=%d" x db($ce+x) @frame
bt ad0d "ITEM_COLOR level=%d zpA0=$%02X" db($30) db($a0)
bt adaf "LEVEL_SETUP level=%d frame=%d" db($30) @frame
