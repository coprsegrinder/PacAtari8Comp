# Altirra debugger commands: two console switches pressed together on the title screen - OPEN-VERIFICATION.md OV-59 (stage 53 coverage).
# The key loop of Start decides on the value of CONSOL after the debounce: START alone ($06) starts the game, OPTION alone ($03) and SELECT alone ($05) change the level and the number of players; any other value goes
# to the `bne` at $A535 and back to the key loop.  No session pressed two switches at once, so $A535 never ran live.  Here SELECT + START together (CONSOL = $04) are held for 9 frames at title frame 200, then START alone at frame 300.
# INPUT ONLY (as altirra_pregame.cmd): the values the game READS at the console reads $A507 / $A514 / $A51C and the trigger shadows; nothing else is written; no poke, no PC move.
# Expected: TWO_KEYS (the instruction at $A535 runs once or a few times, z1a unchanged = one player), then NEW_GAME at frame ~300 with one player.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\two_keys.txt -Seconds 40 -Cmd altirra_two_keys.cmd
r @t1 0
r @t3 0
r @t7 0
bp -n a537 "r @t7 @t7+1"
bp -n a5fd "r @t1 (db($19)>=3)*(@t1+1)"
bp -n a5fd "r @t3 ((@t7=0)&(@t1>=200)&(@t1<=208))*3+((@t7=0)&(@t1>=300)&(@t1<=350))*1"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a4fa "eb $284 1"
bp -n a4ff "eb $285 1"
bt a386 "SENT"
bt a535 "TWO_KEYS f=%d t1=%d z19=%d z1a=%d z1b=%d" @frame @t1 db($19) db($1a) db($1b)
bt a544 "SELECT_PRESSED f=%d" @frame
bt a559 "OPTION_PRESSED f=%d" @frame
bt a537 "NEW_GAME f=%d z1a=%d z1b=%d" @frame db($1a) db($1b)
bt a5fd "TITLE f=%d t1=%d z19=%d" @frame @t1 db($19)
