# Produce one derived `zini_*` specimen from `base`'s routed checkpoint.
#
#   vivado -mode batch -source derive_ff_formal.tcl \
#          -tclargs <outdir> <base.dcp> <site> <asite> <asite2> <variant> <idx> <bel>
#
# `INIT` on a flip-flop is a cell property, so this is one place-and-route serving nine
# bitstreams (design §2.1). `place_design` and `route_design` are NOT run and the source
# checkpoint is NOT modified — the changed state is written to its own `derived.dcp`, so
# the design state the attestation describes exists on disk instead of only in principle.
#
# What is deliberately NOT checked here is whether the resulting bitstream differs from
# base's in the predicted bit. That is the measurement, it is pre-registered, and a
# builder that checked it would be scoring its own work.

set outdir  [lindex $argv 0]
set basedcp [lindex $argv 1]
set site    [lindex $argv 2]
set asite   [lindex $argv 3]
set asite2  [lindex $argv 4]
set variant [lindex $argv 5]
set idx     [lindex $argv 6]
set wantbel [lindex $argv 7]

set part xc7z010clg400-1
set here [file dirname [file normalize [info script]]]
source $here/ff_formal_readback.tcl
file mkdir $outdir

open_checkpoint $basedcp

# Storage cells are selected as a sorted list and indexed, never by a name containing
# square brackets: brackets are Tcl command substitution AND glob metacharacters, and
# getting that escaping subtly wrong is a silent no-op that exits 0.
set stores [lsort [get_cells -hierarchical -filter {NAME =~ "*g_store*" && IS_PRIMITIVE \
                                                    && PRIMITIVE_LEVEL != "MACRO"}]]
if {[llength $stores] != 8} {
    error "expected 8 storage cells in the base checkpoint, got [llength $stores]"
}
set c [lindex $stores $idx]

# The index-to-flip-flop mapping is asserted, not trusted: if lsort order and BEL order
# ever disagreed, every zini specimen would silently change the wrong flip-flop and each
# one would still build and still look correct.
set got_bel [get_property BEL $c]
if {![string match "*/$wantbel" $got_bel] && ![string match "*$wantbel" $got_bel]} {
    error "$variant: index $idx resolved to BEL $got_bel, expected $wantbel"
}
set before [get_property INIT $c]
if {$before ne "1'b1"} {
    error "$variant: expected base INIT 1'b1 on [get_property NAME $c], found $before"
}

set_property INIT 1'b0 $c

set after [get_property INIT $c]
if {$after ne "1'b0"} { error "$variant: INIT did not take, reads $after" }

write_checkpoint -force $outdir/derived.dcp
write_bitstream -force $outdir/spec.bit

emit_readback $outdir $site $asite $asite2 $part $variant derived $idx

puts "SPECIMEN_VARIANT $variant site=$site cell=[get_property NAME $c] bel=$got_bel init=$before->$after"
puts "SPECIMEN_DONE"
