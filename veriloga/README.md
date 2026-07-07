# Verilog-A models

Cadence **Spectre** (Verilog-A) behavioral models of both designs, with internal nets
exposed for probing:

- **`lns_detector.va`** — the multiplier-free **log / LNS** detector (log-domain nets).
- **`mult_detector.va`** — the **classic exact multiplier** baseline (product nets).
- **`tb_lns.scs`** — sweeps the LNS model alone.
- **`tb_compare.scs`** — instantiates **both** and overlays their outputs vs. a Vth sweep.

---

## `lns_detector.va` — multiplier-free log/LNS

Every internal log-domain net is exposed for probing.

```
out = ( A*B + C*D ) > Vth          computed in the log2 domain
```

## Ports

| dir | net | meaning |
|-----|-----|---------|
| in  | `A B C D` | operands (numeric value carried as a voltage: `V(A)=25` ⇒ A=25) |
| in  | `Vth` | threshold |
| out | `lA lB lC lD` | `log2(A) log2(B) log2(C) log2(D)` — the K-bit converters |
| out | `x` | `log2(A*B) = lA + lB` |
| out | `y` | `log2(C*D) = lC + lD` |
| out | `s` | `log2(A*B + C*D) = max(x,y) + log2(1 + 2^-|x-y|)` (the LNS add) |
| out | `out` | comparator: `1` when `s > log2(Vth)` ⇔ `A*B+C*D > Vth` |

## Parameters

| param | default | meaning |
|-------|---------|---------|
| `exact` | `1` | `1` = ideal continuous `log2` (reference); `0` = K-bit Mitchell converter matching `rtl/log_detector.v` |
| `kbits` | `2` | mantissa (helper) bits used when `exact=0` (this build: **K=2**) |
| `voh`/`vol` | `1.0`/`0.0` | logic output levels (V) |
| `tr` | `1n` | output transition time (s) |
| `vmin` | `1e-12` | floor keeping `log` finite as an operand → 0 |

Set `exact=0 kbits=2` to reproduce the synthesized hardware’s approximation; leave
`exact=1` for the mathematical reference. In K-bit mode the per-operand log converters
**and** the `F(|x-y|)` correction are quantized to `1/2^K` exactly like `rtl/log_detector.v`
+ its F-ROM, so the model tracks the gate-level design bit-for-bit (verified below).

## Use it

**Spectre netlist** — see `tb_lns.scs`:
```
ahdl_include "lns_detector.va"
X1 (A B C D Vth  lA lB lC lD  x y s  out) lns_detector exact=1 kbits=2
```
```
spectre tb_lns.scs        # DC-sweeps Vth; plot x y s lA lB out
```

**Virtuoso (ADE):** *File → Import → Verilog-A…* on `lns_detector.va` to create the
symbol/cellview, place it, wire `A B C D Vth` to sources and bring `x y s lA…lD out`
to output nets, then `save`/plot them.

## Sanity check (operating point, `exact=1`, A,B,C,D=25,30,12,40)

```
lA=log2(25)=4.644   lB=log2(30)=4.907   x=log2(750)=9.551
lC=log2(12)=3.585   lD=log2(40)=5.322   y=log2(480)=8.907
s =log2(1230)=10.264 ;  out = 1 while Vth < 1230, 0 above
```

---

## `mult_detector.va` — classic multiplier baseline

Exact reference: `out = (A·B + C·D) > Vth` with real multiplies.

| dir | net | meaning |
|-----|-----|---------|
| in  | `A B C D` | operands (numeric value as a voltage) |
| in  | `Vth` | threshold |
| out | `p1` | `A*B` |
| out | `p2` | `C*D` |
| out | `s` | `A*B + C*D` (or `A*B − C*D` when `sub=1`) |
| out | `out` | comparator: `1` when `s > Vth` |

Parameters: `sub` (`0`=add, `1`=subtract), `voh`/`vol`, `tr`. At A,B,C,D=25,30,12,40:
`p1=750, p2=480, s=1230`, and `out` flips exactly at `Vth=1230`.

## Compare both — `tb_compare.scs`

```
ahdl_include "mult_detector.va"
ahdl_include "lns_detector.va"
XM (A B C D Vth  p1 p2 sM  outM) mult_detector
XL (A B C D Vth  lA lB lC lD  x y sL  outL) lns_detector exact=0 kbits=2
```
```
spectre tb_compare.scs     # overlay outM vs outL against the Vth sweep
```
With `exact=0 kbits=2`, `outM` flips at Vth=1230 (exact) while `outL` flips at the K=2
approximation (~1024) — the same disagreement the RTL sweep shows on the page.

---

## Verified in Spectre

Both models were run on host **tau** with **Cadence Spectre 20.1** (`tb_compare.scs`,
`0 errors`). The DC-`Vth` sweep at A,B,C,D = 25,30,12,40 gives:

| output | flips at Vth | |
|--|--|--|
| `outM` exact multiplier | **1230** | `= A*B+C*D` |
| `outL` log/LNS (K=2) | **1024** | `= 2^sL` |

→ disagreement band **Vth ∈ [1024, 1228]** — **identical** to the Icarus RTL sweep on the
page (log_detector flips at 1024, mult_detector at 1230). Full numbers + the extracted
`compare.csv` are in [`spectre_run/RESULTS.md`](spectre_run/RESULTS.md).

