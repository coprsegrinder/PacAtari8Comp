# Altirra debugger commands: the joystick with a REAL press (stage 63, limit of tools/altirra_stick.cmd): nothing is written to STICK0.  The arrow keys are pressed from outside the machine (tools/run_patrol_trace.ps1 -Keys: WM_KEYDOWN / WM_KEYUP posted to Altirra's window, which maps the cursor keys to joystick 1), so that the OS reads the PIA port in its vertical blank and fills the shadow `STICK0` that the game reads at $B1A1.
# TEST AIDS: the game is started from the first CONSOL poll ($A504 -> $A537); Pac-Man cannot die ($A923 skipped).  Logs: ST (the value read at $B1A1), SI / SO as in altirra_stick.cmd, the PIA port ($D300) at the read.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\realstick.txt -Seconds 50 -Cmd altirra_realstick.cmd -Keys 12:25,14:26,16:27,18:28      then  python -I tools/analyze_input.py analysis/raw-logs/realstick.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt b183 "SI f=%d x=%d ac=%d pd=%d m=%d at=%d a8=%d" @frame db($2b) db($ac) db($93) db($2a) db($4d) db($a8)
bt b1a1 "ST f=%d v=%d pia=%d" @frame db($278+db($2b)) db($d300)
bt b1c4 "SO f=%d ac=%d pd=%d at=%d a8=%d" @frame db($ac) db($93) db($4d) db($a8)
bt b1e3 "MV f=%d c=up" @frame
bt b211 "MV f=%d c=down" @frame
bt b23f "MV f=%d c=right" @frame
bt b271 "MV f=%d c=left" @frame
bt b2aa "MV f=%d c=blocked" @frame
bt b2ce "MV f=%d c=none" @frame
