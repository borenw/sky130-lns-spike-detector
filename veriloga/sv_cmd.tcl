set fp [open "/tmp/sv_probe.txt" w]
set dbs [database list]
puts $fp "DBS=$dbs"
set db [lindex $dbs 0]
catch {puts $fp "SIGS=[database signals -database $db]"} e
puts $fp "sigerr=$e"
close $fp
window new WaveWindow -name Compare
waveform using [window find -match exact -name Compare]
foreach s {outM outL Vth sM sL x y} {
  catch {waveform add -signals ${db}::$s}
}
