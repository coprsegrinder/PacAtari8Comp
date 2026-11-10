# Altirra debugger commands: log every ghost draw (StepAndDrawEntity, $B96A) and cover all ghost states (step C11, ghost frames).
# TEST AIDS (emulated machine only): the game is started by jumping to its start-game code (self-clearing breakpoint 0); ghosts do not kill Pac-Man;
# Pac-Man is moved to a new junction row every 128 frames and a new column every 1280 frames (so ghosts line up with him and patrol);
# every 2048 frames: the pellet flags are refilled and Pac-Man is moved onto a power pellet (the game's own pellet code starts frightened mode), then, about 100 frames later,
# onto the position of ghost (cycle mod 4) so that the game's own collision code eats it.
# (Debugger arguments are split at spaces, so the expressions contain none.)
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 (@frame%$800); eb $89 db($BB83+((@frame/$80)%10)); eb $8e db($BB8D+((@frame/$500)%10)); r @t7 ((@t5>=$F0)&(@t5<$F8)); eb $32 (@t7*$0F)+(1-@t7)*db($32); r @t7 ((@t5>=$100)&(@t5<$110)); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89)); r @t6 ((@frame/$800)%4); r @t7 ((@t5>=$180)&(@t5<$190)); eb $8e db($8e)+@t7*(db($8a+@t6)-db($8e)); eb $89 db($89)+@t7*(db($85+@t6)-db($89))"
# --- evidence: every ghost draw, the frame it chose, what it was chosen from, and the colour register of that ghost
bt b96a "GHOST_DRAW ghost=%d src=$%04X state=$%02X dir=%d af=%d feet=$%02X color=$%02X" x dw($3c) db($ce+x) db($8f+x) db($af) db($41c) db($2c0+x)
bt ac15 "AF_TOGGLE to=1 rtclok=%d frame=%d" db($14) @frame
bt ac11 "AF_TOGGLE to=0 rtclok=%d frame=%d" db($14) @frame
bt a886 "GHOST_EATEN ghost=%d frame=%d" x @frame
bt b3de "PELLET frame=%d" @frame
