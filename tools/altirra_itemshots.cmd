# Altirra debugger commands for tools\run_item_shots.ps1 (OPEN-VERIFICATION.md OV-32): freeze the machine at a chosen state and log everything needed to render the playfield and the pop-up: screen RAM $0C00-$0FFF,
# the status line $2000-$20FF, the game charset $3000-$33FF, the player/missile memory $2300-$27FF, the colour shadows, DliColors, ItemColor, level, lives, and the last writes of the colour registers with their scanline.
# TEST AIDS (emulated RAM/PC only, set per target in run_item_shots.ps1): level counter, dot counter, pellet, positions; the debugger break at the end is the freeze.
r @t1 0
r @t2 0
r @t3 0
r @t4 0
r @t6 0
r @t0 0
bta w d016 L5 "CW r=%04X v=%02X vp=%d hp=%d" @address @value vpos hpos
bta w d409 L1 "CB v=%02X vp=%d hp=%d" @value vpos hpos
bt b97e "HP g=%d x=%d y=%d f=%d" x db($8a+x) db($85+x) @frame
@MODELINES@
bt 443 "SHOT mode=@MODE@ f=%d" @frame
bp 443 "db $0c00 L400; db $2000 L100; db $3000 L400; db $1800 L200; db $1c00 L200; db $e000 L400; db $2300 L500; db $2c0 L10; db $5e L4; db $a0 L1; db $30 L2; db $2c L2; db $e9 L1; db $85 L5; db $8a L5; db $8e L1; db $89 L1; db $ce L4; db $9f L1; db $24 L1; .logclose"
