# Altirra debugger commands: the SECOND EXTRA LIFE and BOARD CHANGES at other levels (OPEN-VERIFICATION.md OV-19b, OV-33).  Run (fast, like altirra_sound_levels.cmd):
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools
un_patrol_trace.ps1 -Log analysis
aw-logs\extra-life.txt -Seconds 170 -Cmd altirra_extra_life.cmd     then   python -I tools/analyze_extra_life.py analysis
aw-logs\extra-life.txt
# INPUT: ONE START press (title frame 450) and the STICK0 bot (as the other sessions).
# TEST AIDS (emulated RAM/PC only, ROM untouched): 1 Pac-Man cannot die ($A923 -> $A936).  2 A cycle of 1500 frames counted from the FIRST START_PLAY (p = frame in the cycle, cyc = cycle):
#   cyc 0, p 10-17: player 1's score bytes $202C-$202F := 9990 (the next dot makes 10,000: the first extra life).
#   cyc 1, p 10-17: score := 19,990 ($202B := 1)  -> the next dot makes 20,000: NO second extra life is expected (flag zp_2E is set).
#   cyc 2, p 10-17: score := 99,990 ($202B := 9)  -> the next dot makes 100,000 (a carry into $202A): none expected.
#   cyc 3-6, p 10-17: the level counter ($30/$31) := 3, 7, 12, 20; at p 100-107 the level-complete flag zp_26 is set (the game's own board end, flashing, AdvanceLevel and the new board follow).
#   No sound register and no other game variable is written by the harness.
r @t1 0
r @t2 0
r @t3 0
r @t4 0
r @t5 0
r @t6 0
r @t7 0
r @t8 0
r @t9 0
bp -n a923 "r pc $a936"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t3 ((@t1>=450)&(@t1<=500))*1"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a800 "r @t2 @t2+(@t2=0)*@frame"
bp -n a82f "r @t6 ((@frame/$30)%4); eb $278 ($0E*(@t6=0))+($07*(@t6=1))+($0D*(@t6=2))+($0B*(@t6=3))"
bp -n a82f "r @t7 (@t2>0)*((@frame-@t2)%1500); r @t8 (@t2>0)*((@frame-@t2)/1500)"
bp -n a82f "r @t4 (@t2>0)&(@t8=0)&(@t7>=10)&(@t7<18); eb $202c (1-@t4)*db($202c)+@t4*$19; eb $202d (1-@t4)*db($202d)+@t4*$19; eb $202e (1-@t4)*db($202e)+@t4*$19; eb $202f (1-@t4)*db($202f)+@t4*$10"
bp -n a82f "r @t4 (@t2>0)&(@t8=1)&(@t7>=10)&(@t7<18); eb $202b (1-@t4)*db($202b)+@t4*$11; eb $202c (1-@t4)*db($202c)+@t4*$19; eb $202d (1-@t4)*db($202d)+@t4*$19; eb $202e (1-@t4)*db($202e)+@t4*$19; eb $202f (1-@t4)*db($202f)+@t4*$10"
bp -n a82f "r @t4 (@t2>0)&(@t8=2)&(@t7>=10)&(@t7<18); eb $202b (1-@t4)*db($202b)+@t4*$19; eb $202c (1-@t4)*db($202c)+@t4*$19; eb $202d (1-@t4)*db($202d)+@t4*$19; eb $202e (1-@t4)*db($202e)+@t4*$19; eb $202f (1-@t4)*db($202f)+@t4*$10"
bp -n a82f "r @t9 ($03*(@t8=3))+($07*(@t8=4))+($0C*(@t8=5))+($14*(@t8=6)); r @t4 (@t2>0)&(@t8>=3)&(@t8<=6)&(@t7>=10)&(@t7<18); eb $30 (1-@t4)*db($30)+@t4*@t9; eb $31 (1-@t4)*db($31)+@t4*@t9"
bp -n a82f "r @t4 (@t2>0)&(@t8>=3)&(@t8<=6)&(@t7>=100)&(@t7<108); eb $26 db($26)|@t4"
bt a5fd "FR f=%d z19=%d z20=%d z21=%d lives=%d,%d lv=%d fc=%d fd=%d f2=%d e5=%d f7=%d f4=%d s1=%02X%02X%02X%02X%02X%02X p=%d cyc=%d t1=%d" @frame db($19) db($20) db($21) db($2c) db($2d) db($30) db($fc) db($fd) db($f2) db($e5) db($f7) db($f4) db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) @t7 @t8 @t1
bta w d200 L16 "SNDW a=$%04X v=$%02X pc=$%04X f=%d vp=%d hp=%d" @address @value pc @frame vpos hpos
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
