#!/usr/bin/env python3
# Real sky130 standard-cell area of log_detector as a function of K (helper bits),
# vs the multiplier baseline.  For each K the F-ROM is regenerated (its table + width
# depend on K) and log_detector is synthesized with chparam K.  The shared 8-bit log
# buses / 8-bit ROM address cleanly cover K<=3; K=4 (9-bit Vth log + 318-entry ROM)
# is linear-extrapolated from the measured points and flagged 'estimate'.
# Output: report/area_vs_k.csv  (K, cells, area_um2, pct_of_mult, source)
import sys, os, subprocess, re, shutil, csv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "model")); import model as M
LIB = "synth/sky130_fd_sc_hd__tt_025C_1v80.lib"
MULT_AREA = 8845.984            # multiplier baseline, real synth (report/power_area.csv)

def synth_area(K):
    M.K = K; M.SCALE = 1 << K
    M.DMAX = 2 * (M.SCALE * (M.WIDTH - 1) + (M.SCALE - 1)); M.FTAB = M.build_ftab(M.DMAX)
    M.emit_ftable_v()
    ys = ("read_verilog -sv rtl/log_detector.v rtl/lod5.v rtl/lns_add.v rtl/lns_ftable.v\n"
          "chparam -set K %d log_detector\nhierarchy -top log_detector\n"
          "synth -top log_detector -flatten\ndfflibmap -liberty %s\nabc -liberty %s\n"
          "opt_clean\ndelete t:$scopeinfo\nstat -liberty %s\n" % (K, LIB, LIB, LIB))
    open("synth/_tmp_k.ys", "w").write(ys)
    out = subprocess.run(["yosys", "-s", "synth/_tmp_k.ys"], capture_output=True, text=True)
    txt = out.stdout + out.stderr
    a = re.search(r"Chip area for.*?:\s*([\d.]+)", txt)
    c = re.search(r"Number of cells:\s*(\d+)", txt)
    return (int(c.group(1)), float(a.group(1))) if a else (0, None)

rows = []
shutil.copy("rtl/lns_ftable.v", "rtl/lns_ftable.v.bak")
try:
    for K in (0, 1, 2, 3):
        cells, area = synth_area(K)
        rows.append([K, cells, round(area, 1), round(100 * area / MULT_AREA, 1), "measured"])
finally:
    shutil.move("rtl/lns_ftable.v.bak", "rtl/lns_ftable.v")   # restore K=2 F-ROM
    if os.path.exists("synth/_tmp_k.ys"): os.remove("synth/_tmp_k.ys")

# linear fit over measured points -> extrapolate K=4
ks = [r[0] for r in rows]; ars = [r[2] for r in rows]
n = len(ks); mk = sum(ks) / n; ma = sum(ars) / n
slope = sum((k - mk) * (a - ma) for k, a in zip(ks, ars)) / sum((k - mk) ** 2 for k in ks)
a4 = ma + slope * (4 - mk)
rows.append([4, "", round(a4, 1), round(100 * a4 / MULT_AREA, 1), "estimate"])

with open("report/area_vs_k.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["K", "cells", "area_um2", "pct_of_mult", "source"])
    w.writerows(rows)
print("mult baseline %.1f um2" % MULT_AREA)
for r in rows:
    print("K=%d  cells=%-5s area=%-8s %%mult=%5.1f%%  (%s)" % (r[0], r[1], r[2], r[3], r[4]))
