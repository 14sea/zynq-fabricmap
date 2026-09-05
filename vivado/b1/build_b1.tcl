# B1 carrier build: the instrument's P3 build (zynq-psoracle/vivado/p3/build_p3.tcl, copied and
# re-pointed) over the B1 RTL variant — synth -> pblock -> place/route -> isolation checks ->
# bitstream -> provenance. Host-only; touches no board.
#
#   vivado -mode batch -source vivado/b1/build_b1.tcl -tclargs <outdir> <NONCE_SEED as 16 hex>
#
# The B1 RTL (rtl/b1/): b1_top/b1_core/b1_axil/b1_arm_gate (derived from the instrument's,
# SEMANTIC_GATE = 0, the VARIANT register) and the verbatim p3_siphash.v; the carrier's own
# files (AXI3 shim, scorer, XDC, isolation checks, generated constants) from THIS repository's
# vivado/carrier, which are hash-equal to the copies the instrument imported at 71666b02
# (tests/test_b1_carrier.py). No key generic: the MAC key is provisioned at runtime.
set outdir [lindex $argv 0]
set seedhex [lindex $argv 1]
set part   xc7z010clg400-1
set here   [file dirname [file normalize [info script]]]
set repo   [file dirname [file dirname $here]]
set fm     $repo/vivado/carrier
file mkdir $outdir
create_project -in_memory -part $part
set srcs [list $repo/rtl/b1/b1_top.v $repo/rtl/b1/b1_core.v $repo/rtl/b1/b1_axil.v $repo/rtl/b1/b1_arm_gate.v \
               $repo/rtl/b1/p3_siphash.v $fm/carrier_axi3_lite.v $fm/carrier_scorer.v]
add_files -norecurse $srcs
set_property include_dirs [list $fm/generated] [current_fileset]
add_files -fileset constrs_1 -norecurse $fm/carrier.xdc
synth_design -top b1_top -part $part -flatten_hierarchy none -include_dirs $fm/generated \
    -generic "NONCE_SEED=64'h$seedhex" -generic "SEMANTIC_GATE=0"
write_checkpoint -force $outdir/post_synth.dcp
report_utilization -file $outdir/post_synth_util.rpt
opt_design
create_pblock pb_logic
set logic_cells [get_cells -hierarchical -filter {IS_PRIMITIVE && NAME !~ "evolvable_*"}]
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
source $fm/isolation_checks.tcl
carrier_isolation_checks $outdir
write_bitstream -force $outdir/b1.bit
set bit_sha [lindex [exec sha256sum $outdir/b1.bit] 0]
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set icap [llength [get_cells -hierarchical -filter {REF_NAME =~ "ICAPE2*"}]]
set fh [open $outdir/b1_build.json w]
puts $fh "{\"schema\": \"p3_build\", \"schema_version\": \"1.0.0\", \"part\": \"$part\", \"top\": \"b1_top\","
puts $fh " \"vivado\": \"[version -short]\", \"routed\": true, \"cell_isolation\": \"passed\", \"wns_ns\": $wns, \"icape2_cells\": $icap,"
puts $fh " \"bitstream\": \"b1.bit\", \"bitstream_sha256\": \"$bit_sha\", \"nonce_seed\": \"0x$seedhex\","
puts $fh " \"gate\": \"b1_arm_gate SEMANTIC_GATE=0 (docs/b1_carrier_contract.md); VARIANT 0x2034 = 0x42310001\","
puts $fh " \"key\": \"runtime-provisioned, write-once register (instrument D4 option A); not in this bitstream\"}"
close $fh
puts "B1 BUILD OK -> $outdir/b1.bit ($bit_sha) WNS=$wns ICAPE2=$icap"
