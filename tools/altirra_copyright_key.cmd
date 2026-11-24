# Altirra debugger commands: a console key at the COPYRIGHT screen (GameState 1 / 2) - stage 58 (docs/34-state-transitions.md), the rule `$A552` for states 1 and 2 (`LA550`: a console key other than START leaves the copyright
# screen for the title menu).  SELECT ($05) is held for 11 frames from frame 100 after the cold start, at the controller reads $A507 / $A514 / $A51C (the values the game gets, as in altirra_pregame.cmd); the copyright screen
# lasts about four seconds (240 frames), so the key comes while GameState = 2.  Nothing else is changed (no poke, no PC move).
# Expected: GameState 2 -> 3 by $A552 at about frame 112, instead of by $A70A at the end of the copyright time.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\copyright_key.txt -Seconds 20 -Cmd altirra_copyright_key.cmd
r @t3 0
bp -n a5fd "r @t3 ((@frame>=100)&(@frame<=110))*2"
bp -n a507 "r a 7-@t3"
bp -n a514 "r a 7-@t3"
bp -n a51c "r a 6+(@t3>0)"
bp -n a4fa "eb $284 1"
bp -n a4ff "eb $285 1"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt a552 "STATE_FROM_KEY f=%d z19_new=%d" @frame @a
bt a70a "STATE_FROM_TIME f=%d" @frame
bt a5fd "V f=%d z19=%d" @frame db($19)
