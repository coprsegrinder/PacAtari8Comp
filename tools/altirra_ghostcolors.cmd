# Altirra debugger commands: the colours of the ghosts (normal, frightened solid/flashing, eaten pop-up and eyes, restore) - docs/16, docs/15 'colours are written by code'.
# TEST AIDS (emulated RAM/PC only), same cycle as altirra_transitions.cmd: Pac-Man cannot die; every 2048 frames a power pellet is eaten (frame mod 2048 = 256) and later a ghost (mod 4 rotates) is eaten;
# the level-complete flag is set at frame mod 2048 = 2032 so that the game itself advances through levels 0,1,2,...; no dot pokes.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log F:\Ports\ghostcolors.txt -Seconds 120 -Cmd altirra_ghostcolors.cmd   then  python -I tools/analyze_ghostcolors_log.py F:/Ports/ghostcolors.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 (@frame%$800); eb $89 db($BB83+((@frame/$80)%10)); eb $8e db($BB8D+((@frame/$500)%10)); r @t7 ((@t5>=$F0)&(@t5<$F8)); eb $32 (@t7*$0F)+(1-@t7)*db($32); r @t7 ((@t5>=$100)&(@t5<$110)); eb $8e db($8e)+@t7*($3A-db($8e)); eb $89 db($89)+@t7*($3C-db($89)); r @t6 ((@frame/$800)%4); r @t7 ((@t5>=$180)&(@t5<$190)); eb $8e db($8e)+@t7*(db($8a+@t6)-db($8e)); eb $89 db($89)+@t7*(db($85+@t6)-db($89))"
bp -n a82f "r @t7 ((@frame%$800)=$7F0); eb $26 @t7|db($26)"
bt a82f "COLS st=$%02X,$%02X,$%02X,$%02X c=$%02X,$%02X,$%02X,$%02X FC=%d FD=%d lv=%d f=%d pc=$%02X" db($ce) db($cf) db($d0) db($d1) db($2c0) db($2c1) db($2c2) db($2c3) db($fc) db($fd) db($30) @frame db($2c7)
bt afd0 "FRIGHT_COLOR ghost=%d y=$%02X FC=%d FD=%d st=$%02X f=%d" x y db($fc) db($fd) db($ce+x) @frame
bt af84 "END_RESTORE ghost=%d val=$%02X f=%d" x db($bbe2+x) @frame
bt a8ab "POPUP ghost=%d f=%d" x @frame
bt b0aa "EYES ghost=%d f=%d" x @frame
bt b769 "HOME_RESTORE ghost=%d val=$%02X st=$%02X f=%d" x db($bbe2+x) db($ce+x) @frame
bt b118 "LOAD_SHADOW f=%d" @frame
bt a886 "GHOST_EATEN ghost=%d f=%d" x @frame
bt b3de "PELLET f=%d" @frame
bt ac7e "LEVEL_ADVANCE level=%d f=%d" db($30) @frame
bt adaf "LEVEL_SETUP level=%d f=%d" db($30) @frame
