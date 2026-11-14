# Altirra debugger commands: the sight test (GhostSeesPacMan, $BA19) while a ghost is frightened or eaten - docs/15 'sight test', docs/17.
# Code facts: the only caller is the loop at $B603 (in Sub_B5C7, once per frame); it calls GhostSeesPacMan only for a ghost whose state is EXACTLY $08 or $10 (patrol travel / patrol).
# TEST AIDS (emulated RAM/PC only): Pac-Man cannot die ($A923 skipped); from 32 frames after each board set-up Pac-Man is kept on the line of sight of one ghost at a time (target changes every 16 frames):
# same row 24 px in front of a horizontally moving ghost standing on a junction row, or same column 24 px in front of a vertically moving ghost on a junction column; power pellets are eaten 160, 528, 768, 960, 1152, 560, 1088 and 1312 frames after the set-up, and also whenever a ghost is in patrol state $10 and no frightened period is running (so that frightened patrol ghosts $90 occur) (the patrol states $08/$10 only occur from about frame 500 on);
# the level-complete flag is set 1520 frames after the set-up (the game advances the level itself). Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\sightstates.txt -Seconds 110 -Cmd altirra_sight_states.cmd
#   then  python -I tools/analyze_sight_states_log.py analysis/raw-logs/sightstates.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n adaf "r @t1 @frame"
bp -n a82f "r @t5 (@frame-@t1); r @t6 ((@t5/$10)%4); r @t2 db($8a+@t6); r @t3 db($85+@t6); r @t4 db($8f+@t6); r @t9 (((@t5>=$A0)&(@t5<$A8))+((@t5>=$210)&(@t5<$218))+((@t5>=$300)&(@t5<$308))+((@t5>=$3C0)&(@t5<$3C8))+((@t5>=$480)&(@t5<$488))+((@t5>=$230)&(@t5<$238))+((@t5>=$440)&(@t5<$448))+((@t5>=$520)&(@t5<$528))+((db($fc)=0)&(@t5>=$100)&(@t5<$5F0)&(((db($ce)=$10)+(db($cf)=$10)+(db($d0)=$10)+(db($d1)=$10))>0))); r @t0 ((@t5>=$20)&(@t5<$5F0)&(1-@t9)); r @t7 (@t0&((@t4=8)|(@t4=4))&(((@t3=$2c)+(@t3=$44)+(@t3=$54)+(@t3=$64)+(@t3=$74)+(@t3=$84)+(@t3=$94)+(@t3=$a4)+(@t3=$b4)+(@t3=$c4))>0)); eb $89 db($89)+@t7*(@t3-db($89)); eb $8e db($8e)+@t7*(@t2+24*(@t4=8)-24*(@t4=4)-db($8e)); r @t8 (@t0&((@t4=1)|(@t4=2))&(((@t2=$3a)+(@t2=$46)+(@t2=$52)+(@t2=$62)+(@t2=$76)+(@t2=$82)+(@t2=$96)+(@t2=$a6)+(@t2=$b2)+(@t2=$be))>0)); eb $8e db($8e)+@t8*(@t2-db($8e)); eb $89 db($89)+@t8*(@t3+24*(@t4=2)-24*(@t4=1)-db($89))"
bp -n a82f "eb $32 (@t9*$0F)+(1-@t9)*db($32); eb $8e db($8e)+@t9*($3A-db($8e)); eb $89 db($89)+@t9*($3C-db($89)); r @t7 (@t5=$5F0); eb $26 @t7|db($26)"
bt b601 "SL st=$%02X,$%02X,$%02X,$%02X x=%d,%d,%d,%d y=%d,%d,%d,%d d=%d,%d,%d,%d p=%d,%d rt=%d lv=%d f=%d" db($ce) db($cf) db($d0) db($d1) db($8a) db($8b) db($8c) db($8d) db($85) db($86) db($87) db($88) db($8f) db($90) db($91) db($92) db($8e) db($89) db($14) db($30) @frame
bt ba19 "CALL g=%d st=$%02X f=%d" x db($ce+x) @frame
bt bab9 "SIGHTED g=%d f=%d" x @frame
bt b3de "PELLET f=%d" @frame
bt a886 "GHOST_EATEN g=%d f=%d" x @frame
bt adaf "LEVEL_SETUP level=%d f=%d" db($30) @frame
