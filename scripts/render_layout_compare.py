import re, subprocess
LEF="/usr/local/packages/tsmc_18m/ip/digital/Back_End/lef/tcb018gbwp7t_270a/lef/tcb018gbwp7t_6lm.lef"
sizes={}; cur=None
for ln in open(LEF,errors='ignore'):
    m=re.match(r'\s*MACRO\s+(\S+)',ln); cur=m.group(1) if m else cur
    m=re.match(r'\s*SIZE\s+([\d.]+)\s+BY\s+([\d.]+)',ln)
    if m and cur: sizes[cur]=(float(m.group(1)),float(m.group(2)))
def parse(path):
    t=open(path,errors='ignore').read(); u=float(re.search(r'MICRONS (\d+)',t).group(1))
    d=list(map(int,re.search(r'DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)',t).groups()))
    die=((d[2]-d[0])/u,(d[3]-d[1])/u); c=[]
    for m in re.finditer(r'-\s+\S+\s+(\S+)\s+\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)',t):
        cell=m.group(1); c.append((cell,int(m.group(2))/u,int(m.group(3))/u,*sizes.get(cell,(0.56,3.92))))
    return die,c
S=7.0  # px per micron (common scale)
A=parse("pnr_vthp/vth_prime.def"); B=parse("pnr_multcd/mult_cd.def")
gap=40; pad=10; lab=46
maxH=max(A[0][1],B[0][1])
Wpx=int((A[0][0]+B[0][0])*S+3*pad+gap); Hpx=int(maxH*S+2*pad+lab)
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="system-ui,sans-serif">'%(Wpx,Hpx)]
svg.append('<rect width="%d" height="%d" fill="#0d0d10"/>'%(Wpx,Hpx))
def draw(die,comps,ox,title):
    W,H=die
    base=Hpx-lab-pad
    def X(x):return ox+x*S
    def Y(y):return base-y*S
    svg.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="#e8c15a" stroke-width="1.5"/>'%(X(0),Y(H),W*S,H*S))
    for cell,x,y,w,h in comps:
        f="#3a3f4b" if cell.startswith("FILL") else ("#2f6f4f" if cell.startswith(("TAP","ENDCAP")) else "#3d7fd6")
        svg.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>'%(X(x),Y(y+h),w*S,h*S,f))
    svg.append('<text x="%.1f" y="%d" fill="#e6e6e6" font-size="15" font-weight="600">%s</text>'%(ox,Hpx-16,title))
    svg.append('<text x="%.1f" y="%d" fill="#9a9a9a" font-size="12">%.0f×%.0f µm</text>'%(ox,Hpx-2,W,H))
draw(A[0],A[1],pad,"vth_prime  (log)")
draw(B[0],B[1],pad+A[0][0]*S+gap,"mult_cd  (multiplier)")
svg.append('</svg>')
open("pnr_multcd/layout_compare.svg","w").write(''.join(svg))
subprocess.run(["convert","-density","150","pnr_multcd/layout_compare.svg","pnr_multcd/layout_compare.png"],check=False)
print("compare: vth_prime %.0fx%.0f vs mult_cd %.0fx%.0f um (same scale)"%(A[0][0],A[0][1],B[0][0],B[0][1]))
