# Altirra debugger commands: ADVERSARIAL play frames (OV-64): at the entry of the handler in every play frame the ghost and Pac-Man state is overwritten with random values chosen to make the frame as heavy as the code allows,
# and the cost of the frame is read from the tracepoints of tools/run_mainloop_audit.ps1 (-Only fuzz -Cycles).  The random numbers are POKEY's RANDOM ($D20A).
# What is randomised (only in a frame that would be a play frame: GameState 0, play started, WaitState 0, no death, no eaten-ghost pause, no level end):
#   GhostState of each ghost: one of the 16 documented states (the table at $4200); GhostTimer: 0 in 3 of 4 frames (the timer-expired paths: patrol -> corner -> patrol); the position of each ghost and of Pac-Man: a junction of the maze
#   (a Y of JunctionYList and an X of JunctionXList), so that JunctionLookup finds a junction; the direction of each: one of the four; MoveDelayCount of each ghost: 0 (the ghost moves this frame).
# TEST AIDS besides: Pac-Man cannot die ($A923 skipped); the game is started from the first CONSOL poll; a joystick bot pokes STICK0.  The states written are not all reachable in a game: the result is an UPPER bound of what play can cost, not a sample of it.
# Run: powershell -File tools\run_mainloop_audit.ps1 -Only fuzz -Cycles -Seconds 300     then  python -I tools/analyze_fuzz.py analysis/raw-logs/fuzzmainloop-fuzz.txt
r @t1 0
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
eb $4200 $00 $01 $02 $04 $08 $10 $20 $42 $44 $80 $81 $82 $84 $88 $90 $A0
eb $4210 $01 $02 $04 $08
bp -n a5fd "r @t1 (@frame>=600)*(db($19)=0)*(db($21)=1)*(db($24)=0)*(db($ed)=0)*(db($e5)=0)*(db($26)=0)*(db($9b)=0)*(db($20)=0)"
bp -n a5fd "eb $ce (db($4200+(db($d20a)&15))*@t1)+(db($ce)*(1-@t1)); eb $cf (db($4200+(db($d20a)&15))*@t1)+(db($cf)*(1-@t1)); eb $d0 (db($4200+(db($d20a)&15))*@t1)+(db($d0)*(1-@t1)); eb $d1 (db($4200+(db($d20a)&15))*@t1)+(db($d1)*(1-@t1))"
bp -n a5fd "eb $ca (((db($d20a)&3)=0)*(db($d20a)&$7f))*@t1+db($ca)*(1-@t1); eb $cb (((db($d20a)&3)=0)*(db($d20a)&$7f))*@t1+db($cb)*(1-@t1); eb $cc (((db($d20a)&3)=0)*(db($d20a)&$7f))*@t1+db($cc)*(1-@t1); eb $cd (((db($d20a)&3)=0)*(db($d20a)&$7f))*@t1+db($cd)*(1-@t1)"
bp -n a5fd "eb $8a (db($bb8d+((db($d20a)/2)%10))*@t1)+(db($8a)*(1-@t1)); eb $85 (db($bb83+((db($d20a)/2)%10))*@t1)+(db($85)*(1-@t1)); eb $8b (db($bb8d+((db($d20a)/2)%10))*@t1)+(db($8b)*(1-@t1)); eb $86 (db($bb83+((db($d20a)/2)%10))*@t1)+(db($86)*(1-@t1))"
bp -n a5fd "eb $8c (db($bb8d+((db($d20a)/2)%10))*@t1)+(db($8c)*(1-@t1)); eb $87 (db($bb83+((db($d20a)/2)%10))*@t1)+(db($87)*(1-@t1)); eb $8d (db($bb8d+((db($d20a)/2)%10))*@t1)+(db($8d)*(1-@t1)); eb $88 (db($bb83+((db($d20a)/2)%10))*@t1)+(db($88)*(1-@t1))"
bp -n a5fd "eb $8e (db($bb8d+((db($d20a)/2)%10))*@t1)+(db($8e)*(1-@t1)); eb $89 (db($bb83+((db($d20a)/2)%10))*@t1)+(db($89)*(1-@t1))"
bp -n a5fd "eb $8f (db($4210+(db($d20a)&3))*@t1)+(db($8f)*(1-@t1)); eb $90 (db($4210+(db($d20a)&3))*@t1)+(db($90)*(1-@t1)); eb $91 (db($4210+(db($d20a)&3))*@t1)+(db($91)*(1-@t1)); eb $92 (db($4210+(db($d20a)&3))*@t1)+(db($92)*(1-@t1)); eb $93 (db($4210+(db($d20a)&3))*@t1)+(db($93)*(1-@t1))"
bp -n a5fd "eb $b5 (db($b5)*(1-@t1)); eb $b6 (db($b6)*(1-@t1)); eb $b7 (db($b7)*(1-@t1)); eb $b8 (db($b8)*(1-@t1))"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt a4e2 "KEY_TOGGLE f=%d new=%d" @frame @a
