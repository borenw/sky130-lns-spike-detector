# PnR + DRC + LVS — how to get the real routed GDS and signoff

**These scripts were prepared on a synthesis-only host that cannot run place-and-route,
DRC or LVS** (no OpenROAD/OpenLane, Magic, KLayout or Netgen, and no *physical* sky130
PDK — only the timing `.lib`). So this repo ships **logical synthesis + a standard-cell
floorplan estimate**, not a routed layout. Run the flow below on a machine that has the
toolchain to produce the genuine routed GDS and the DRC/LVS-clean signoff.
See `../report/DRC_LVS_STATUS.txt` for the honest current status.

## Prerequisites (on the PnR host)
- **OpenLane 2 / LibreLane**: `pip install openlane` (pulls its tools via Nix), **or**
  classic OpenLane 1 (Docker image `efabless/openlane`).
- **sky130 physical PDK**: `pip install volare && volare enable <hash>` — sets
  `PDK_ROOT` with `sky130A` (tech-LEF, cell-LEF, cell-GDS, Magic tech, DRC decks, Netgen setup).

## Run it
```bash
./run_pnr.sh log     # multiplier-free log_detector (10-bit, K=2)
./run_pnr.sh mult    # exact-multiplier baseline
```
Each invocation runs synth → floorplan → place → CTS → route → GDS, then **Magic DRC +
KLayout DRC + Netgen LVS** as signoff steps (all part of the default OpenLane flow).

## What comes out (OpenLane 2 layout)
| Deliverable | Path | "Clean" looks like |
|---|---|---|
| Routed **GDS** | `runs/*/final/gds/<top>.gds` | — |
| **Magic DRC** | `runs/*/**/*-drc/reports/drc.rpt` | `COUNT: 0` |
| **KLayout DRC** | `runs/*/**/*klayout*drc*/reports/*.xml` | 0 items |
| **Netgen LVS** | `runs/*/**/*-lvs/reports/lvs.rpt` | `Circuits match uniquely` |
| Post-route timing | `runs/*/**/*sta*/reports/*.rpt` | met (WNS ≥ 0) |

## Standalone DRC (bonus)
If you have Magic + the PDK but not full OpenLane, DRC-check any GDS directly:
```bash
magic -dnull -noconsole \
  -rcfile $PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc \
  signoff_magic_drc.tcl runs/*/final/gds/log_detector.gds log_detector
```
Standalone LVS with Netgen (needs the Magic-extracted spice + the netlist):
```bash
netgen -batch lvs \
  "log_detector.spice log_detector" \
  "../synth/log_detector_netlist.v log_detector" \
  $PDK_ROOT/sky130A/libs.tech/netgen/sky130A_setup.tcl lvs.rpt
```

## Files
- `config_log.json`, `config_mult.json` — OpenLane configs (clock 20 ns = 50 MHz,
  `sky130_fd_sc_hd`, 45 % util, DRC+LVS enabled).
- `run_pnr.sh` — driver.
- `signoff_magic_drc.tcl` — standalone Magic DRC on a GDS.

Once you run these, drop the produced `drc.rpt` / `lvs.rpt` (or the OpenLane summary)
back into `report/` and the honest status file can be replaced with the real clean summary.
