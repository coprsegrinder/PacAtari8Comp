# The same as altirra_stick.cmd in a TWO-PLAYER game where Pac-Man CAN die (so that the turn passes to player 2 and STICK1 is read): at every frame the stick value is a random number 0-15 (all sixteen values, the impossible ones too), the game starts at once as a two-player game (zp_1A := 1).
# TEST AIDS (emulated machine only): the game is started from the first CONSOL poll ($A504 -> $A537); STICK0 and STICK1 ($0278, $0279) are poked just before MovePacMan reads them ($B19F) with POKEY's RANDOM bits (the numbers are not the game's).
# The log: SI at $B183 (the state before the input path: the player on turn x, the wanted direction zp_AC, Pac-Man's direction, the open directions zp_2A, ATRACT, zp_A8), ST at $B1A1 (the stick value the game reads: STICK0,x), SO at $B1C4 (the state after it), MV at the entry of each of the six cases of the dispatch.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\stick.txt -Seconds 60 -Cmd altirra_stick.cmd      then  python -I tools/analyze_input.py analysis/raw-logs/stick*.txt
bp -n a504 "eb $1a 1; r pc $a537; bc 0"
bp -n b19f "eb $278 (db($d20a)&15); eb $279 (db($d20a)&15)"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt b183 "SI f=%d x=%d ac=%d pd=%d m=%d at=%d a8=%d" @frame db($2b) db($ac) db($93) db($2a) db($4d) db($a8)
bt b1a1 "ST f=%d v=%d" @frame db($278+db($2b))
bt b1c4 "SO f=%d ac=%d pd=%d at=%d a8=%d" @frame db($ac) db($93) db($4d) db($a8)
bt b1e3 "MV f=%d c=up" @frame
bt b211 "MV f=%d c=down" @frame
bt b23f "MV f=%d c=right" @frame
bt b271 "MV f=%d c=left" @frame
bt b2aa "MV f=%d c=blocked" @frame
bt b2ce "MV f=%d c=none" @frame
