set LIBDIR /usr/local/packages/tsmc_18m/ip/digital/Front_End/timing_power_noise/NLDM/tcb018gbwp7t_270a
create_library_set -name libs_typ -timing [list $LIBDIR/tcb018gbwp7ttc.lib]
create_rc_corner    -name rc_typ
create_delay_corner -name dc_typ -library_set libs_typ -rc_corner rc_typ
create_constraint_mode -name cm_func -sdc_files [list mult_cd.sdc]
create_analysis_view   -name av_typ -constraint_mode cm_func -delay_corner dc_typ
set_analysis_view -setup {av_typ} -hold {av_typ}
