let( (cv n m errs)
    cv = dbOpenCellViewByType("myLib" "vth_prime" "schematic" "schematic" "a")
    if( cv then
        n = length(cv->instances)
        m = length(cv->nets)
        errs = schCheck(cv)
        printf("VTHP_SCH_OK instances=%d nets=%d schCheckErrs=%L\n" n m errs)
        dbCheck(cv)
        dbClose(cv)
    else
        printf("VTHP_SCH_FAIL: could not open\n")
    )
)
exit()
