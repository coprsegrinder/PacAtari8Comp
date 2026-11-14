# Altirra debugger commands: ONE long session from the title screen through several whole games (docs/21): first board start with its tune, game over, high-score comparison, the 30 s countdown, the return to the title, and keys pressed during the countdown.
# NO STATE IS CHANGED. The only injected things are the values the game READS from the controller registers, at the exact instructions that read them (the ROM is untouched and no game variable is written):
#   joystick bot: STICK0 ($0278) as in altirra_death.cmd (direction only); START/SELECT/OPTION: the byte the game gets from CONSOL ($D01F) after the load at $A504/$A511 and while it waits for release at $A51C; trigger: STRIG0/STRIG1 shadows ($0284/$0285) before the loads at $A4FA/$A4FF.
#   No life counter is refilled, no PC is moved, no timer is poked (altirra_gameover.cmd jumped to $A537 to start the game: that aid is gone). A real F2 key event posted to Altirra's window (run_patrol_trace.ps1 -PressStart) does NOT start the game, so START is injected at CONSOL.
#   PASSIVE mode (a person plays in Altirra's window): run_patrol_trace.ps1 -Cmd altirra_fullgame.cmd -Ini external-tools\Altirra\Altirra.ini -Drop '^bp -n (a82f |a507|a514|a51c|a4fa|a4ff|a5fd "r @t[345])' leaves out every injection (docs/21).
# Schedule (g = number of games started so far, counted by the NEWGAME events, @t7):
#   g=0 title: START at title frame 120-170.  g=1: nothing during the countdown (full 30 s), then at the title (state 4) a STRIG0 press at title frame 200-260.
#   g=2: START during the countdown at zp_1E 100-93.  g=3: STRIG0 at 150-143.  g=4: STRIG1 at 150-143.  g=5: OPTION at 100-93, then START at the title (state 3) frame 120-170.
#   g=6: SELECT at 100-93 (toggles the number of players), then START at the title.  g=7 (two players): nothing, full countdown, stays at the title.
# Run: powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\fullgame.txt -Seconds 400 -Cmd altirra_fullgame.cmd    then   python -I tools/analyze_fullgame_log.py analysis/raw-logs/fullgame.txt
r @t1 0
r @t3 0
r @t4 0
r @t5 0
r @t7 0
bp -n a537 "r @t7 @t7+1"
bp -n a82f "r @t6 ((@frame/$30)%4); eb $278 ($0E*(@t6=0))+($07*(@t6=1))+($0D*(@t6=2))+($0B*(@t6=3))"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t3 ((@t7=2)&(db($19)=0)&(db($20)=1)&(db($1e)<=100)&(db($1e)>=93))*1+((@t7=5)&(db($19)=0)&(db($20)=1)&(db($1e)<=100)&(db($1e)>=93))*4+((@t7=6)&(db($19)=0)&(db($20)=1)&(db($1e)<=100)&(db($1e)>=93))*2+((@t7=5)&(db($19)=3)&(@t1>=120)&(@t1<=170))*1+((@t7=6)&(db($19)=3)&(@t1>=120)&(@t1<=170))*1"
bp -n a5fd "r @t3 @t3+((@t7=0)&(@t1>=120)&(@t1<=170))"
bp -n a5fd "r @t4 ((@t7=1)&(db($19)=4)&(@t1>=200)&(@t1<=260))+((@t7=3)&(db($19)=0)&(db($20)=1)&(db($1e)<=150)&(db($1e)>=143))"
bp -n a5fd "r @t5 ((@t7=4)&(db($19)=0)&(db($20)=1)&(db($1e)<=150)&(db($1e)>=143))"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a4fa "eb $284 1-@t4"
bp -n a4ff "eb $285 1-@t5"
bt a5fd "FR f=%d g=%d z19=%d z1a=%d z1b=%d z1c=%d z1d=%d z1e=%d z20=%d z21=%d z22=%d z23=%d z24=%d z25=%d z26=%d a3=%d at=%d z45=%d z46=%d z9b=%d cp=%d lives=%d,%d lv=%d,%d sl=%02X%02X ch=$%02X c=$%02X,$%02X,$%02X,$%02X,$%02X in=%d,%d,%d s1=%02X%02X%02X%02X%02X%02X s2=%02X%02X%02X%02X%02X%02X hi=%02X%02X%02X%02X%02X%02X ds=%d gs=$%02X,$%02X,$%02X,$%02X px=%d py=%d" @frame @t7 db($19) db($1a) db($1b) db($1c) db($1d) db($1e) db($20) db($21) db($22) db($23) db($24) db($25) db($26) db($a3) db($4d) db($45) db($46) db($9b) db($2b) db($2c) db($2d) db($30) db($31) db($231) db($230) db($2fc) db($2c4) db($2c5) db($2c6) db($2c7) db($2c8) @t3 @t4 @t5 db($202a) db($202b) db($202c) db($202d) db($202e) db($202f) db($2047) db($2048) db($2049) db($204a) db($204b) db($204c) db($2039) db($203a) db($203b) db($203c) db($203d) db($203e) db($ed) db($ce) db($cf) db($d0) db($d1) db($8e) db($89)
bt a537 "NEWGAME f=%d z19=%d z20=%d z1e=%d z1a=%d" @frame db($19) db($20) db($1e) db($1a)
bt a544 "KEY_SELECT f=%d z19=%d z20=%d z1e=%d z1a=%d" @frame db($19) db($20) db($1e) db($1a)
bt a559 "KEY_OPTION f=%d z19=%d z20=%d z1e=%d startlevel=%d" @frame db($19) db($20) db($1e) db($1b)
bt a550 "TO_TITLE3 f=%d z19=%d z20=%d z1e=%d" @frame db($19) db($20) db($1e)
bt a554 "SET_Z19 f=%d new=%d z20=%d z1e=%d" @frame db($19) db($20) db($1e)
bt a4f1 "COUNTDOWN_DONE f=%d z19=%d z20=%d z1e=%d" @frame db($19) db($20) db($1e)
bt a477 "RESTART f=%d z19=%d z20=%d z1c=%d" @frame db($19) db($20) db($1c)
bt a4a3 "MAIN_INITBOARD f=%d" @frame
bt a4a6 "MAIN_ADF1 f=%d z1a=%d" @frame db($1a)
bt a632 "SUB_A632 f=%d" @frame
bt a64e "SUB_A64E f=%d" @frame
bt a4b6 "MAIN_DONE f=%d" @frame
bt a7c8 "READY_DRAW f=%d z22=%d" @frame db($22)
bt a7f5 "TUNE f=%d x=%d a1=$%02X a2=$%02X rt=%d" @frame db($a3) db($bc50+db($a3)) db($bc90+db($a3)) db($14)
bt a7fb "TUNE_AD0E f=%d lives=%d,%d" @frame db($2c) db($2d)
bt a7fe "TUNE_DONE f=%d" @frame
bt a800 "START_PLAY f=%d" @frame
bt ac93 "LEVEL_INDICATOR f=%d" @frame
bt ad5e "CLEAR_READY f=%d" @frame
bt adaf "INITBOARD f=%d" @frame
bt ad0e "SUB_AD0E f=%d" @frame
bt ad13 "TURN_START lives=%d f=%d" db($2c) @frame
bt a923 "DEATH_START f=%d" @frame
bt aef1 "DEATH_DONE f=%d" @frame
bt aae6 "INITBOARD_CALL f=%d lives=%d" @frame db($2c)
bt aaef "GAME_OVER_TEXT f=%d z23=%d z1a=%d cp=%d lives=%d,%d" @frame db($23) db($1a) db($2b) db($2c) db($2d)
bt ab26 "HS_ENTRY x=%d f=%d s=%02X%02X%02X%02X%02X%02X hi=%02X%02X%02X%02X%02X%02X" x @frame db($2000+x) db($2001+x) db($2002+x) db($2003+x) db($2004+x) db($2005+x) db($2039) db($203a) db($203b) db($203c) db($203d) db($203e)
bt ab3a "HS_RET_EQUAL f=%d hi=%02X%02X%02X%02X%02X%02X" @frame db($2039) db($203a) db($203b) db($203c) db($203d) db($203e)
bt ab3b "HS_COPY y=%d x=%d f=%d" y x @frame
bt ab47 "HS_RET f=%d hi=%02X%02X%02X%02X%02X%02X" @frame db($2039) db($203a) db($203b) db($203c) db($203d) db($203e)
bta w 2039 L6 "HSW pc=$%04X f=%d" pc @frame
bta w d200 L8 "SNDW pc=$%04X f=%d" pc @frame
bta w 0ded L14 "TEXTW pc=$%04X f=%d" pc @frame
