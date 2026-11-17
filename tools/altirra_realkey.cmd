# OV-61: the keyboard path of the OS with a REAL key press.  The space bar is pressed twice from outside the emulated machine (tools/run_patrol_trace.ps1 -Keys: WM_KEYDOWN / WM_KEYUP posted to Altirra's window), so POKEY's keyboard scanner raises the keyboard IRQ and the OS IRQ routine puts the code into CH ($02FC); the game's key loop ($A4CC-$A4E6) then toggles Paused ($9B).  Nothing is written to CH or to any register by this harness.
# TEST AIDS (emulated RAM/PC only, as altirra_pause.cmd): the game is started from the first CONSOL poll ($A537); Pac-Man cannot die ($A923 skipped); a joystick bot pokes STICK0 so that the game keeps moving.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\realkey.txt -Seconds 45 -Cmd altirra_realkey.cmd -Keys 22:20,32:20      then  python -I tools/analyze_realkey.py analysis/raw-logs/realkey.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bta r d209 L1 "KBCODE_READ pc=$%04X f=%d" pc @frame
bta r d20f L1 "SKSTAT_READ pc=$%04X f=%d" pc @frame
bta w 2fc L1 "CHW pc=$%04X v=$%02X f=%d" pc @value @frame
bta w 9b L1 "PAUSEW pc=$%04X v=$%02X f=%d" pc @value @frame
bt a4e2 "KEY_TOGGLE f=%d new=%d old=%d" @frame @a db($9b)
bt a79c "PAUSED_FRAME f=%d" @frame
bt a5fd "PV f=%d paused=%d rtclok=%d ch=%02X" @frame db($9b) db($14) db($2fc)
