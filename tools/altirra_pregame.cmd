# Altirra debugger commands: the two-player pre-game screens and the maze copies at the turn switches - OPEN-VERIFICATION.md OV-34, docs/19.
# Input only through the controller registers (CONSOL at the debounce reads, STRIG not pressed), as in altirra_sound_bot.cmd: title frame 200 SELECT (the real toggle $A544: one player -> two players), title frame 300 START.
# STICK0 gets the pseudo-random direction pattern of altirra_sound_bot.cmd (the value the game reads; nothing else is written), so Pac-Man wanders, eats different dots for each player and is caught: both players lose their lives and the turns switch.  No pokes.
# Logged: the screen RAM of the title ($1C00-$1DFF) at every frame of the title in state 3 (the logging stops at the first new game), the status-line labels ($2004-$2006 "1UP", $2021-$2023 "2UP") and the player variables at every frame,
# and the maze copies ($0C00-$0FFF, $1000-$13FF, $1400-$17FF, the stored original $0800-$0BFF) at every save and load of a turn switch.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\pregame.txt -Seconds 90 -Cmd altirra_pregame.cmd      then  python -I tools/analyze_pregame.py analysis/raw-logs/pregame.txt
r @t1 0
r @t3 0
r @t7 0
bp -n a82f "eb $278 ($0E*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=0))+($07*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=1))+($0D*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=2))+($0B*(((((@frame/$20)*5)+(((@frame/$20)*(@frame/$20))/7))%4)=3))"
bt a78b "TITLE f=%d z19=%d z1a=%d lv=%d" @frame db($19) db($1a) db($1b)
bp -n a78b "db 1c00 L200"
bp -n a537 "bc 2"
bp -n a537 "r @t7 @t7+1"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t3 ((@t7=0)&(@t1>=200)&(@t1<=208))*2+((@t7=0)&(@t1>=300)&(@t1<=350))*1"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a4fa "eb $284 1"
bp -n a4ff "eb $285 1"
bt a5fd "FR f=%d z19=%d z1a=%d cp=%d fa=%d lives=%d,%d z23=%d lev=%d,%d l1=%02X%02X%02X l2=%02X%02X%02X t1=%d t7=%d" @frame db($19) db($1a) db($2b) db($fa) db($2c) db($2d) db($23) db($30) db($31) db($2004) db($2005) db($2006) db($2021) db($2022) db($2023) @t1 @t7
bt a923 "DEATH_START f=%d cp=%d" @frame db($2b)
bt aaef "TURN_END f=%d cp=%d" @frame db($2b)
bt b13d "SAVE1_IN f=%d" @frame
bp -n b13d "db 0c00 L400"
bt b15a "SAVE1_OUT f=%d" @frame
bp -n b15a "db 1000 L400"
bt b15b "SAVE2_IN f=%d" @frame
bp -n b15b "db 0c00 L400"
bt b178 "SAVE2_OUT f=%d" @frame
bp -n b178 "db 1400 L400"
bt aa3f "LOAD1_IN f=%d" @frame
bp -n aa3f "db 1000 L400; db 800 L400"
bt aa5c "LOAD1_OUT f=%d" @frame
bp -n aa5c "db 0c00 L400"
bt aa69 "LOAD2_IN f=%d" @frame
bp -n aa69 "db 1400 L400; db 800 L400"
bt aa86 "LOAD2_OUT f=%d" @frame
bp -n aa86 "db 0c00 L400"
