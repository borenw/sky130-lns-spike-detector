#!/usr/bin/env python3
# Measured end-to-end disagreement rate (out_k1 != out_exact) as a function of K,
# using the SAME Monte-Carlo methodology as model/model.py (seed 1234, 4M random
# A,B,C,D combos x the fixed Vth list).  K=2 reproduces the headline 2.838%.
# Output: report/disagree_vs_k.csv  (K, disagree_pct)
import sys, os, csv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "model")); import model as M
import numpy as np

N, SEED = 4_000_000, 1234
rows = []
for K in range(0, 5):
    M.K = K; M.SCALE = 1 << K
    M.DMAX = 2 * (M.SCALE * (M.WIDTH - 1) + (M.SCALE - 1)); M.FTAB = M.build_ftab(M.DMAX)
    A, B, C, D, Sexact, s, s_zero = M.compute_sample(N, SEED)
    dis = tot = 0
    for Vth in M.VTHS:
        exact = (Sexact > Vth).astype(np.int8)
        k1 = M.k1_out_vec(s, s_zero, Vth)
        dis += int(np.count_nonzero(exact != k1)); tot += Sexact.size
    rate = 100.0 * dis / tot
    rows.append([K, round(rate, 3)])
    print("K=%d  disagreement = %.3f%%" % (K, rate))

with open("report/disagree_vs_k.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["K", "disagree_pct"]); w.writerows(rows)
