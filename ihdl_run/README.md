# Cadence schematic of `vth_prime` via Verilog-In (`ihdl`)

Builds `myLib/vth_prime/{schematic,symbol}` — a real Cadence schematic of the
full-exact Vth′(C,D) block, drawn from **tcb018gbwp7t** standard-cell symbols.

Flow: `rtl/vth_prime.v` → yosys (`synth/run_vthp.ys`, tcb018 NLDM liberty) →
`synth/vth_prime_tcb018.v` (179 tcb018 cells) → **`ihdl`** (`run_ihdl.sh`).

- `cds.lib`   — softincludes `~/Desktop/pnr180/cds.lib` (defines `myLib`, `tcb018gbwp7t`, `basic`).
- `param.txt` — Verilog-In parameter file (`dest_sch_lib=myLib`, `ref_lib_list=tcb018gbwp7t,basic`,
  `structural_views=1` i.e. schematic).
- `verify_sch.il` — headless `schCheck` (result: 183 instances, 571 nets, **0 errors**).

Run:  `./run_ihdl.sh`   (needs the live/headless Virtuoso IC618 + the 2021 license).
