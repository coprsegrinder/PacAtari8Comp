# Altirra debugger commands: the KEY LOOP's rare outcomes (OV-65, tools/run_keyloop_audit.ps1): the OPTION key pressed ten times at the title (StartLevel 0 1 2 4 6 8 10 12 0 1: both sides of `cmp #2`, of `cmp #$0C`, the reset), a console value that CHANGES during the debounce (the `cmp zp_46` of $A518 fails and the loop reads again), and the second joystick button (STRIG1) that starts the game.
# Title (state 3, frame counter t1 = frames since the title menu appeared): OPTION ($03) held for 9 frames at t1 60, 80, ..., 240; at t1 300 to 308 the first CONSOL read gives SELECT ($05) and the debounce read gives nothing ($07); STRIG1 = 0 from t1 450 for 10 frames.
# The values are put into A after the three CONSOL reads of the key loop ($A507, $A514, $A51C), as in altirra_inputs.cmd.  TEST AIDS (emulated machine only): Pac-Man cannot die ($A923 skipped).
r @t1 0
r @t3 0
r @t2 0
r @t7 0
bp -n a923 "r pc $a936"
bp -n a537 "r @t7 @t7+1"
bp -n a5fd "r @t1 (db($19)>=3)*(@t7=0)*(@t1+1)"
bp -n a5fd "r @t3 (((@t1>=60)&(@t1<=68))|((@t1>=80)&(@t1<=88))|((@t1>=100)&(@t1<=108))|((@t1>=120)&(@t1<=128))|((@t1>=140)&(@t1<=148))|((@t1>=160)&(@t1<=168))|((@t1>=180)&(@t1<=188))|((@t1>=200)&(@t1<=208))|((@t1>=220)&(@t1<=228))|((@t1>=240)&(@t1<=248)))*4+((@t1>=300)&(@t1<=308))*2"
bp -n a5fd "r @t2 @t3*(1-((@t1>=300)&(@t1<=308)))"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t2"
bp -n a51c "r a 6+(@t3>0)"
bp -n a4fa "eb $284 1"
bp -n a4ff "eb $285 1-((@t1>=450)&(@t1<=460))"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt a537 "NEW_GAME f=%d t1=%d" @frame @t1
