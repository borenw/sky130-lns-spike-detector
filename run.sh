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
sets=[(25,30,12,40),(8,8,5,5),(50,50,20,20),(3,3,3,3),(40,40,10,10),(30,30,10,10)]
rows=[]
for sid,(A,B,C,D) in enumerate(sets):
    S=A*B-C*D; Vhi=max(80,2*S+80)
    lf=next((v for v in range(0,Vhi+1) if m.sub_k2(A,B,C,D,v)==0),0)
    lo=max(0,min(S,lf)-30); hi=max(S,lf)+30; Vmax=max(Vhi,hi+40)
    vals=set(); step=max(1,Vmax//200); v=0
    while v<=Vmax: vals.add(v); v+=step
    for v in range(lo,hi+1): vals.add(v)
    for v in sorted(vals): rows.append((sid,A,B,C,D,v))
with open('verif/sweep_sub_vec.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['sid','A','B','C','D','Vth']); w.writerows(rows)
PY
iverilog -g2012 -o verif/tb_sweep_sub.vvp verif/tb_sweep_sub.v \
    rtl/mult_sub.v rtl/log_sub.v rtl/lod5.v rtl/lns_add.v rtl/lns_ftable.v
vvp verif/tb_sweep_sub.vvp

echo "== Phase 5: synthesis =="
yosys -s synth/run_mult.ys > synth/d1_synth.log 2>&1
yosys -s synth/run_log.ys  > synth/d2_synth.log 2>&1
for n in synth/mult_detector_netlist.v synth/log_detector_netlist.v; do
    [ "$(grep -cE '^\s*\$' "$n")" -eq 0 ] || { echo "$n has \$-cells"; exit 1; }
done

echo "== Phase 6: power + area =="
python3 model/power_area.py

echo "== Phase 6b: standard-cell floorplan + GDS =="
python3 model/floorplan.py

echo "== Phase 7: GitHub page =="
python3 model/build_page.py

echo "== Done. See report/SUMMARY.md and docs/index.html =="
