# Stage 61: the cold start from power-on to the title, in the real machine, NO test aids (nothing is written to the emulated machine; the game is not started: it stays at the title).
# bp 0 (the first line, so `bc 0` is its number): the first pass of the key loop ($A4BA) dumps the state once: the chips (.antic .gtia .pokey), zero page, OS page 2, the tables at $0600-$07FF, then clears itself.
# Milestones are tracepoints on instructions that run once; every line carries the frame, the scan line (vp) and the colour clock (hp).  The sentinel line absorbs Altirra's late first tracepoint (docs/32 rule 1).
bp -n a4ba ".echo ---KEYLOOP_FIRST; .echo ---ANTIC; .antic; .echo ---GTIA; .gtia; .echo ---POKEY; .pokey; .echo ---ZP; db 0 L100; .echo ---P2; db 200 L100; .echo ---TABLES; db 600 L200; .echo ---END; bc 0"
bp -n a386 ".echo ---RUN_STATE; .echo ---RUN_ZP; db 0 L100; .echo ---RUN_P4; db 400 L40; .echo ---RUN_MAZETAIL; db b98 L68; .echo ---RUN_END; bc 1"
bt a386 "SENT f=%d pc=$%04X" @frame pc
bt a386 "MS_RUN f=%d vp=%d hp=%d s=$%02X p=$%02X a=$%02X x=$%02X y=$%02X ret=$%04X" @frame vpos hpos s p @a x y dw($101+s)
bt a6b4 "MS_INIT f=%d vp=%d hp=%d ret=$%04X" @frame vpos hpos dw($101+s)
bt a391 "MS_HSTEXT f=%d vp=%d hp=%d" @frame vpos hpos
bt a3a1 "MS_ZPCLEAR f=%d vp=%d hp=%d" @frame vpos hpos
bt a3f6 "MS_MAZE f=%d vp=%d hp=%d" @frame vpos hpos
bt a41b "MS_NIBBLES f=%d vp=%d hp=%d" @frame vpos hpos
bt a42e "MS_CHARSET f=%d vp=%d hp=%d" @frame vpos hpos
bt a441 "MS_TITLECHARSET f=%d vp=%d hp=%d" @frame vpos hpos
bt a44c "MS_TAIL f=%d vp=%d hp=%d" @frame vpos hpos
bt a456 "MS_IRQ f=%d vp=%d hp=%d" @frame vpos hpos
bt a460 "MS_SETVBV f=%d vp=%d hp=%d a=$%02X x=$%02X y=$%02X" @frame vpos hpos @a x y
bt a463 "MS_SETVBV_DONE f=%d vp=%d hp=%d vvblkd=$%04X" @frame vpos hpos dw($224)
bt a477 "MS_RESTART f=%d vp=%d hp=%d" @frame vpos hpos
bt a484 "MS_COPY1 f=%d vp=%d hp=%d" @frame vpos hpos
bt a48d "MS_COPIES_DONE f=%d vp=%d hp=%d gs=%d" @frame vpos hpos db($19)
bt a5fd "VBI f=%d vp=%d gs=%d rtclok=%d" @frame vpos db($19) db($14)
bta w 19 L1 "GS_WRITE pc=$%04X v=$%02X f=%d vp=%d" pc @value @frame vpos
bta w 200 L2 "VDSLST_WRITE pc=$%04X a=$%04X v=$%02X f=%d vp=%d" pc @address @value @frame vpos
bta r bffa L6 "HDR_READ a=$%04X pc=$%04X f=%d" @address pc @frame
bta r a000 L2 "ROM_FIRST pc=$%04X a=$%04X f=%d" pc @address @frame
