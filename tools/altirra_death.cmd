# Altirra debugger commands: Pac-Man's own pictures and the death sequence (Pac-Man frames, the ghosts during the death) - docs/12 'DeathPlotBytes', docs/20.
# TEST AIDS (emulated machine only; the death routine is NOT skipped here - the game really kills Pac-Man): a joystick 'bot' pokes STICK0 ($0278) every frame, changing direction every 48 frames (up, right, down, left, ...),
# so that Pac-Man moves, stops at walls and eats dots by himself and is caught by the ghosts; at every death start both life counters are refilled to 3 so that the game never ends.
# Run: powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\death.txt -Seconds 150 -Cmd altirra_death.cmd   then   python -I tools/analyze_death_log.py analysis/raw-logs/death.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "eb $2c 3; eb $2d 3"
bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
bt a82f "DF f=%d ds=%d ee=%d da=%d daf=%d dad=%d z24=%d f0=%d ef=%d f1=%d lives=%d,%d px=%d py=%d" @frame db($ed) db($ee) db($ea) db($eb) db($ec) db($24) db($f0) db($ef) db($f1) db($2c) db($2d) db($8e) db($89)
bt a923 "DEATH_START ghost=%d gst=$%02X,$%02X,$%02X,$%02X gx=%d,%d,%d,%d gy=%d,%d,%d,%d px=%d py=%d pdir=%d chomp=%d f=%d" x db($ce) db($cf) db($d0) db($d1) db($8a) db($8b) db($8c) db($8d) db($85) db($86) db($87) db($88) db($8e) db($89) db($93) db($ab) @frame
bt b2ea "PACSEL y=%d off=%d dir=%d chomp=%d pause=%d f=%d" y x db($93) db($ab) db($a7) @frame
bt b339 "PACDRAW px=%d py=%d shape=%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X rows=%02X%02X%02X%02X%02X%02X%02X%02X%02X%02X f=%d" db($8e) db($89) db($403) db($404) db($405) db($406) db($407) db($408) db($409) db($40a) db($40b) db($40c) db($2300+db($89)+3) db($2300+db($89)+4) db($2300+db($89)+5) db($2300+db($89)+6) db($2300+db($89)+7) db($2300+db($89)+8) db($2300+db($89)+9) db($2300+db($89)+10) db($2300+db($89)+11) db($2300+db($89)+12) @frame
bt ae47 "FREEZE_LEG af=%d ee=%d f=%d" db($af) db($ee) @frame
bt ae4e "FREEZE_GHOST g=%d dir=%d st=$%02X x=%d y=%d f=%d" x db($8f+x) db($ce+x) db($8a+x) db($85+x) @frame
bt ae63 "GHOST_HPOS_ZERO g=%d f=%d" x @frame
bt ae76 "ANIM_ON f=%d" @frame
bt af2c "ANIM_FRAME0 f=%d" @frame
bt af29 "ANIM_PLOT idx=%d row=%d byte=$%02X f=%d" x y db($bb57+x) @frame
bt af3a "ANIM_STAR f=%d" @frame
bt af48 "ANIM_END f=%d" @frame
bt aef1 "DEATH_DONE z24 f=%d" @frame
bt b96a "GDRAW g=%d src=$%04X feet=$%02X st=$%02X f=%d" x dw($3c) db($41c) db($ce+x) @frame
bt adaf "LEVEL_SETUP level=%d f=%d" db($30) @frame
bt ad13 "TURN_START lives=%d,%d f=%d" db($2c) db($2d) @frame
bt ae99 "AUDF1 st=3 val=%d f=%d" db($f0) @frame
bt aeb2 "AUDF1 st=4 val=%d f=%d" db($f0) @frame
bt aed7 "AUDF1 st=5 val=%d f=%d" db($ef) @frame
bt ae94 "AUDC1 val=168 f=%d" @frame
