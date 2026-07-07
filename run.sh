#!/usr/bin/env bash
# End-to-end flow for the two-design comparison.  Stops on any failing check.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
LIB=synth/sky130_fd_sc_hd__tt_025C_1v80.lib

echo "== Phase 1: tools =="
iverilog -V | head -1; python3 --version; yosys --version | grep -i yosys | head -1
[ "$(stat -c%s $LIB)" -gt 10000000 ] || { echo "liberty too small"; exit 1; }

echo "== Phase 2: golden model + F-ROM =="
python3 model/model.py

echo "== Phase 3: elaboration (latch/mul audit) =="
yosys -s synth/run_mult.ys > /dev/null   # (also produces netlist; audit in report/elaboration.txt)

echo "== Phase 4: verification =="
iverilog -g2012 -o verif/tb.vvp verif/tb.v \
    rtl/mult_detector.v rtl/log_detector.v rtl/lod5.v rtl/lns_add.v rtl/lns_ftable.v
vvp verif/tb.vvp | tee verif/sim_report.txt
grep -q "RESULT: PASS" verif/sim_report.txt || { echo "VERIFY FAILED"; exit 1; }

echo "== Phase 4b: RTL Vth sweep (A,B,C,D=25,30,12,40) =="
python3 - <<'PY'
vs=[]; v=60
while v<1000: vs.append(v); v+=20
while v<=1300: vs.append(v); v+=1
v=1340
while v<=6000: vs.append(v); v+=40
open('verif/sweep_vth.txt','w').write('\n'.join(map(str,vs))+'\n')
PY
iverilog -g2012 -o verif/tb_sweep.vvp verif/tb_sweep.v \
    rtl/mult_detector.v rtl/log_detector.v rtl/lod5.v rtl/lns_add.v rtl/lns_ftable.v
vvp verif/tb_sweep.vvp

echo "== Phase 4c: RTL subtraction sweep (A*B-C*D > Vth, several sets) =="
python3 - <<'PY'
import csv, sys; sys.path.insert(0,'model'); import model as m
sets=[(25,30,12,40,300),(8,8,5,5,150),(50,50,20,20,2000),(40,40,10,10,1500),(30,30,10,10,800),
      (20,20,10,10,300),(60,60,50,50,1100),(100,10,30,30,150),(45,45,15,15,1800),
      (12,12,4,4,150),(23,19,11,7,380)]   # A,B,C,D,operating Vth
rows=[]
for sid,(A,B,C,D,Vop) in enumerate(sets):
    S=A*B-C*D; Vmax=2*Vop                                  # x-axis = 0 .. 2*Vth
    lf=next((v for v in range(0,Vmax+1) if m.sub_k2(A,B,C,D,v)==0),0)
    vals=set([0,Vmax,Vop]); step=max(1,Vmax//240); v=0
    while v<=Vmax: vals.add(v); v+=step
    for cen in (S,lf,Vop):
        for v in range(max(0,cen-25),min(Vmax,cen+25)+1): vals.add(v)
    for v in sorted(vals):
        if 0<=v<=Vmax: rows.append((sid,A,B,C,D,v))
with open('verif/sweep_sub_vec.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['sid','A','B','C','D','Vth']); w.writerows(rows)
PY
iverilog -g2012 -o verif/tb_sweep_sub.vvp verif/tb_sweep_sub.v \
    rtl/mult_sub.v rtl/log_sub.v rtl/lod5.v rtl/lns_add.v rtl/lns_ftable.v
vvp verif/tb_sweep_sub.vvp

echo "== Phase 4d: repeat subtraction sweep at K=3 (F-ROM swapped, then restored) =="
cp rtl/lns_ftable.v /tmp/_ftab_k2.v
python3 -c "import sys;sys.path.insert(0,'model');import model as m;m.K=3;m.SCALE=8;m.DMAX=2*(m.SCALE*(m.WIDTH-1)+(m.SCALE-1));m.FTAB=m.build_ftab(m.DMAX);m.emit_ftable_v()"
sed -e 's/\.K(2)/.K(3)/' -e 's/sweep_sub_rtl\.csv/sweep_sub_rtl_k3.csv/' verif/tb_sweep_sub.v > verif/tb_sweep_sub_k3.v
iverilog -g2012 -o verif/tb_sweep_sub_k3.vvp verif/tb_sweep_sub_k3.v \
    rtl/mult_sub.v rtl/log_sub.v rtl/lod5.v rtl/lns_add.v rtl/lns_ftable.v
vvp verif/tb_sweep_sub_k3.vvp
cp /tmp/_ftab_k2.v rtl/lns_ftable.v                     # restore the committed K=2 F-ROM
python3 - <<'PY'
import csv
a=list(csv.DictReader(open('verif/sweep_sub_rtl.csv'))); b=list(csv.DictReader(open('verif/sweep_sub_rtl_k3.csv')))
for x,y in zip(a,b): x['out_log_k3']=y['out_log']
cols=['sid','A','B','C','D','Vth','out_mult','out_log','out_log_k3']
with open('verif/sweep_sub_rtl.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(a)
PY

echo "== Phase 5: synthesis =="
yosys -s synth/run_mult.ys > synth/d1_synth.log 2>&1
yosys -s synth/run_log.ys  > synth/d2_synth.log 2>&1
for n in synth/mult_detector_netlist.v synth/log_detector_netlist.v; do
    [ "$(grep -cE '^\s*\$' "$n")" -eq 0 ] || { echo "$n has \$-cells"; exit 1; }
done

echo "== Phase 5b: area vs K (re-synthesize log_detector for K=0..3) =="
python3 scripts/area_vs_k.py
echo "== Phase 5c: disagreement vs K (Monte-Carlo, K=0..4) =="
python3 scripts/disagree_vs_k.py

echo "== Phase 6: power + area =="
python3 model/power_area.py

echo "== Phase 6b: standard-cell floorplan + GDS =="
python3 model/floorplan.py

echo "== Phase 7: GitHub page =="
python3 model/build_page.py

echo "== Done. See report/SUMMARY.md and docs/index.html =="
