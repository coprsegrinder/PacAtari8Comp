# Run:  powershell -File tools\run_patrol_trace.ps1 -Log analysis\raw-logs\warmstart.txt -Seconds 40 -Cmd altirra_warmstart.cmd -Keys 20:74
bp -n a386 ".echo ---RUN_STATE f=%d; db 0 L100; .echo ---RUN_P4; db 400 L40; .echo ---RUN_MAZETAIL; db b98 L68; .echo ---RUN_END"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt a386 "RUN f=%d vp=%d s=$%02X p=$%02X a=$%02X x=$%02X y=$%02X gs=%d" @frame vpos s p @a x y db($19)
bt a6b4 "INITRTS f=%d vp=%d ret=$%04X" @frame vpos dw($101+s)
bt a3a1 "ZPCLEAR f=%d gs=%d" @frame db($19)
bta w 19 L1 "GS_WRITE pc=$%04X v=$%02X f=%d" pc @value @frame
bta r bffa L6 "HDR_READ a=$%04X pc=$%04X f=%d" @address pc @frame
