# Altirra debugger commands: TARGETED session for frightened patrol ghosts ($90 = frightened $10, $88 = frightened $08) and the sight test (docs/15, follow-up of altirra_sight_states.cmd).
# Code facts: the only caller of GhostSeesPacMan is the loop at $B603 (once per frame); it calls it only for a ghost whose state is EXACTLY $08 or $10.
# TEST AIDS (emulated RAM/PC only): Pac-Man cannot die ($A923 skipped). ONE LONG BOARD at level 0 (no level-complete flag, no level poke) so that the ghosts go through chase, corner and patrol many times.
# Pac-Man is placed in line of sight (24 px in front, on a junction row/column) ONLY of a ghost that is frightened patrol ($88/$90, $90 first); a ghost in $08/$10 is left alone (otherwise it would sight Pac-Man and turn to chase).
# A power pellet is eaten whenever a ghost is in $10 and no frightened period runs (so that $90 occurs). The dot counter is reset when it passes $60 (keeps the late-board permanent chase away).
# Run: powershell -File tools\run_patrol_trace.ps1 -Log F:\Ports\sightstates90.txt -Seconds 300 -Cmd altirra_sight_states_90.cmd   then   python -I tools/analyze_sight_states_log.py F:/Ports/sightstates90.txt
un_patrol_trace.ps1 -Log F:\Ports\sightstates90.txt -Seconds 300 -Cmd altirra_sight_states_90.cmd   then  python -I tools/analyze_sight_states_log.py F:/Ports/sightstates90.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n adaf "r @t1 @frame"
bp -n a82f "r @t5 (@frame-@t1); r @t6 ((@t5/$10)%4); r @t0 @t6; r @t6 (@t6+(db($ce+((@t0+3)%4))=$88)*(((@t0+3)%4)-@t6)); r @t6 (@t6+(db($ce+((@t0+2)%4))=$88)*(((@t0+2)%4)-@t6)); r @t6 (@t6+(db($ce+((@t0+1)%4))=$88)*(((@t0+1)%4)-@t6)); r @t6 (@t6+(db($ce+((@t0+0)%4))=$88)*(((@t0+0)%4)-@t6)); r @t6 (@t6+(db($ce+((@t0+3)%4))=$90)*(((@t0+3)%4)-@t6)); r @t6 (@t6+(db($ce+((@t0+2)%4))=$90)*(((@t0+2)%4)-@t6)); r @t6 (@t6+(db($ce+((@t0+1)%4))=$90)*(((@t0+1)%4)-@t6)); r @t6 (@t6+(db($ce+((@t0+0)%4))=$90)*(((@t0+0)%4)-@t6)); r @t2 db($8a+@t6); r @t3 db($85+@t6); r @t4 db($8f+@t6); r @t9 ((db($fc)=0)&(((db($ce)=$10)+(db($cf)=$10)+(db($d0)=$10)+(db($d1)=$10))>0)); r @t0 ((1-@t9)&((db($ce+@t6)=$88)|(db($ce+@t6)=$90))); r @t7 (@t0&((@t4=8)|(@t4=4))&(((@t3=$2c)+(@t3=$44)+(@t3=$54)+(@t3=$64)+(@t3=$74)+(@t3=$84)+(@t3=$94)+(@t3=$a4)+(@t3=$b4)+(@t3=$c4))>0)); eb $89 db($89)+@t7*(@t3-db($89)); eb $8e db($8e)+@t7*(@t2+24*(@t4=8)-24*(@t4=4)-db($8e)); r @t8 (@t0&((@t4=1)|(@t4=2))&(((@t2=$3a)+(@t2=$46)+(@t2=$52)+(@t2=$62)+(@t2=$76)+(@t2=$82)+(@t2=$96)+(@t2=$a6)+(@t2=$b2)+(@t2=$be))>0)); eb $8e db($8e)+@t8*(@t2-db($8e)); eb $89 db($89)+@t8*(@t3+24*(@t4=2)-24*(@t4=1)-db($89))"
bp -n a82f "eb $32 (@t9*$0F)+(1-@t9)*db($32); eb $8e db($8e)+@t9*($3A-db($8e)); eb $89 db($89)+@t9*($3C-db($89)); eb $34 db($34)*(db($34)<$60)"
bt b601 "SL st=$%02X,$%02X,$%02X,$%02X x=%d,%d,%d,%d y=%d,%d,%d,%d d=%d,%d,%d,%d p=%d,%d rt=%d lv=%d f=%d" db($ce) db($cf) db($d0) db($d1) db($8a) db($8b) db($8c) db($8d) db($85) db($86) db($87) db($88) db($8f) db($90) db($91) db($92) db($8e) db($89) db($14) db($30) @frame
bt ba19 "CALL g=%d st=$%02X f=%d" x db($ce+x) @frame
bt bab9 "SIGHTED g=%d f=%d" x @frame
bt b3de "PELLET f=%d" @frame
bt a886 "GHOST_EATEN g=%d f=%d" x @frame
bt adaf "LEVEL_SETUP level=%d f=%d" db($30) @frame
