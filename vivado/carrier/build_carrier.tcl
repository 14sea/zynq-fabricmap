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
# One list, used both to add the sources and to hash them into the provenance record: a
# second hand-kept list would drift from what Vivado actually reads, which is the only list
# that matters.
set srcs [list $here/carrier_top.v $here/carrier_axi3_lite.v $here/carrier_axil.v \
               $here/carrier_stream.v $here/carrier_crc32.v $here/carrier_scorer.v]
add_files -norecurse $srcs
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
# LEFT of the first flush column, where PS7 also is. There is no BRAM in the design at all
# — with the frame-staged engine the candidate buffer is gone entirely (the AXI write
# channel is the word stream) and what remains is a 101-word readback window in LUTRAM —
# so nothing pulls the logic to the right-hand side of tile column X3.
#
# The right-hand region was tried at 124 crossers and the left-hand one with a BRAM buffer
# at 190; both were broken by CONTROL-class nets, which is what the one-envelope contract
# exists to remove. Recorded so neither is re-tried as an idea.
# RULED 2026-08-11 (user), erratum 002: TWO ranges, and this is the final floorplan —
# no further search for another one on LUT count or WNS.
#   SLICE_X0Y0:SLICE_X1Y99  left of the first written column, where PS7 also is
#   SLICE_X6Y0:SLICE_X7Y99  CLBLM_R_X5, baseaddr 0x00400B80 — NOT one of the 15 written FARs
# The second pair became necessary when the AXI3 shim erratum 002 requires landed: 837 LUTs
# post-opt against 800 sites, and `place_design` failed outright. It became ADMISSIBLE when
# erratum 001 retired the authority the old one-region floorplan served: crossing nets are
# an evidence record, cell ownership is the verdict, and bit invariance against the routed
# base is the rule. Measured with both ranges: place+route OK, WNS +7.305 ns, cell isolation
# target=6 flush=0, route inventory flush 415 / target 560 / foreign 554 — a larger
# blast-radius record, not a violated rule, because those routes are part of the base and
# every candidate rewrites them identically.
resize_pblock pb_logic -add {SLICE_X0Y0:SLICE_X1Y99}
resize_pblock pb_logic -add {SLICE_X6Y0:SLICE_X7Y99}

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

# ------------------------------------------------------------------ provenance
# Erratum 001 requires the 15 base frames to come from THE FINAL ROUTED CARRIER
# BITSTREAM, not an earlier probe or a DCP — and requires that to be machine-checked
# rather than asserted. Only this script knows, at this point, that the bitstream it
# just wrote is the routed design whose cell isolation passed, so it is this script
# that records it. scripts/gate_carrier_base.py refuses a phenotype_manifest whose
# base does not match this record.
# THE SOURCES, hashed, and the commit they came from. Output hashes alone cannot show that
# a bitstream was built from the RTL now in history: carrier_stream.v, carrier_scorer.v and
# carrier_top.v were all edited AFTER a published build, the integration bench verified the
# new sources, and the exact bitstream a board would load was still the pre-fix one. Nothing
# in the record could have caught that.
#
# Every file Vivado actually reads is listed here — the sources added above, the XDC, the
# generated inputs, and the two scripts that run the build and the checks — so
# `scripts/gate_carrier_base.py` can require each to equal its HEAD blob and refuse a
# bitstream whose sources have since moved.
# The generated inputs are taken from what GIT TRACKS, not from a glob. Vivado writes its
# own droppings into the working directory — which is `generated/` — so a glob swept up
# vivado.log, vivado.jou and clockInfo.txt and the gate refused the run for naming files
# that are not sources. Asking git also keeps the provenance and the gate's rule ("every
# source equals its HEAD blob") consistent by construction rather than by an extension
# guess that would need updating whenever an input type is added.
set repo [file dirname [file dirname $here]]
set generated {}
if {![catch {exec git -C $repo ls-files vivado/carrier/generated} out]} {
    foreach rel [split [string trim $out] "\n"] {
        if {$rel ne ""} { lappend generated [file join $repo $rel] }
    }
}
set source_files {}
foreach f [concat $srcs [list $here/carrier.xdc $here/build_carrier.tcl \
                              $here/isolation_checks.tcl] [lsort $generated]] {
    lappend source_files $f
}
set source_json {}
foreach f $source_files {
    set rel [string range $f [expr {[string length $repo] + 1}] end]
    lappend source_json "    \"$rel\": \"[lindex [exec sha256sum $f] 0]\""
}
set source_commit "unknown"
if {![catch {exec git -C $repo rev-parse HEAD} out]} {
    set source_commit [string trim $out]
}
set source_dirty "unknown"
if {![catch {exec git -C $repo diff HEAD --name-only} out]} {
    set source_dirty [expr {[string trim $out] eq "" ? "clean" : "DIRTY"}]
}

set bit_sha [lindex [exec sha256sum $outdir/carrier.bit] 0]
set dcp_sha [lindex [exec sha256sum $outdir/post_route.dcp] 0]
set iso_sha [lindex [exec sha256sum $outdir/isolation.txt] 0]
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set fh [open $outdir/carrier_build.json w]
puts $fh "{"
puts $fh "  \"schema\": \"carrier_build\","
puts $fh "  \"schema_version\": \"1.0.0\","
puts $fh "  \"part\": \"$part\","
puts $fh "  \"top\": \"carrier_top\","
puts $fh "  \"vivado\": \"[version -short]\","
puts $fh "  \"routed\": true,"
puts $fh "  \"cell_isolation\": \"passed\","
puts $fh "  \"wns_ns\": $wns,"
puts $fh "  \"bitstream\": \"carrier.bit\","
puts $fh "  \"bitstream_sha256\": \"$bit_sha\","
puts $fh "  \"post_route_dcp_sha256\": \"$dcp_sha\","
puts $fh "  \"isolation_evidence_sha256\": \"$iso_sha\","
puts $fh "  \"source_commit\": \"$source_commit\","
puts $fh "  \"source_tree\": \"$source_dirty\","
puts $fh "  \"sources\": {"
puts $fh [join $source_json ",\n"]
puts $fh "  }"
puts $fh "}"
close $fh

puts "CARRIER BUILD OK -> $outdir/carrier.bit"
puts "  provenance -> $outdir/carrier_build.json (bitstream $bit_sha)"
