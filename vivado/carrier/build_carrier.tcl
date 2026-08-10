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

# ONE CONTIGUOUS REGION, clear of all four column segments (SLICE X2..X5 and X8..X9).
# Three disjoint islands routed, but asking for CONTAIN_ROUTING on them produced 3
# unroutable pins and 196 reachable-but-unrouted pins: disjoint islands are not a usable
# routing topology, whatever they are as a placement constraint.
# Region 1 of the frozen order (design §9): a contiguous block clear of all four column
# segments.
#
# Region 2 (SLICE_X0..X1, left of the flush column) was TRIED and is worse: 190 flush nets
# against 124, because the BRAM the buffer needs then sits across INT_R_X7 from the logic
# and axi_buf_rdata crosses instead. Recorded so it is not re-tried as an idea.
resize_pblock pb_logic -add {SLICE_X10Y0:SLICE_X43Y99}
resize_pblock pb_logic -add {RAMB36_X1Y0:RAMB36_X2Y19}

# THE PROPERTY THAT ACTUALLY MAKES IT A BOUNDARY. Vivado pblocks default to IS_SOFT=1,
# which the placer may cross; the range is a preference until this is false. Every
# earlier "the pblock is barely applied" reading came from here, not from
# add_cells_to_pblock: all 865 primitives did carry PBLOCK=pb_logic, and the CELL_COUNT of
# 36 that suggested otherwise is not a leaf-primitive count at all (PRIMITIVE_COUNT is).
set_property IS_SOFT false [get_pblocks pb_logic]

puts "pblock pb_logic: PRIMITIVE_COUNT=[get_property PRIMITIVE_COUNT [get_pblocks pb_logic]] IS_SOFT=[get_property IS_SOFT [get_pblocks pb_logic]]"

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
