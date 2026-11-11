# Altirra debugger commands: freeze the game when one particular Pac-Man picture / death-sequence frame is on screen (Pac-Man frames and death sequence, screenshot check).
# Used by tools\run_pacman_shots.ps1, which replaces @COND@ and @MODE@ and appends these lines to the common aids. Same freeze technique as altirra_ghostshots.cmd: a real debugger break at $0443 (a JMP in free RAM), the ROM is not touched.
# MODE shape: Pac-Man cannot die ($A923 skipped) and a joystick bot moves him; the frame the wanted shape was drawn, zp_AA bit 7 is set (the game's own 'Pac-Man frozen' flag: MovePacMan returns at once), so the picture stays; 3 frames later the machine is frozen.
# MODE ready / readylatch: as death, but the condition is evaluated at the per-frame routine $A78C (after the death); readylatch waits 8 frames after the condition first holds (the screen shows the frame before the freeze).
# MODE death: the game really kills Pac-Man (bot, lives refilled); the machine is frozen the first frame the condition holds (the death animation holds each picture for 8 frames).
r @t1 0
r @t2 0
r @t3 0
r @t6 0
@MODELINES@
bt 443 "SHOT mode=@MODE@ f=%d" @frame
bp 443 "db $85 L5; db $8a L5; db $8f L4; db $ce L4; db $2c0 L8; db $8e L1; db $89 L1; db $93 L1; db $aa L1; db $ab L1; db $ed L2; db $ea L4; db $24 L1; db $f0 L2; db $f1 L1; db $14 L1; db $af L1; db $de0 L30; db $3000 L330; db $2300 L100; db $2400 L400; .logclose"
