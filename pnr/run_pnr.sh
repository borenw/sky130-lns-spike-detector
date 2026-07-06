#!/usr/bin/env bash
# Run place-and-route + DRC + LVS on a host that HAS the toolchain + PDK.
# This does NOT run on the synthesis-only host these RTL/estimates were built on
# (no OpenROAD/OpenLane/Magic/Netgen, no physical sky130 PDK there).
#
# Prereqs on the PnR host:
#   * OpenLane 2 / LibreLane   (pip install openlane)   OR classic OpenLane (Docker)
#   * sky130 physical PDK       (volare enable <hash>, sets PDK_ROOT/sky130A)
#
# Usage:
#   ./run_pnr.sh log     # place & route + signoff the log_detector
#   ./run_pnr.sh mult    # place & route + signoff the mult_detector baseline
set -euo pipefail
cd "$(dirname "$0")"
which=${1:-log}
cfg="config_${which}.json"
[ -f "$cfg" ] || { echo "no $cfg"; exit 1; }

echo "== OpenLane PnR + signoff for $cfg =="
# OpenLane 2 (LibreLane, pip):
openlane "$cfg"                 # -> runs/<tag>/  with final GDS + DRC/LVS reports
# Classic OpenLane 1 (Docker) equivalent:
#   flow.tcl -design . -config_file "$cfg" -tag pnr

echo
echo "== where the deliverables land (OpenLane 2 layout) =="
echo "  routed GDS : runs/*/final/gds/${which}_detector.gds"
echo "  Magic DRC  : runs/*/**/*-drc/reports/drc.rpt          (violations: 0 == clean)"
echo "  KLayout DRC: runs/*/**/*klayout*drc*/reports/*.xml"
echo "  Netgen LVS : runs/*/**/*-lvs/reports/lvs.rpt           ('Circuits match uniquely' == clean)"
echo "  timing     : runs/*/**/*sta*/reports/*.rpt"
