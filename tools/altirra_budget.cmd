# Altirra debugger commands: how many CPU cycles the vertical-blank handler's thread really gets in a frame on the game screen (OV-64: the display model of tools/dma_model.py against the machine).
# TEST AIDS (emulated RAM/PC only): the game is started as in altirra_pause.cmd and runs with its bot for 400 frames; from frame 400 on, at every entry of the deferred handler ($A5FD) the program counter is sent to a counting loop in RAM at $4000
# (25 cycles an iteration: lda/clc/adc/sta/lda/adc/sta/jmp on a 16-bit counter at $4100) and the stack pointer is reset, so the loop runs from the entry until the next vertical-blank interrupt takes it over; at the next entry the loop saves its count to $4102/$4103 and clears it.
# The loop also clears the display-list interrupts' band counter ($18), as the handler does, so the interrupts behave as in the game.  The count x 25 is the number of CPU cycles the handler's thread has between its entry and the next interrupt: the display, the interrupts and the OS's own work are all in it.
# Run through tools/run_patrol_trace.ps1 -Cmd altirra_budget.cmd -Seconds 60 -Log analysis/raw-logs/budget.txt, then tools/analyze_budget.py.
r @t1 0
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
bp -n a5fd "r @t1 (@frame>=400)"
bp -n a5fd "r @t4 (@frame=399); eb $4000 $A9 $00 $85 $18 $AD $00 $41 $8D $02 $41 $AD $01 $41 $8D $03 $41 $A9 $00 $8D $00 $41 $8D $01 $41 $AD $00 $41 $18 $69 $01 $8D $00 $41 $AD $01 $41 $69 $00 $8D $01 $41 $4C $18 $40"
bp -n a5fd "r pc ($4000*@t1)+($a5fd*(1-@t1)); r s ($ff*@t1)+(@s*(1-@t1))"
bt a5fd "BUD f=%d t1=%d n=%d" @frame @t1 (db($4102)+256*db($4103))
bt a386 "SENT f=%d pc=$%04X" @frame pc
