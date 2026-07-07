# Verilog-A model — `lns_detector.va`

Cadence **Spectre** (Verilog-A) behavioral model of the multiplier-free log/LNS MAC
detector, with every internal log-domain net exposed for probing.

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
`exact=1` for the mathematical reference. (In K-bit mode the per-operand log
converters are quantized exactly as in RTL; the `F(|x-y|)` correction is evaluated
in closed form rather than from the rounded ROM — the only difference vs. gate-level.)

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

> Behavioral model, not verified in this repo’s host (no Spectre here); it targets
> Cadence Spectre / Virtuoso. Standard Verilog-AMS (`constants.vams`,
> `disciplines.vams`).
