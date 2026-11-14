# Altirra debugger commands: provoke and trace the SOUNDS that no earlier run reached (OPEN-VERIFICATION.md OV-10): ghost eaten ($A8EE, $B049-$B088), frightened phase ($B021/$B028), eyes returning ($B042), bonus item eaten ($ABFE/$AC01), plus extra life and level complete (no sound routine exists for them).
# Use with tools/record_tune.ps1 -Cmd altirra_sound_events.cmd -Trace analysis/raw-logs/sound-events.txt -Out analysis/sound-events-recorded.wav -Seconds 220  (the recording is made at normal speed), then  python -I tools/analyze_tail_sound.py analysis/sound-events-recorded.wav analysis/raw-logs/sound-events.txt
# INPUT (as in the other sessions): ONE START press injected at the CONSOL read (title frame 900, after the recording has started) and the STICK0 bot.
# TEST AIDS (emulated machine only, the ROM is never changed; every one is listed here and in OPEN-VERIFICATION.md):
#   1  Pac-Man cannot die: $A923 -> $A936 (as altirra_catch.cmd / altirra_house_frightened.cmd).
#   2  A repeating cycle of 1500 frames counted from START_PLAY (p = frames into the cycle, cyc = cycle number):
#      p 20-27, cyc 0 and 1: the dot counter zp_34 is set to $50 (cyc 0) or $A0 (cyc 1) so that the bonus item appears (the game appears it at 80 and 160 dots).
#      p 60-599: while the bonus item is on screen (zp_9F = 1) the collision test at $A93B is forced to "hit" (the hardware collision M2PF is not produced because Pac-Man is not steered onto the item); the routine behind it (score, pop-up, sound start) is the game's.
#      p 690-697: the power pellet flags zp_32 := $0F (refill).  p 700-707: Pac-Man is placed on the top-left power pellet (X=$3A, Y=$3C), as altirra_catch.cmd does: the game eats the pellet.
#      p 800-807 and 950-957: Pac-Man is placed on ghost (cyc mod 4) and ghost (cyc+1 mod 4) (the game's own contact test then eats the frightened ghost).
#      cyc 2, p 10-17: player 1's score is set to 9990 (score bytes $202C-$202F), so the next dot makes 10000 (the game's extra life).
#      cyc 3, p 1400-1407: the level-complete flag zp_26 is set (the game's own board end, flashing, AdvanceLevel and new board follow).
#   No other game variable is written; no sound register is written by the harness.
# Trace: every write to $D200-$D20F with value, PC, frame and beam position (SNDW), a short line per frame (FR, also makes the log flush), and the game events.
r @t1 0
r @t2 0
r @t3 0
r @t4 0
r @t5 0
r @t7 0
r @t8 0
r @t9 0
bp -n a923 "r pc $a936"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t3 (@t1>=900)&(@t1<=950)"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a800 "r @t2 @frame"
bp -n a82f "r @t6 ((@frame/$30)%4); eb $278 ($0E*(@t6=0))+($07*(@t6=1))+($0D*(@t6=2))+($0B*(@t6=3))"
bp -n a82f "r @t7 (@t2>0)*((@frame-@t2)%1500); r @t8 (@t2>0)*((@frame-@t2)/1500)"
bp -n a82f "r @t4 (@t2>0)&(@t7>=20)&(@t7<28)&(@t8<2); eb $34 (1-@t4)*db($34)+@t4*($50+$50*(db($43)=1))"
bp -n a82f "r @t5 (@t2>0)&(@t7>=60)&(@t7<600)"
bp -n a93b "r pc $a93b+2*(db($9f)=1)*@t5"
bp -n a82f "r @t4 (@t2>0)&(@t8=2)&(@t7>=10)&(@t7<18); eb $202c (1-@t4)*db($202c)+@t4*$19; eb $202d (1-@t4)*db($202d)+@t4*$19; eb $202e (1-@t4)*db($202e)+@t4*$19; eb $202f (1-@t4)*db($202f)+@t4*$10"
bp -n a82f "r @t4 (@t2>0)&(@t7>=690)&(@t7<698); eb $32 (1-@t4)*db($32)+@t4*$0F; r @t4 (@t2>0)&(@t7>=700)&(@t7<708); eb $8e db($8e)+@t4*($3A-db($8e)); eb $89 db($89)+@t4*($3C-db($89))"
bp -n a82f "r @t9 (@t8%4); r @t4 (@t2>0)&(@t7>=800)&(@t7<808); eb $8e db($8e)+@t4*(db($8a+@t9)-db($8e)); eb $89 db($89)+@t4*(db($85+@t9)-db($89))"
bp -n a82f "r @t9 ((@t8+1)%4); r @t4 (@t2>0)&(@t7>=950)&(@t7<958); eb $8e db($8e)+@t4*(db($8a+@t9)-db($8e)); eb $89 db($89)+@t4*(db($85+@t9)-db($89))"
bp -n a82f "r @t4 (@t2>0)&(@t8=3)&(@t7>=1400)&(@t7<1408); eb $26 db($26)|@t4"
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
