# Altirra debugger commands: the PAUSE key (the space bar, keyboard code $21) - the one key of the key loop that was never tested live (docs/21 'Keys', docs/25 `Paused`, OPEN-VERIFICATION C-60).
# The key loop ($A4CC-$A4E6, in Start) reads CH ($02FC); with $02F1 = 0 and CH = $21 it toggles `Paused` ($9B) and clears CH to $FF; while Paused the frame routine only silences POKEY and returns ($A79C).
# TEST AIDS (emulated RAM/PC only): the game is started by jumping from the first CONSOL poll to the start-game code ($A537); Pac-Man cannot die ($A923 skipped); a joystick bot pokes STICK0 ($0278) so that Pac-Man and the ghosts
# keep moving (direction changes every 48 frames); and the key press itself: CH := $21 is written once at frame 600 (pause) and once at frame 900 (resume), at the VBI, as if the space bar had been struck.  The game's own code does the rest.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\pause.txt -Seconds 40 -Cmd altirra_pause.cmd      then  python -I tools/analyze_pause.py analysis/raw-logs/pause.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
bp -n a5fd "r @t6 ((@frame=600)|(@frame=900)); eb $2fc $21*@t6+db($2fc)*(1-@t6)"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt a5fd "PV f=%d paused=%d rtclok=%d px=%d py=%d g=%d,%d,%d,%d,%d,%d,%d,%d ch=%d" @frame db($9b) db($14) db($8e) db($89) db($8a) db($8b) db($8c) db($8d) db($85) db($86) db($87) db($88) db($2fc)
bt a4e2 "KEY_TOGGLE f=%d new=%d old=%d" @frame @a db($9b)
bt a79c "PAUSED_FRAME f=%d" @frame
