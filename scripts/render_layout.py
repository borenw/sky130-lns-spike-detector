import re, sys, subprocess
LEF="/usr/local/packages/tsmc_18m/ip/digital/Back_End/lef/tcb018gbwp7t_270a/lef/tcb018gbwp7t_6lm.lef"
# cell sizes (um)
sizes={}
cur=None
for ln in open(LEF,errors='ignore'):
    m=re.match(r'\s*MACRO\s+(\S+)',ln)
    if m: cur=m.group(1)
    m=re.match(r'\s*SIZE\s+([\d.]+)\s+BY\s+([\d.]+)',ln)
    if m and cur: sizes[cur]=(float(m.group(1)),float(m.group(2)))

def parse_def(path):
    t=open(path,errors='ignore').read()
    u=float(re.search(r'UNITS DISTANCE MICRONS (\d+)',t).group(1))
    dx0,dy0,dx1,dy1=map(int,re.search(r'DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)',t).groups())
    die=((dx1-dx0)/u,(dy1-dy0)/u)
    comps=[]
    for m in re.finditer(r'-\s+\S+\s+(\S+)\s+\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)',t):
        cell,x,y,o=m.group(1),int(m.group(2))/u,int(m.group(3))/u,m.group(4)
        w,h=sizes.get(cell,(0.56,3.92))
        comps.append((cell,x,y,w,h))
    return die,comps

def render(path,title,out,px=900):
    die,comps=parse_def(path)
    W,H=die; pad=6
    sc=px/(W+2*pad); Wpx=int((W+2*pad)*sc); Hpx=int((H+2*pad)*sc)+40
    def X(x):return (x+pad)*sc
    def Y(y):return Hpx-40-(y+pad)*sc   # flip
    S=['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="system-ui,sans-serif">'%(Wpx,Hpx)]
    S.append('<rect width="%d" height="%d" fill="#0d0d10"/>'%(Wpx,Hpx))
    S.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#e8c15a" stroke-width="1.5"/>'%(X(0),Y(H),W*sc,H*sc))
    nlog=0
    for cell,x,y,w,h in comps:
        fill= "#3a3f4b" if cell.startswith("FILL") else ("#2f6f4f" if cell.startswith(("TAP","ENDCAP")) else "#3d7fd6")
        if not cell.startswith(("FILL","TAP","ENDCAP")): nlog+=1
        S.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s" stroke="#0d0d10" stroke-width="0.25"/>'%(X(x),Y(y+h),w*sc,h*sc,fill))
    S.append('<text x="10" y="%d" fill="#e6e6e6" font-size="15" font-weight="600">%s</text>'%(Hpx-14,title))
    S.append('<text x="%d" y="%d" text-anchor="end" fill="#9a9a9a" font-size="12">%.1f × %.1f µm  ·  %d std cells</text>'%(Wpx-10,Hpx-14,W,H,nlog))
    S.append('</svg>')
    open(out,'w').write(''.join(S))
    subprocess.run(["convert","-density","140",out,out.replace('.svg','.png')],check=False)
    return W,H,nlog

for path,title,out in [
  ("pnr_vthp/vth_prime.def","vth_prime  (log-domain Vth′ block)","pnr_vthp/vth_prime_layout.svg"),
  ("pnr_multcd/mult_cd.def","mult_cd  (10×10 C·D multiplier)","pnr_multcd/mult_cd_layout.svg")]:
    w,h,n=render(path,title,out); print("%s: %.1f x %.1f um, %d logic cells -> %s"%(title,w,h,n,out.replace('.svg','.png')))
