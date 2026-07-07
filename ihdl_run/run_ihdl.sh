#!/bin/sh
# Import synth/vth_prime_tcb018.v into myLib as a Cadence schematic via Verilog-In (ihdl).
# Creates myLib/vth_prime/{schematic,symbol}, std cells resolved from tcb018gbwp7t.
export PATH=/usr/local/packages/cadence_2021/IC618/tools.lnx86/dfII/bin:$PATH
export CDS_LIC_FILE=/usr/local/packages/cadence_2021/license.dat
cd "$(dirname "$0")"
mkdir -p work
cp ../synth/vth_prime_tcb018.v .
ihdl -param param.txt -cdslib ./cds.lib -NOCOPYRIGHT vth_prime_tcb018.v
# verify (headless): open + schCheck + count
virtuoso -nograph -replay verify_sch.il -log verify.log >/dev/null 2>&1
grep -E "VTHP_SCH_OK|VTHP_SCH_FAIL" verify.log
