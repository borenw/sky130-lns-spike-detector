set init_lef_file /usr/local/packages/tsmc_18m/ip/digital/Back_End/lef/tcb018gbwp7t_270a/lef/tcb018gbwp7t_6lm.lef
set init_verilog mult_cd_tcb018.v
set init_top_cell mult_cd
set init_pwr_net VDD
set init_gnd_net VSS
set init_mmmc_file mmmc_multcd.tcl
init_design
setDesignMode -process 180
floorPlan -site core7T -r 1.0 0.62 6 6 6 6
set inpins {}
foreach b {C D} { for {set i 9} {$i>=0} {incr i -1} { lappend inpins "$b\[$i\]" } }
set outpins {}
for {set i 19} {$i>=0} {incr i -1} { lappend outpins "P\[$i\]" }
setPinAssignMode -pinEditInBatch true
editPin -side Left  -layer METAL3 -spreadType center -pin $inpins
editPin -side Right -layer METAL3 -spreadType center -pin $outpins
setPinAssignMode -pinEditInBatch false
globalNetConnect VDD -type pgpin -pin VDD -inst * -verbose
globalNetConnect VSS -type pgpin -pin VSS -inst * -verbose
globalNetConnect VDD -type net -net VDD
globalNetConnect VSS -type net -net VSS
addRing -nets {VDD VSS} -type core_rings -layer {top METAL5 bottom METAL5 left METAL6 right METAL6} -width 2 -spacing 2 -offset 2
place_design
sroute -connect {corePin floatingStripe} -nets {VDD VSS}
routeDesign
addFiller -cell {FILL64BWP7T FILL32BWP7T FILL16BWP7T FILL8BWP7T FILL4BWP7T FILL2BWP7T FILL1BWP7T} -prefix FILLER
setExtractRCMode -engine postRoute
extractRC
verifyConnectivity -type all -report multcd_conn.rpt
verify_drc -report multcd_drc.rpt
saveNetlist mult_cd_pnr.v
defOut -floorplan -netlist -routing mult_cd.def
streamOut mult_cd.gds -mapFile tsmc_streamout.map -merge /usr/local/packages/tsmc_18m/ip/digital/Back_End/gds/tcb018gbwp7t_270a/tcb018gbwp7t.gds -units 1000 -mode ALL
summaryReport -outfile multcd_summary.rpt
exit
