# Altirra debugger commands: the SOUND SESSION of altirra_sound_events.cmd repeated at other LEVELS and at other DOT COUNTS (OPEN-VERIFICATION.md OV-11, OV-12), with the dot counter in the trace.
# TEMPLATE: tools/run_sound_levels.py replaces @@LEVEL@@ (the level counter poked right after the start levels at $ADFD, as altirra_catch.cmd does; "db($1b)" = no poke, the game's own StartLevel) and @@OPTS@@ (number of OPTION presses at the
# title before START: each moves StartLevel 0,1,2,4,6,8,10,12; 0 = none) and runs it through run_patrol_trace.ps1 at fast speed.
# INPUT: ONE START press (title frame 450) and OPTION presses (title frames 100 + 40 k, 8 frames each) injected at the controller register, the STICK0 bot.
# TEST AIDS (emulated RAM/PC only, ROM untouched; same as altirra_sound_events.cmd except the last two lines of the list):
#   1 Pac-Man cannot die ($A923 -> $A936).   2 The level counter is poked when @@LEVEL@@ is a number.
#   3 In a 900-frame cycle counted from START_PLAY (cyc = 0..4): the dot counter zp_34 is set at p 20-27 to $50 (cyc 0) / $A0 (cyc 1) so the bonus item appears, and to $B2 (cyc 2), $E2 (cyc 3), $F1 (cyc 4): siren steps 3, 4, 5.
#   4 While the bonus item is on screen the hit test at $A93B is forced. 5 Power-pellet flags refilled and Pac-Man placed on the pellet (p 440-457) and on two ghosts (p 520-527, 640-647), every cycle.
# Analysis: python -I tools/analyze_sound_events.py <trace> --lenient     (sounds that cannot occur at a level are information, not failures)
r @t1 0
r @t2 0
r @t3 0
r @t4 0
r @t5 0
r @t7 0
r @t8 0
r @t9 0
bp -n a923 "r pc $a936"
bp -n adfd "eb $30 @@LEVEL@@; eb $31 @@LEVEL@@"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t3 ((@t1>=450)&(@t1<=500))*1+((@t1>=100)&(@t1<100+40*@@OPTS@@)&(((@t1-100)%40)<8))*4"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a800 "r @t2 @frame"
bp -n a82f "r @t6 ((@frame/$30)%4); eb $278 ($0E*(@t6=0))+($07*(@t6=1))+($0D*(@t6=2))+($0B*(@t6=3))"
bp -n a82f "r @t7 (@t2>0)*((@frame-@t2)%900); r @t8 (@t2>0)*((@frame-@t2)/900)"
bp -n a82f "r @t4 (@t2>0)&(@t7>=20)&(@t7<28)&(@t8<5); r @t9 ($50*(@t8=0))+($A0*(@t8=1))+($B2*(@t8=2))+($E2*(@t8=3))+($F1*(@t8=4)); eb $34 (1-@t4)*db($34)+@t4*@t9"
bp -n a82f "r @t5 (@t2>0)&(@t7>=60)&(@t7<400)"
bp -n a93b "r pc $a93b+2*(db($9f)=1)*@t5"
bp -n a82f "r @t4 (@t2>0)&(@t7>=440)&(@t7<448); eb $32 (1-@t4)*db($32)+@t4*$0F; r @t4 (@t2>0)&(@t7>=450)&(@t7<458); eb $8e db($8e)+@t4*($3A-db($8e)); eb $89 db($89)+@t4*($3C-db($89))"
bp -n a82f "r @t9 (@t8%4); r @t4 (@t2>0)&(@t7>=520)&(@t7<528); eb $8e db($8e)+@t4*(db($8a+@t9)-db($8e)); eb $89 db($89)+@t4*(db($85+@t9)-db($89))"
bp -n a82f "r @t9 ((@t8+1)%4); r @t4 (@t2>0)&(@t7>=640)&(@t7<648); eb $8e db($8e)+@t4*(db($8a+@t9)-db($8e)); eb $89 db($89)+@t4*(db($85+@t9)-db($89))"
bt a5fd "FR f=%d lives=%d,%d lv=%d fc=%d fd=%d f2=%d e5=%d f7=%d f4=%d d34=%d d36=%d sl=%d p=%d cyc=%d t1=%d" @frame db($2c) db($2d) db($30) db($fc) db($fd) db($f2) db($e5) db($f7) db($f4) db($34) db($36) db($1b) @t7 @t8 @t1
bta w d200 L9 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos
bt a537 "NEWGAME f=%d" @frame
bt a7c8 "READY_DRAW f=%d" @frame
bt a7f5 "TUNE f=%d x=%d" @frame db($a3)
bt a800 "START_PLAY f=%d" @frame
bt b3de "PELLET f=%d" @frame
bt a886 "GHOST_EATEN f=%d x=%d" @frame x
bt a93d "BONUS_EATEN f=%d" @frame
bt b660 "BONUS_APPEAR f=%d" @frame
bt b487 "EXTRA_LIFE f=%d" @frame
bt ac75 "LEVEL_ADV f=%d" @frame
bt adaf "INIT_BOARD f=%d" @frame
bt aef1 "DEATH_DONE f=%d" @frame
# OPTIONAL (run_patrol_trace.ps1 -Complete, fast runs only): POKEY internal state from the debugger's .pokey at every ghost-eaten start ($A8EC) and at the sweep calls ($B058, $B072): per channel the output level, the CPU cycles
# until the next underflow and the period.  They validate the timer model of tools/pokey_timers.py exactly (python -I tools/analyze_ghost_sweep.py --validate-timers <trace>); the model itself uses no dump.
# (They work in recorded runs too, with the private no-pause settings that tools/record_tune.ps1 uses by default; with Altirra's "Pause when inactive" on, ANY recorded run stalls as soon as another window takes the focus.)
#COMPLETE bt a8ec "POKEYDUMP f=%d vp=%d hp=%d" @frame vpos hpos
#COMPLETE bp -n a8ec ".pokey"
#COMPLETE bt b058 "POKEYDUMP f=%d vp=%d hp=%d" @frame vpos hpos
#COMPLETE bp -n b058 ".pokey"
#COMPLETE bt b072 "POKEYDUMP f=%d vp=%d hp=%d" @frame vpos hpos
#COMPLETE bp -n b072 ".pokey"
