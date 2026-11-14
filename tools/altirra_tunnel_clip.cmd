# Altirra debugger commands: the tunnel-edge clipping of the pictures (Sub_AB48 / Sub_AB57, $AB48-$ABC8, called by the VBI at $A60A) - OPEN-VERIFICATION.md OV-31, docs/16.
# Code facts: every frame the VBI calls Sub_AB48 (when zp_E5 = 0); for each entity x = 4..0 (4 = Pac-Man) whose EntityY ($85+x) is $74 (the tunnel row) Sub_AB57 builds a mask zp_FE from EntityX and ANDs the 16 picture rows at page $24+x (Pac-Man: $23), offset $74 with it;
# beyond the right edge (X >= $C0) the mask is $FF << (X-$C0), left of $39 it is $FF >> ($38-X); an entity at X >= $CA going right (dir 8) is moved to $2A, at X <= $2A going left (dir 4) to $CA (the tunnel wrap).
# TEST AIDS (emulated RAM/PC only): Pac-Man cannot die ($A923 skipped); from 200 frames after the start, in every VBI just before Sub_AB48 all five entities are put on the tunnel row (EntityY := $74), at EntityX = $20 + (k mod 190) ($20..$DD), direction left
# for the first 190 frames and right for the next 190 (then it repeats), and their 16 picture rows at the tunnel row are filled with $FF, so the picture after the call IS the mask.  The ROM is not touched.
# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\tunnel-clip.txt -Seconds 60 -Cmd altirra_tunnel_clip.cmd      then  python -I tools/analyze_tunnel_clip.py analysis/raw-logs/tunnel-clip.txt
bp -n a504 "r pc $a537; bc 0"
bp -n a923 "r pc $a936"
bp -n adaf "r @t1 0"
bp -n a60a "r @t1 (@t1+1)"
bp -n a60a "r @t2 $20+((@t1-200)%190); r @t3 4+4*((((@t1-200)/190)%2)); r @t4 (@t1>=200)"
bp -n a60a "eb $85 $74*@t4+db($85)*(1-@t4); eb $86 $74*@t4+db($86)*(1-@t4); eb $87 $74*@t4+db($87)*(1-@t4); eb $88 $74*@t4+db($88)*(1-@t4); eb $89 $74*@t4+db($89)*(1-@t4)"
bp -n a60a "eb $8a @t2*@t4+db($8a)*(1-@t4); eb $8b @t2*@t4+db($8b)*(1-@t4); eb $8c @t2*@t4+db($8c)*(1-@t4); eb $8d @t2*@t4+db($8d)*(1-@t4); eb $8e @t2*@t4+db($8e)*(1-@t4)"
bp -n a60a "eb $8f @t3*@t4+db($8f)*(1-@t4); eb $90 @t3*@t4+db($90)*(1-@t4); eb $91 @t3*@t4+db($91)*(1-@t4); eb $92 @t3*@t4+db($92)*(1-@t4); eb $93 @t3*@t4+db($93)*(1-@t4)"
bp -n a60a "f $2474 L10 $FF*@t4+0; f $2574 L10 $FF*@t4+0; f $2674 L10 $FF*@t4+0; f $2774 L10 $FF*@t4+0; f $2374 L10 $FF*@t4+0"
bt ab57 "ENTER x=%d X=%d Y=%d dir=%d k=%d f=%d" x db($8a+x) db($85+x) db($8f+x) @t1 @frame
bt abc8 "LEAVE x=%d X=%d dir=%d mask=$%02X ptr=$%02X%02X z80=$%02X b0=$%02X b7=$%02X b15=$%02X f=%d" x db($8a+x) db($8f+x) db($fe) db($48) db($47) db($80) db(dw($47)+0) db(dw($47)+7) db(dw($47)+15) @frame
