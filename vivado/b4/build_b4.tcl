# B4 carrier v2 build: the B1 build (vivado/b1/build_b1.tcl, pinned) re-pointed at the v2 RTL — synth -> pblock ->
# place / route -> the v2 isolation checks -> bitstream -> provenance. Host-only; touches no board.
#
#   vivado -mode batch -source vivado/b4/build_b4.tcl -tclargs <outdir> <NONCE_SEED as 16 hex>
set outdir [lindex $argv 0]
set seedhex [lindex $argv 1]
set part   xc7z010clg400-1
set here   [file dirname [file normalize [info script]]]
set repo   [file dirname [file dirname $here]]
file mkdir $outdir
create_project -in_memory -part $part
set srcs [list $repo/rtl/b4/b4_top.v $repo/rtl/b4/b4_core.v $repo/rtl/b4/b4_axil.v $repo/rtl/b4/b4_gate.v $repo/rtl/b4/b4_engine.v \
               $repo/rtl/b4/b4_gsr_reg.v $repo/rtl/b4/b4_slot_ram.v $repo/rtl/b4/b4_target_slice.v \
               $repo/rtl/b1/p3_siphash.v $repo/vivado/carrier/carrier_axi3_lite.v]
add_files -norecurse $srcs
add_files -fileset constrs_1 -norecurse $here/b4.xdc
synth_design -top b4_top -part $part -flatten_hierarchy none -generic "NONCE_SEED=64'h$seedhex"
write_checkpoint -force $outdir/post_synth.dcp
report_utilization -file $outdir/post_synth_util.rpt
opt_design
create_pblock pb_logic
set logic_cells [get_cells -hierarchical -filter {IS_PRIMITIVE && NAME !~ "target/target_*" && NAME != "startup" && NAME != "ps7"}]
if {[llength $logic_cells] < 100} { error "pblock would capture only [llength $logic_cells] cells" }
add_cells_to_pblock pb_logic $logic_cells
resize_pblock pb_logic -add {SLICE_X0Y0:SLICE_X1Y99}
resize_pblock pb_logic -add {SLICE_X6Y0:SLICE_X7Y99}
resize_pblock pb_logic -add {SLICE_X14Y0:SLICE_X25Y99}
set_property IS_SOFT false [get_pblocks pb_logic]
puts "pblock pb_logic: PRIMITIVE_COUNT=[get_property PRIMITIVE_COUNT [get_pblocks pb_logic]]"
place_design
route_design
write_checkpoint -force $outdir/post_route.dcp
report_timing_summary -file $outdir/timing.rpt
report_utilization   -file $outdir/post_route_util.rpt
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
puts $fh " \"key\": \"runtime-provisioned, write-once, persistent across the init event; not in this bitstream\"}"
close $fh
puts "B4 BUILD OK -> $outdir/b4.bit ($bit_sha) WNS=$wns ICAPE2=$icap RAM32X1S=$ram"
