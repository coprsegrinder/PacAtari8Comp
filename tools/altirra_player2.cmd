# Altirra debugger commands: TWO-PLAYER game, player 2's counter ($31) and the per-player state (step C11, docs/19-two-players.md).
# TEST AIDS (emulated machine only; the game's own code does all the work):
#   start: the first time the main loop polls CONSOL ($A504) jump to the start-game code ($A537) with zp_1A (the 1/2-player flag that SELECT toggles on the title screen) set to 1; breakpoint 0 deletes itself
#   just after both level counters are set to the start level ($ADFD): player 1 := level 2, player 2 := level 7, so that the two counters differ
#   every cycle of $800 frames: phase 0 level-complete flag (zp_26) for the CURRENT player (the game's own AdvanceLevel runs) and both life counters set to 3 (so the game never ends);
#   phase >= $200 the current player's dot counter set to $50 (the bonus item appears); $240-$24F Pac-Man moved onto the bonus item; $280-$28F onto a power pellet
#   NO no-kill aid: ghosts kill Pac-Man, so the turn passes to the other player by the game's own code (idle Pac-Man is caught within a minute)
#   cycles 3-6, phase $300: the 10,000s digit of the CURRENT player's score ($202B / $2048) set to 1 (the game's own extra-life test then runs at the next score addition; once per player)
# Evidence: every per-level table read logged with the CURRENT player's level ($30 + CurrentPlayer) and analysed like the one-player sweep (analyze_levels_log.py), plus the player switches with a snapshot of all per-player variables.
# (Debugger arguments are split at spaces, so the expressions contain none.)
bp -n a504 "r pc $a537; eb $1a 1; bc 0"
bp -n adfd "eb $30 2; eb $31 7"
bp -n adf1 "r @t0 (@frame/$800); r @t1 (@frame/$800)"
bp -n a82f "r @t5 (@frame%$800); r @t6 (@frame/$800); r @t7 ((@t5=0)&(@t6>0)); eb $26 @t7|db($26); eb $2c db($2c)+@t7*(3-db($2c)); eb $2d db($2d)+@t7*(3-db($2d)); r @t7 ((@t5>=$200)&(@t1!=@t6)); eb ($34+db($2b)) @t7*$50+(1-@t7)*db($34+db($2b)); r @t1 (@t1+@t7*(@t6-@t1)); r @t7 ((@t5>=$240)&(@t5<$250)); eb $8e db($8e)+@t7*($7C-db($8e)); eb $89 db($89)+@t7*($84-db($89)); r @t7 ((@t5>=$280)&(@t5<$290)); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89)); r @t7 ((@t5=$300)&(@t6>=3)&(@t6<=6)); eb ($202b+db($2b)*$1D) db($202b+db($2b)*$1D)+@t7*(1-db($202b+db($2b)*$1D))"
bt ac7e "LEVEL_ADVANCE level_p1=%d level_p2=%d frame=%d" db($30+db($2b)) db($31) @frame
bt ac7e "PLAYER_ADVANCE player=%d p1=%d p2=%d lives=%d,%d frame=%d" db($2b) db($30) db($31) db($2c) db($2d) @frame
bt b5c4 "MOVE_DELAY ent=%d delay=%d cycle=%d level=%d player=%d" x db($b5+x) db($b0+x) db($30+db($2b)) db($2b)
bt b3ff "FRIGHT_TIME level=%d FD=$%02X player=%d" db($30+db($2b)) db($fd) db($2b)
bt af77 "FRIGHT_END_CHECK level=%d table=%d FC=%d FD=%d player=%d" db($30+db($2b)) db($672+x) db($fc) db($fd) db($2b)
bt b677 "BONUS_APPEARS level=%d glyph=$%02X,$%02X player=%d" db($30+db($2b)) db($df3) db($df4) db($2b)
bt a95a "BONUS_GLYPHS level=%d g=$%02X $%02X $%02X $%02X $%02X player=%d" db($30+db($2b)) db($df1) db($df2) db($df3) db($df4) db($df5) db($2b)
bt a989 "BONUS_SCORE level=%d thousands=%d hundreds=%d player=%d" db($30+db($2b)) db($96) db($97) db($2b)
bt ad0d "INDICATOR level=%d row=$%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X $%02X" db($30+db($2b)) db($f86) db($f87) db($f88) db($f89) db($f8a) db($f8b) db($f8c) db($f8d) db($f8e) db($f8f) db($f90) db($f91) db($f92) db($f93)
bt ae3c "RELEASE_TIMERS level=%d t1=$%02X t2=$%02X t3=$%02X frame=%d player=%d" db($30+db($2b)) db($cb) db($cc) db($cd) @frame db($2b)
bt adaf "LEVEL_SETUP level=%d frame=%d player=%d" db($30+db($2b)) @frame db($2b)
bt b758 "RELEASE ghost=%d state=$%02X frame=%d" x db($ce+x) @frame
bt ad0d "ITEM_COLOR level=%d zpA0=$%02X player=%d" db($30+db($2b)) db($a0) db($2b)
bt aa61 "SWITCH to=0 from=%d 1a=%d lives=%d,%d level=%d,%d flags=$%02X,$%02X dots=%d,%d eml=%d,%d zp43=%d,%d s1=%02X%02X%02X%02X%02X%02X s2=%02X%02X%02X%02X%02X%02X frame=%d" db($2b) db($1a) db($2c) db($2d) db($30) db($31) db($32) db($33) db($34)+256*db($36) db($35)+256*db($37) db($2e) db($2f) db($43) db($44) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($2047) db($2048) db($2049) db($204a) db($204b) db($204c) @frame
bt aa8b "SWITCH to=1 from=%d 1a=%d lives=%d,%d level=%d,%d flags=$%02X,$%02X dots=%d,%d eml=%d,%d zp43=%d,%d s1=%02X%02X%02X%02X%02X%02X s2=%02X%02X%02X%02X%02X%02X frame=%d" db($2b) db($1a) db($2c) db($2d) db($30) db($31) db($32) db($33) db($34)+256*db($36) db($35)+256*db($37) db($2e) db($2f) db($43) db($44) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($2047) db($2048) db($2049) db($204a) db($204b) db($204c) @frame
bt ad13 "LIFE_LOST player=%d lives=%d,%d frame=%d" db($2b) db($2c) db($2d) @frame
bt b487 "EXTRA_LIFE player=%d frame=%d" db($2b) @frame
bt b432 "SCORE_ADD player=%d base=$%02X" db($2b) x
bt adf1 "NEW_GAME frame=%d" @frame
bt adaf "BOARD_START cur=%d lives=%d,%d level=%d,%d flags=$%02X,$%02X dots=%d,%d eml=%d,%d zp43=%d,%d s1=%02X%02X%02X%02X%02X%02X s2=%02X%02X%02X%02X%02X%02X frame=%d" db($2b) db($2c) db($2d) db($30) db($31) db($32) db($33) db($34)+256*db($36) db($35)+256*db($37) db($2e) db($2f) db($43) db($44) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($2047) db($2048) db($2049) db($204a) db($204b) db($204c) @frame
