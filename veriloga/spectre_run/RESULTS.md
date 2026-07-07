# Spectre simulation results — `tb_compare.scs`

Ran on host **tau** with **Cadence Spectre 20.1.0.186** (`0 errors, 0 warnings`).
DC sweep of `Vth` = 0 → 2000 (1001 points), operands fixed at **A,B,C,D = 25,30,12,40**,
comparing `mult_detector.va` (exact) against `lns_detector.va` (log/LNS, `exact=0 kbits=2`).

## Internal nets at the operating point

| net | model | value |
|-----|-------|-------|
| `p1 = A*B` | mult | 750 |
| `p2 = C*D` | mult | 480 |
| `sM = A*B+C*D` | mult | **1230** |
| `x = log2(A*B)` | log K=2 | 9.250 |
| `y = log2(C*D)` | log K=2 | 8.750 |
| `sL = log2(A*B+C*D)` | log K=2 | 10.000  (2^sL = **1024**) |

## Comparator outputs (vs the Vth sweep)

| | flips at Vth | meaning |
|--|--|--|
| `outM` (exact multiplier) | **1230** | `= A*B + C*D` (exact) |
| `outL` (log / LNS, K=2)   | **1024** | `= 2^sL`, the K=2 approximation |

**Disagreement band: Vth ∈ [1024, 1228]** (103 sweep points) — the log model reads 0
while the exact reads 1.

## Cross-check vs. RTL

This is **identical** to the Icarus RTL sweep on the page (`log_detector.v` flips at 1024,
`mult_detector.v` at 1230, band 1024–1229). The Verilog-A `exact=0` model rounds the
`F(|x−y|)` correction to `1/2^K` exactly like the RTL F-ROM, so the analog behavioral
model and the gate-level RTL agree bit-for-bit on the decision boundary.

## Reproduce

```
export PATH=/usr/local/packages/cadence_2021/SPECTRE201/tools.lnx86/bin:$PATH
export CDS_LIC_FILE=/usr/local/packages/cadence_2021/license.dat
cd veriloga
spectre tb_compare.scs -format psfascii -raw ./spectre_run
# parse ./spectre_run/swpVth.dc  (compare.csv is the extracted Vth,outM,outL,… table)
```
