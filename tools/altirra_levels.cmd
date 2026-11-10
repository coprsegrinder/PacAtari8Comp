# Altirra debugger commands: unattended level sweep (step C11, per-level tables).
# TEST AIDS (they change emulated RAM / PC only, never the ROM; the real game code and tables then run by themselves).
# One cycle = $600 = 1536 frames (about 26 s of game time):
#   phase 0          : set the level-complete flag (zp_26): the game runs its own level-advance code (inc Level, Sub_ADAF, indicator ...)
#   phase >= $200    : set the dot counter (zp_34) to $50: the game's own test at $B658 makes the bonus item appear
#   phase $240-$24F  : move Pac-Man onto the bonus item (PacX $7C, PacY $84): its collision code scores the bonus
#   phase $280-$28F  : move Pac-Man onto a power pellet (PacX $3A, PacY $3C): the game's own pellet test at $B3AF fires
#   always           : a ghost touching Pac-Man does not kill him ($A923 -> $A936)
# Level jumps (at the advance moment, so the game's own level setup runs with the new value): cycle 30 -> Level 99 (then 100), 40 -> 199 (200), 50 -> 250 (251, ..., 255, then the 8-bit wrap to 0).
# @t0 and @t1 are one-shot latches (last cycle in which the advance / dot poke were done), set when a game starts (Sub_ADF1).
# (Debugger arguments are split at spaces, so the expressions contain none.)
# start the game without a key press: the first time the main loop polls CONSOL ($A504) jump to the start-game code ($A537), then
# delete this breakpoint (it is breakpoint 0, the first command of the file) so the busy poll loop is not slowed down
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n adf1 "r @t0 (@frame/$600); r @t1 (@frame/$600)"
bp -n a82f "r @t5 (@frame%$600); r @t6 (@frame/$600); r @t7 ((@t6!=@t0)&(@t6>0)); eb $26 @t7|db($26); eb $30 db($30)+@t7*(((@t6=30)*(99-db($30)))+((@t6=40)*(199-db($30)))+((@t6=50)*(250-db($30)))); r @t0 @t6; r @t7 ((@t5>=$200)&(@t1!=@t6)); eb ($34+db($2b)) @t7*$50+(1-@t7)*db($34+db($2b)); r @t1 (@t1+@t7*(@t6-@t1)); r @t7 ((@t5>=$240)&(@t5<$250)); eb $8e db($8e)+@t7*($7C-db($8e)); eb $89 db($89)+@t7*($84-db($89)); r @t7 ((@t5>=$280)&(@t5<$290)); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89))"
# --- evidence
bt ac7e "LEVEL_ADVANCE level_p1=%d level_p2=%d frame=%d" db($30) db($31) @frame
bt b5c4 "MOVE_DELAY ent=%d delay=%d cycle=%d level=%d" x db($b5+x) db($b0+x) db($30)
bt b3ff "FRIGHT_TIME level=%d FD=$%02X" db($30) db($fd)
bt af77 "FRIGHT_END_CHECK level=%d table=%d FC=%d FD=%d" db($30) db($672+x) db($fc) db($fd)
bt b677 "BONUS_APPEARS level=%d glyph=$%02X,$%02X" db($30) db($df3) db($df4)
bt a95a "BONUS_GLYPHS level=%d g=$%02X $%02X $%02X $%02X $%02X" db($30) db($df1) db($df2) db($df3) db($df4) db($df5)
bt a989 "BONUS_SCORE level=%d thousands=%d hundreds=%d" db($30) db($96) db($97)
bt ad0d "INDICATOR level=%d row=$%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X" db($30) db($f86) db($f87) db($f88) db($f89) db($f8a) db($f8b) db($f8c) db($f8d) db($f8e) db($f8f) db($f90) db($f91) db($f92) db($f93)
# ghost house release (Window3Table -> zp_CB..CD = GhostTimer of ghosts 1..3, 8 jiffies per tick) and the moment each ghost leaves the house
bt ae3c "RELEASE_TIMERS level=%d t1=$%02X t2=$%02X t3=$%02X frame=%d" db($30) db($cb) db($cc) db($cd) @frame
bt adaf "LEVEL_SETUP level=%d frame=%d" db($30) @frame
bt b758 "RELEASE ghost=%d state=$%02X frame=%d" x db($ce+x) @frame
