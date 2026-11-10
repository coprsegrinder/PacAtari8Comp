# Altirra debugger commands: when does RAM $07D0/$07D1 (ReverseDir entries for up/down) change? (altirra_transitions.cmd plus a per-frame read; same test aids)
# Altirra debugger commands: log EVERY write to GhostState (all 13 store instructions) with the old value and what the game was doing (step C11, ghost state transitions).
# The tracepoint sits on the store instruction itself, so it fires only when the store runs; the new value is not readable there (the accumulator is not available to expressions)
# and is checked by tools/analyze_transitions_log.py instead: it is derived from the code for each site, and the NEXT write of the same ghost must find it as its old value.
# TEST AIDS (emulated machine only; the sight test and all timers are the game's own): the game is started by jumping to its start-game code (self-clearing breakpoint 0); ghosts do not kill Pac-Man;
# Pac-Man is moved around the junction lattice, onto power pellets and onto ghosts (as in altirra_ghostframes.cmd); and the dots-eaten counter (zp $34/$36) is set to $B1, $E1 and $F1 in turn
# (once per 24,576 frames each) so that the game's own late-board code (Sub_B5C7 / Sub_B616) runs; the counter is reset to 0 at the start of each cycle.
# Each line: ST site=<address of the store> ghost old dots(16 bit) ChaseTimer GhostTimer(ghost) x y FrightenCountdown frame.
# (Debugger arguments are split at spaces, so the expressions contain none.)
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 (@frame%$800); eb $89 db($BB83+((@frame/$80)%10)); eb $8e db($BB8D+((@frame/$500)%10)); r @t7 ((@t5>=$F0)&(@t5<$F8)); eb $32 (@t7*$0F)+(1-@t7)*db($32); r @t7 ((@t5>=$100)&(@t5<$110)); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89)); r @t6 ((@frame/$800)%4); r @t7 ((@t5>=$180)&(@t5<$190)); eb $8e db($8e)+@t7*(db($8a+@t6)-db($8e)); eb $89 db($89)+@t7*(db($85+@t6)-db($89))"
bp -n a82f "r @t8 (@frame%$6000); r @t9 (@t8=$3000); eb $34 db($34)+@t9*($B1-db($34)); r @t9 (@t8=$4000); eb $34 db($34)+@t9*($E1-db($34)); r @t9 (@t8=$5000); eb $34 db($34)+@t9*($F1-db($34)); r @t9 (@t8=0); eb $34 db($34)-@t9*db($34); eb $36 db($36)-@t9*db($36)"
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
bt adaf "INIT_BOARD frame=%d" @frame
bt b384 "DOTSTORE ptr=$%04X pacx=%d pacy=%d dots=%d frame=%d" dw($80) db($8e) db($89) db($34) @frame
