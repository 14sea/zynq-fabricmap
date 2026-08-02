# Build one specimen family: a single LUT6 pinned to a site, written out once per
# INIT variant.
#
# The variants come from ONE placed-and-routed design: place/route runs once, then
# each variant only sets the cell's INIT property and re-writes the bitstream.  That
# is what makes the diff attributable — re-running placement per variant would let
# unrelated bits move and the "isolated single-feature diff" would be a fiction.
#
#   vivado -mode batch -source build_specimen.tcl -tclargs <outdir> <site> <bel> <init>...
set outdir [lindex $argv 0]
set site   [lindex $argv 1]
set bel    [lindex $argv 2]
set inits  [lrange $argv 3 end]

set part xc7z010clg400-1
set here [file dirname [file normalize [info script]]]
file mkdir $outdir

create_project -in_memory -part $part
read_verilog $here/specimen_lut.v
synth_design -top specimen_lut -part $part -flatten_hierarchy none

# IOs: fixed package pins so nothing about them varies between runs.
set pins {N17 N18 N20 P14 P15 P16}
for {set k 0} {$k < 6} {incr k} {
    set_property PACKAGE_PIN [lindex $pins $k] [get_ports i[$k]]
}
set_property PACKAGE_PIN P18 [get_ports o]
set_property IOSTANDARD LVCMOS33 [get_ports *]

set cell [get_cells target]
if {[llength $cell] != 1} { error "expected exactly one 'target' cell, got: $cell" }
set_property LOC $site $cell
set_property BEL $bel  $cell

# LUT input pin swapping is a standard Vivado optimisation: it permutes I0..I5 onto
# the physical A1..A6 inputs and rewrites INIT to match.  Without LOCK_PINS the
# logical INIT bit index no longer equals the physical truth-table index, so a
# single-bit prediction is wrong for every entry except all-zeros and all-ones (the
# two that are invariant under any input permutation).  Measured on this exact
# design: logical INIT bit 1 landed on the db's INIT[04].
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $cell

place_design
route_design
write_checkpoint -force $outdir/base.dcp

# Report where the tool actually put it — the harness must never assume this.
set placed [get_property LOC  $cell]
set pbel   [get_property BEL  $cell]
puts "SPECIMEN_PLACEMENT site=$placed bel=$pbel"
puts "SPECIMEN_TILE [get_tiles -of_objects [get_sites $site]]"
foreach pin {I0 I1 I2 I3 I4 I5} {
    puts "SPECIMEN_PINMAP $pin -> [get_property BEL_PIN [get_pins target/$pin]]"
}

foreach init $inits {
    set_property INIT 64'h$init $cell
    set bit $outdir/spec_$init.bit
    write_bitstream -force $bit
    puts "SPECIMEN_VARIANT init=$init bit=$bit"
}
puts "SPECIMEN_DONE"
