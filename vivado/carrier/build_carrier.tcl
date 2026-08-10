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
