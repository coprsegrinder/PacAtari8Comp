# The same as altirra_budget.cmd on the title screen (OV-64): the game is not started, the counting loop takes over at frame 700.
r @t1 0
bp -n a923 "r pc $a936"
bp -n a82f "r @t5 ((@frame/$30)%4); eb $278 ($0E*(@t5=0))+($07*(@t5=1))+($0D*(@t5=2))+($0B*(@t5=3))"
bp -n a5fd "r @t1 (@frame>=700)"
bp -n a5fd "r @t4 (@frame=399); eb $4000 $A9 $00 $85 $18 $AD $00 $41 $8D $02 $41 $AD $01 $41 $8D $03 $41 $A9 $00 $8D $00 $41 $8D $01 $41 $AD $00 $41 $18 $69 $01 $8D $00 $41 $AD $01 $41 $69 $00 $8D $01 $41 $4C $18 $40"
bp -n a5fd "r pc ($4000*@t1)+($a5fd*(1-@t1)); r s ($ff*@t1)+(@s*(1-@t1))"
bt a5fd "BUD f=%d t1=%d n=%d" @frame @t1 (db($4102)+256*db($4103))
bt a386 "SENT f=%d pc=$%04X" @frame pc
