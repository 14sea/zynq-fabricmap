# Resume the B4 carrier v2 build from the ROUTED checkpoint: the isolation checks, the bitstream, the provenance
# record. Used when the checks themselves were corrected after a routed build (no re-synthesis, no re-route: the
# routed design is the one judged).
#   vivado -mode batch -source vivado/b4/resume_b4.tcl -tclargs <outdir> <NONCE_SEED as 16 hex>
set outdir [lindex $argv 0]
set seedhex [lindex $argv 1]
set part   xc7z010clg400-1
set here   [file dirname [file normalize [info script]]]
open_checkpoint $outdir/post_route.dcp
source $here/isolation_checks_b4.tcl
b4_isolation_checks $outdir
write_bitstream -force $outdir/b4.bit
set bit_sha [lindex [exec sha256sum $outdir/b4.bit] 0]
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set icap [llength [get_cells -hierarchical -filter {REF_NAME =~ "ICAPE2*"}]]
set ram [llength [get_cells -hierarchical -filter {REF_NAME == RAM32X1S}]]
set fh [open $outdir/b4_build.json w]
puts $fh "{\"schema\": \"b4_carrier_build\", \"schema_version\": \"1.0.0\", \"part\": \"$part\", \"top\": \"b4_top\","
puts $fh " \"vivado\": \"[version -short]\", \"routed\": true, \"cell_isolation\": \"passed\", \"wns_ns\": $wns, \"icape2_cells\": $icap,"
puts $fh " \"startupe2_cells\": 1, \"ram32x1s_cells\": $ram, \"bitstream\": \"b4.bit\", \"bitstream_sha256\": \"$bit_sha\", \"nonce_seed\": \"0x$seedhex\","
puts $fh " \"gate\": \"b4_gate (the B1 gate without the sweep; persistent nonce / armed / fault); VARIANT 0x2034 = 0x42340001\","
puts $fh " \"init_mechanism\": \"(b) GSR through STARTUPE2, driven by b4_engine; the key, nonce, fault, armed latch, samples and witnesses in RAM32X1S\","
puts $fh " \"key\": \"runtime-provisioned, write-once, persistent across the init event; not in this bitstream\","
puts $fh " \"resumed_from\": \"post_route.dcp (the isolation checker's BEL string corrected after the first routed build; no re-synthesis, no re-route)\"}"
close $fh
puts "B4 BUILD OK -> $outdir/b4.bit ($bit_sha) WNS=$wns ICAPE2=$icap RAM32X1S=$ram"
