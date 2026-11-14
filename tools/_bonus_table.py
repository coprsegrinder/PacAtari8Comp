import re, bisect, sys
fr={};ev=[]
for l in open(sys.argv[1],errors='replace'):
    if l.startswith('FR ') and ' t1=' in l:
        d=dict(re.findall(r'(\w+)=(\S+)',l)); fr[int(d['f'])]=d
    else:
        m=re.match(r'(NEWGAME|BONUS_APPEAR|BONUS_EATEN) f=(\d+)',l)
        if m: ev.append((int(m.group(2)),m.group(1)))
fs=sorted(fr)
for f,n in ev:
    d=fr[fs[bisect.bisect_right(fs,f)-1]]
    if n!='NEWGAME': print(n,f,'game',d['p'],'level',d['lv'],'dots',int(d['d34'])+256*int(d['d36']),'players' , d['lives'])
print('games',sum(1 for e in ev if e[1]=='NEWGAME'),'last frame',fs[-1])
