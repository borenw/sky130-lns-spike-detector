# Standalone Magic DRC signoff on a routed GDS (bonus; OpenLane also does this).
# Run on a host with Magic + sky130A PDK:
#   magic -dnull -noconsole \
#     -rcfile $PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc \
#     signoff_magic_drc.tcl <routed_gds> <top_cell>
#
set gdsfile [lindex $argv 0]
set topcell [lindex $argv 1]
gds read $gdsfile
load $topcell
select top cell
drc euclidean on
drc style drc(full)
drc check
drc catchup
set n [drc list count total]
puts "======================================================"
puts " DRC signoff : $topcell"
puts " total DRC violations = $n"
if {$n == 0} { puts " RESULT: DRC CLEAN" } else { puts " RESULT: DRC VIOLATIONS ($n)" }
puts "======================================================"
# dump the offending regions if any
if {$n > 0} { drc why }
exit 0
