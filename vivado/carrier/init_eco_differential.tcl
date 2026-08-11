# Carrier design §4 check 3 — the INIT differential, as a POST-ROUTE ECO.
#
#   vivado -mode batch -source init_eco_differential.tcl -tclargs <outdir> <cell> <init_hex>
#
# Open the ROUTED checkpoint, change one evolvable LUT's INIT, write the bitstream. No
# re-synthesis, no re-placement, no re-routing. Re-running implementation for the variant
# would make the comparison worthless: the router is free to produce a different result, so
# a clean diff would prove nothing and a dirty one could not distinguish an INIT effect from
# a routing change. This is exactly how the `clb_ff_config` line's specimens were derived,
# and the frame-ECC known answers in scripts/frame_ecc.py were validated against those pairs.
#
# This script only PRODUCES the variant. The verdict is host-side, in
# scripts/gate_init_eco.py, which compares frames bit for bit — the same authority erratum
# 001 moved everything else to.

set outdir   [lindex $argv 0]
set cellname [lindex $argv 1]
set initval  [lindex $argv 2]

if {$outdir eq "" || $cellname eq "" || $initval eq ""} {
    error "usage: -tclargs <outdir> <cell> <init_hex e.g. 64'hDEAD...>"
}

open_checkpoint $outdir/post_route.dcp

set cell [get_cells -quiet $cellname]
if {[llength $cell] != 1} {
    error "expected exactly 1 cell named $cellname, got [llength $cell]"
}
# A cell that is not where the map says it is would make the differential meaningless.
set loc [get_property LOC $cell]
set bel [get_property BEL $cell]
set before [get_property INIT $cell]
puts "ECO: $cellname LOC=$loc BEL=$bel INIT $before -> $initval"

if {$before eq $initval} {
    error "the ECO INIT equals the base INIT: the differential would be vacuously empty"
}

# The routing must be untouched, and "untouched" is checked as an INVARIANT measured on
# this design rather than against an allowlist of status values guessed at in advance. The
# first version filtered for `ROUTE_STATUS != ROUTED` and flagged 518 perfectly healthy
# nets: a routed carrier_top also has INTRASITE (482) and NOLOADS (36) nets.
proc route_census {} {
    array set c {}
    foreach n [get_nets -hierarchical] {
        set s [get_property ROUTE_STATUS $n]
        if {[info exists c($s)]} { incr c($s) } else { set c($s) 1 }
    }
    set out {}
    foreach s [lsort [array names c]] { lappend out "$s=$c($s)" }
    return [join $out " "]
}

set census_before [route_census]
set_property INIT $initval $cell
set census_after [route_census]
puts "ECO: route census before: $census_before"
puts "ECO: route census after:  $census_after"
if {$census_before ne $census_after} {
    error "the ECO changed the routing census ($census_before -> $census_after): a\
 differential taken across a re-route proves nothing"
}

write_bitstream -force $outdir/carrier_eco.bit

set bit_sha [lindex [exec sha256sum $outdir/carrier_eco.bit] 0]
set fh [open $outdir/carrier_eco.json w]
puts $fh "{"
puts $fh "  \"schema\": \"carrier_eco\","
puts $fh "  \"schema_version\": \"1.0.0\","
puts $fh "  \"cell\": \"$cellname\","
puts $fh "  \"loc\": \"$loc\","
puts $fh "  \"bel\": \"$bel\","
puts $fh "  \"init_before\": \"$before\","
puts $fh "  \"init_after\": \"$initval\","
puts $fh "  \"reimplemented\": false,"
puts $fh "  \"bitstream\": \"carrier_eco.bit\","
puts $fh "  \"bitstream_sha256\": \"$bit_sha\""
puts $fh "}"
close $fh

puts "ECO BITSTREAM OK -> $outdir/carrier_eco.bit ($bit_sha)"
