# Altirra debugger commands: the RARE paths of the frame (OV-64): pauses at several moments (during the start tune, the ready wait and play), SELECT and OPTION pressed during play (play -> title menu), START pressed during play and during the start tune (-> start idle), and the title START again.
# TEST AIDS (emulated RAM/PC only), as in altirra_pause.cmd / altirra_inputs.cmd: Pac-Man cannot die ($A923 skipped); a joystick bot pokes STICK0 ($0278); the keys are the game's own reads: the console value is put into A after the three CONSOL reads of the key loop ($A507, $A514, $A51C), the space bar is CH := $21 at the VBI.
# Counters: @t7 = games started (the start-game code $A537), @t8 = frames since the last start, @t1 = frames since the title menu appeared (state >= 3).  Sequence: START at the title (t1 100), pauses in game 1 at t8 100-140 (start tune), 700-740 (play), 1100-1130; SELECT at t8 1500 (game 1 -> title); START at the title; game 2: pause at 300-330, START at t8 500 (play -> start idle); game 3: START at t8 150 (start tune -> start idle); game 4: OPTION at t8 900 (play -> title), START at the title; game 5 runs on.
# Run through tools/run_mainloop_audit.ps1 -Only rare (it adds the tracepoints of the main-loop audit).
r @t1 0
r @t3 0
r @t7 0
r @t8 0
bp -n a923 "r pc $a936"
bp -n a537 "r @t7 @t7+1; r @t8 0; r @t1 0"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t8 (@t7>0)*(@t8+1)"
bp -n a5fd "r @t3 (((@t1>=100)&(@t1<=108))*1)+(((@t7=1)&(@t8>=1500)&(@t8<=1508))*2)+(((@t7=2)&(@t8>=500)&(@t8<=508))*1)+(((@t7=3)&(@t8>=150)&(@t8<=158))*1)+(((@t7=4)&(@t8>=900)&(@t8<=908))*4)"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a82f "r @t5 ((@t8/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
bp -n a5fd "r @t6 (((@t7=1)&((@t8=100)|(@t8=140)|(@t8=700)|(@t8=740)|(@t8=1100)|(@t8=1130)))|((@t7=2)&((@t8=300)|(@t8=330)))); eb $2fc $21*@t6+db($2fc)*(1-@t6)"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt a537 "NEW_GAME f=%d t7=%d" @frame @t7
bt a4e2 "KEY_TOGGLE f=%d new=%d old=%d" @frame @a db($9b)
