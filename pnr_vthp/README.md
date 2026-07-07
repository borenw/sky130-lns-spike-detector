# Innovus P&R — log-based `vth_prime` vs multiplier `mult_cd` (tcb018, 0.18µm)

Standard-cell place & route of the two blocks (yosys tcb018 netlist → Innovus →
DRC-clean GDS → strmin to Virtuoso `layout`). Matched 10-bit C,D inputs.

| | vth_prime (log, full Vth′) | mult_cd (10×10 C·D) |
|--|--:|--:|
| gate cells        | 179        | 343        |
| std-cell area     | 4215 µm²   | 9824 µm²   |
| die               | 159×150 µm | 225×221 µm |
| die area          | ~23.9k µm² | ~49.7k µm² |
| DRC               | clean      | clean      |

A single 10×10 multiplier is ~2× the whole log-domain Vth′ block.

Flow (per dir `pnr_vthp/`, `pnr_multcd/`): `run_*_pnr.tcl` (Innovus), `mmmc_*.tcl`,
`*.sdc`, `tsmc_streamout.map`. Run: `innovus -no_gui -files run_*_pnr.tcl`. Then
`strmin -library <lib> -strmFile *.gds -layerMap tsmc18.layermap -view layout`.
Schematics: `myLib/{vth_prime,mult_cd}` (via ihdl). Layouts: `vthp_pnr/{vth_prime,mult_cd}`.
