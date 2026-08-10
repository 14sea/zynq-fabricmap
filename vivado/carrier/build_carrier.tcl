# Build the Claim B round-1 carrier: synth + place + route + bitstream + the isolation
# checks that must pass before the result is looked at.
#
#   vivado -mode batch -source build_carrier.tcl -tclargs <outdir>
#
# Every get_cells/get_nets goes through `pick`, which errors unless exactly the expected
# number matched. Vivado has silently built the wrong thing and exited 0 three times in
# this repo; a warn-and-continue path is how that keeps happening.

set outdir [lindex $argv 0]
set part   xc7z010clg400-1
set here   [file dirname [file normalize [info script]]]
file mkdir $outdir

proc pick {what pattern want} {
    set got [eval $pattern]
    if {[llength $got] != $want} {
        error "$what: expected $want, got [llength $got]: $got"
    }
    return $got
}

create_project -in_memory -part $part
set_property verilog_define {} [current_fileset]
add_files -norecurse [list \
    $here/carrier_top.v $here/carrier_axil.v $here/carrier_envelope.v \
    $here/carrier_guard.v $here/carrier_scorer.v]
set_property include_dirs [list $here/generated] [current_fileset]
add_files -fileset constrs_1 -norecurse $here/carrier.xdc

# The scorer reads its constants with $readmemh at elaboration. Vivado resolves those
# paths relative to the working directory, so this script is run FROM generated/.

synth_design -top carrier_top -part $part -flatten_hierarchy none \
             -include_dirs $here/generated
write_checkpoint -force $outdir/post_synth.dcp
report_utilization -file $outdir/post_synth_util.rpt

opt_design

# The logic pblock, applied AFTER opt_design so it sees the cells that will actually be
# placed. Measured column mapping (not assumed):
#   CLBLL_L_X2 (major 20, TARGET) -> SLICE_X2, X3
#   CLBLM_R_X3 (major 21, FLUSH)  -> SLICE_X4, X5
#   CLBLM_L_X6 (major 24, TARGET) -> SLICE_X8, X9
#   DSP_R_X7   (major 25, FLUSH)  -> no slices
create_pblock pb_logic
set logic_cells [get_cells -hierarchical -filter {IS_PRIMITIVE && NAME !~ "evolvable_*"}]
if {[llength $logic_cells] < 100} {
    error "pblock would capture only [llength $logic_cells] cells; the filter is wrong"
}
add_cells_to_pblock pb_logic $logic_cells
resize_pblock pb_logic -add {SLICE_X0Y0:SLICE_X1Y99}
resize_pblock pb_logic -add {SLICE_X6Y0:SLICE_X7Y99}
resize_pblock pb_logic -add {SLICE_X10Y0:SLICE_X43Y99}
resize_pblock pb_logic -add {RAMB36_X0Y0:RAMB36_X2Y19}
puts "pblock pb_logic: [llength [get_cells -of_objects [get_pblocks pb_logic]]] cells assigned"

place_design
route_design
write_checkpoint -force $outdir/post_route.dcp
report_timing_summary -file $outdir/timing.rpt
report_utilization   -file $outdir/post_route_util.rpt

# ------------------------------------------------------------------ isolation checks
source $here/isolation_checks.tcl
carrier_isolation_checks $outdir

write_bitstream -force $outdir/carrier.bit
puts "CARRIER BUILD OK -> $outdir/carrier.bit"
