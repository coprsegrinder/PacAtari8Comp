# Altirra debugger commands: the FORCED CHASE of the late board (ForceChase $B616, called by ChaseTimerSirenSight when 224 dots (or more) are eaten) - stage 58 (docs/34-state-transitions.md), the rule `$B626`.
# TEST AIDS (emulated RAM/PC only): the game is started by jumping from the first CONSOL poll to the start-game code ($A537); Pac-Man cannot die ($A923 skipped); a joystick bot pokes STICK0 ($0278) so that Pac-Man and the ghosts keep
# moving (direction changes every 48 frames); and the number of dots eaten (DotsEatenLo $34, player 1) is set to $DF once at frame 900, the way a long game would have reached it; the game decides everything else (the next dot makes it $E0).
# Expected: ghosts that patrol or go to their corner (states $08 / $10 / $20) change to chase ($02) at $B626 and ChaseTimer becomes $FF.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\forcechase.txt -Seconds 40 -Cmd altirra_forcechase.cmd
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
bp -n a5fd "r @t6 (@frame=900); eb $34 $DF*@t6+db($34)*(1-@t6)"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt b626 "FORCE_CHASE f=%d x=%d old=$%02X dots=%d" @frame x db($ce+x) db($34)
