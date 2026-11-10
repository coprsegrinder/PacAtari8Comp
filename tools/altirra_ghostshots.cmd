# Altirra debugger commands: freeze the game when one particular ghost picture is on screen (step C11, ghost frames, screenshot check).
# Used by tools\run_ghost_shots.ps1, which replaces @COND@ (e.g. (dw($3c)==$BAC0)&(db($41c)==$54)) and appends these lines to altirra_ghostframes.cmd (without its tracepoints).
# The freeze waits until two whole frames have passed with no ghost drawn (draw counter @t8 equal to its value one frame earlier, @t9; @t0 counts the quiet frames), so the screen shows exactly the logged RAM (with one quiet frame the screen can still show the previous picture).
# TEST AIDS (emulated machine only): the freeze is a real debugger break: at the next
# frame start after the draw, PC is changed to a small JMP in free RAM ($0440: JMP $0443) whose target $0443 has a plain breakpoint (the debugger does not check breakpoints on the first instruction after a PC change); the game's ROM is not touched. The emulator then stays stopped, so the screen is a complete frame that matches the logged RAM. At the freeze the ghosts' x ($85-$88), y ($8a-$8d), directions ($8f-$92), states ($ce-$d1), colour registers ($2c0-$2c3) and the four players' memory ($2400-$27FF) are written to the log (the GTIA's own HPOS registers cannot be used: the display-list interrupts reuse the players for the bottom icons).
r @t1 0; r @t0 0; r @t8 0; r @t9 0
bp -n b96a "r @t1 @COND@; r @t2 (x); r @t3 dw($3c); r @t4 db($41c); r @t8 (@t8+1)"
bp -n a82f "r @t6 ((@t8=@t9)*(@t0>=2)); r @t0 ((1-(@t8=@t9))*@t1+(@t8=@t9)*(@t0>=1)*(@t0+1)); r @t9 (@t8); eb 440 $4c; eb 441 $43; eb 442 $04; eb 443 $4c; eb 444 $43; eb 445 $04; r pc ($a82f*(1-@t6))+($440*@t6)"
bt 443 "SHOT ghost=%d src=$%04X feet=$%02X pcolr=$%02X af=%d frame=%d" @t2 @t3 @t4 db($2c0+@t2) db($af) @frame
bp 443 "db $85 L5; db $8a L5; db $8f L4; db $ce L4; db $2c0 L4; db $2400 L400; .logclose"
