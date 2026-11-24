# Altirra debugger commands: OV-57 - can an eaten ghost reach the door square moving UP (the path $B6C6-$B6CC of EyesAndHousePerFrame)?  docs/18 ('At the door square'), docs/OPEN-VERIFICATION.md OV-57.
# The idea: a ghost that LEAVES the house while frightened (state $80, walking up the door column) is eaten the moment it touches Pac-Man; its direction (up) is kept, so the eyes arrive at the door square (124,100) moving up.
# Every board: a power pellet is eaten EARLY (4 * (b mod 16) + 20 frames after the set-up, before the ghosts leave), then Pac-Man stands on the DOOR SQUARE (124,100) from 20 frames later until frame 1400, the frightened time is held
# (FrightenCountdown $FD = $FF) so that ghosts 1-3 come out of the house frightened, one after the other, into Pac-Man.  The level counter is set to b mod 6 at every board set-up (release timers and frightened time differ).
# TEST AIDS (emulated RAM/PC only, as in altirra_frightened_cases.cmd): Pac-Man cannot die ($A923 skipped); the pellet is eaten by putting Pac-Man on it (x $3A, y $3C) and marking the pellets present ($32) for 16 frames;
# Pac-Man's position is written to $89 / $8E; $FD is held; the level is ended at frame $5F0.  Nothing else is touched: the game's own logic decides eating, the eyes' return and the direction.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\door-up.txt -Seconds 150 -Cmd altirra_door_up.cmd      then  python -I tools/analyze_door_up.py analysis/raw-logs/door-up.txt
r @t0 0
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n adaf "r @t0 @t0+1; r @t1 @frame; eb $30 ((@t0-1)%6); eb $31 ((@t0-1)%6)"
bp -n a82f "r @t5 (@frame-@t1); r @t4 (20+4*((@t0-1)%16))"
bp -n a82f "r @t7 ((@t5>=@t4)&(@t5<(@t4+16)))"
bp -n a82f "r @t2 ((@t5>=(@t4+20))&(@t5<1400))"
bp -n a82f "eb $32 (@t7*$0F)+(1-@t7)*db($32); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89))"
bp -n a82f "eb $89 @t2*100+(1-@t2)*db($89); eb $8e @t2*124+(1-@t2)*db($8e)"
bp -n a82f "r @t8 ((@t5>=(@t4+16))&(@t5<1400)); eb $fd @t8*$FF+(1-@t8)*db($fd)"
bp -n a82f "r @t3 (@t5=$5F0); eb $26 @t3|db($26)"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt adaf "INIT_BOARD board=%d level=%d f=%d" @t0 db($30) @frame
bt b3de "PELLET f=%d t5=%d" @frame @t5
bt a88a "EATEN g=%d dir=%d x=%d y=%d st=$%02X px=%d py=%d f=%d t5=%d" x db($8f+x) db($8a+x) db($85+x) db($ce+x) db($8e) db($89) @frame @t5
bt b738 "LEAVE g=%d y=%d st=$%02X dir=%d f=%d" x db($85+x) db($ce+x) db($8f+x) @frame
bt b6c0 "EY_DOOR g=%d dir=%d st=$%02X x=%d y=%d f=%d" x db($8f+x) db($ce+x) db($8a+x) db($85+x) @frame
bt b6c6 "EY_UP g=%d st=$%02X f=%d" x db($ce+x) @frame
bt b6ce "EY_STATE44 g=%d dir=%d f=%d" x db($8f+x) @frame
bt b764 "HOME g=%d st=$%02X f=%d" x db($ce+x) @frame
