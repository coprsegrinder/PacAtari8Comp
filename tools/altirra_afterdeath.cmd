# Altirra debugger commands: what happens AFTER the death - the turn/board restart and the 'get ready' display, frame by frame (docs/20, 'After the death').
# TEST AIDS (emulated machine only): as altirra_death.cmd - the game really kills Pac-Man; a joystick bot pokes STICK0; at every death start both life counters are refilled to 3 so that the game goes on.
# One line per frame of the per-frame routine ($A78C): all main-loop state variables, ghost/Pac-Man state and positions, the 14 screen bytes of the READY text row ($0DED), the colour registers.
# Run: powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\afterdeath.txt -Seconds 120 -Cmd altirra_afterdeath.cmd   then   python -I tools/analyze_afterdeath_log.py analysis/raw-logs/afterdeath.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "eb $2c 3; eb $2d 3"
bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
bt a78c "FR f=%d z20=%d z21=%d z22=%d z23=%d z24=%d z25=%d z26=%d z1c=%d z1e=%d a3=%d ds=%d ae=%d lives=%d,%d gs=$%02X,$%02X,$%02X,$%02X gx=%d,%d,%d,%d gy=%d,%d,%d,%d px=%d py=%d pd=%d txt=%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X c=$%02X,$%02X,$%02X,$%02X,$%02X,$%02X,$%02X,$%02X dots=%d,%d fl=$%02X bon=%d fc=%d fd=%d ch=%d aa=$%02X cp=%d leg=%d pel=%d,%d,%d,%d" @frame db($20) db($21) db($22) db($23) db($24) db($25) db($26) db($1c) db($1e) db($a3) db($ed) db($ae) db($2c) db($2d) db($ce) db($cf) db($d0) db($d1) db($8a) db($8b) db($8c) db($8d) db($85) db($86) db($87) db($88) db($8e) db($89) db($93) db($DED) db($DEE) db($DEF) db($DF0) db($DF1) db($DF2) db($DF3) db($DF4) db($DF5) db($DF6) db($DF7) db($DF8) db($DF9) db($DFA) db($2c0) db($2c1) db($2c2) db($2c3) db($2c4) db($2c5) db($2c6) db($2c7) db($34) db($36) db($32) db($43) db($fc) db($fd) db($ad) db($aa) db($ab) db($af) db($c7b) db($c9c) db($e83) db($ea4)
bt a923 "DEATH_START f=%d" @frame
bt aef1 "DEATH_DONE f=%d" @frame
bt aae6 "INITBOARD_CALL f=%d lives=%d" @frame db($2c)
bt aaef "GAME_OVER_TEXT f=%d" @frame
bt ad0e "SUB_AD0E f=%d" @frame
bt ad49 "SUB_AD49 f=%d" @frame
bt ad13 "TURN_START lives=%d f=%d" db($2c) @frame
bt ad5e "CLEAR_READY f=%d" @frame
bt adaf "INITBOARD f=%d" @frame
bt a800 "START_PLAY f=%d" @frame
bt a810 "AA2D_RETURN z23=%d z20=%d f=%d" db($23) db($20) @frame
bt a818 "Z24_INC f=%d" @frame
bt ac93 "LEVEL_INDICATOR f=%d" @frame
bt a7fb "TUNE_END_DRAW f=%d" @frame
bta w d200 L8 "SNDW pc=$%04X f=%d" pc @frame
bta w 0ded L14 "TEXTW pc=$%04X f=%d" pc @frame
bt b902 "SAD_IN g=%d ae=%d dir=%d x=%d y=%d st=$%02X f=%d" x db($ae) db($8f+x) db($8a+x) db($85+x) db($ce+x) @frame
bt b93f "SAD_OUT g=%d x=%d y=%d f=%d" x db($8a+x) db($85+x) @frame

