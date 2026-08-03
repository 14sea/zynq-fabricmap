# Build one clb_lutram specimen.
#
# Every mode is a different primitive, so unlike build_ff.tcl there is no one-P&R
# trick here: one invocation == one synth + place + route + bitstream.
#
# The readback block is the point of this script as much as the bitstream is. The
# ruling on round 9 requires that the tool freedoms this class exposes -- which
# SLICEM, which LUT BELs a multi-LUT primitive lands on, the resolved pin mapping,
# and the RAM/SRL mode Vivado actually chose -- are recorded from the routed design
# rather than assumed from what was requested.
#
#   vivado -mode batch -source build_lutram.tcl -tclargs <outdir> <site> <mode> [bel]
set outdir [lindex $argv 0]
set site   [lindex $argv 1]
set mode   [lindex $argv 2]
set bel    [lindex $argv 3]

set part xc7z010clg400-1
set here [file dirname [file normalize [info script]]]
file mkdir $outdir

create_project -in_memory -part $part
read_verilog $here/specimen_lutram.v
synth_design -top specimen_lutram -part $part -flatten_hierarchy none \
             -generic MODE=$mode

# 8 address bits + clk/we/d/o. Fixed pins so the IO ring is identical across modes
# and cannot itself be the thing that moved.
set apins {A20 B19 B20 C20 D18 D19 D20 E17}
for {set k 0} {$k < 8} {incr k} {
    set_property PACKAGE_PIN [lindex $apins $k] [get_ports a[$k]]
}
set_property PACKAGE_PIN E18 [get_ports clk]
set_property PACKAGE_PIN E19 [get_ports we]
set_property PACKAGE_PIN F16 [get_ports d]
set_property PACKAGE_PIN F17 [get_ports o]
set_property IOSTANDARD LVCMOS33 [get_ports *]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets -of_objects [get_pins bufg_inst/I]]

# LOC the target to the site under test.
#
# Picking the cells is where this script went wrong twice, both times silently:
#   * `IS_PRIMITIVE` alone returns the RAM64X1S MACRO *and* its RAMS64E child, so the
#     single-cell test below saw two cells, forced no BEL, and Vivado placed the RAM
#     on D6LUT while the baseline LUT6 sat on A6LUT -- a diff of two different LUTs.
#   * `PRIMITIVE_LEVEL == LEAF` then matched NOTHING: a macro's child reports
#     PRIMITIVE_LEVEL `INTERNAL`, not `LEAF` (LUT6 is LEAF, RAM64X1S is MACRO,
#     RAM64X1S/SP is INTERNAL). With no cells matched, no LOC was applied at all and
#     the specimen floated to wherever the placer liked -- and the build still exited
#     0 with a bitstream.
# So: everything that is not a MACRO and not an IO/clock buffer.
set cells [get_cells -hierarchical -filter {IS_PRIMITIVE && PRIMITIVE_LEVEL != "MACRO" && \
                                            REF_NAME != "BUFG" && \
                                            REF_NAME !~ "IBUF*" && REF_NAME !~ "OBUF*"}]
if {[llength $cells] == 0} { error "no target cells matched -- refusing to build an unconstrained specimen" }
foreach c $cells { set_property LOC $site $c }
# A BEL is only forced for the single-leaf modes: RAM128/RAM256 span several LUTs and
# forcing one would either fail or hide the placement freedom this specimen exposes.
#
# set_property BEL on a macro's INTERNAL child is a SILENT NO-OP. Probed directly:
# after `set_property LOC` alone, RAM64X1S/SP already reads SLICEM.D6LUT, and both
# `set_property BEL A6LUT` and the site-qualified form return without error and change
# nothing. The macro pins its own LUT. So the resolved BEL is compared with the
# request below and the mismatch is recorded rather than assumed away.
set bel_effective ""
if {$bel ne "" && [llength $cells] == 1} {
    set c0 [lindex $cells 0]
    catch {set_property BEL $bel $c0}
    if {[get_property REF_NAME $c0] eq "LUT6"} {
        set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $c0
    }
    set bel_effective [get_property BEL $c0]
    if {![string match "*$bel" $bel_effective]} {
        puts "SPECIMEN_WARN requested BEL $bel but cell reads $bel_effective -- constraint did not take"
    }
}

place_design
route_design
write_checkpoint -force $outdir/base.dcp
write_bitstream -force $outdir/spec_mode$mode.bit

# ---- readback: what the tool actually did ----------------------------------------
# Emitted as flat TAB-separated key/value lines rather than JSON: composing JSON in
# Tcl needs literal braces inside quoted strings, which the parser miscounts, and a
# half-written readback file is worse than none. scripts/lutram_readback.py turns
# this into placement.json.
set st [get_sites $site]
set fh [open $outdir/readback.tsv w]
proc kv {fh k v} { puts $fh "$k\t$v" }
kv $fh part $part
kv $fh vivado_version [version -short]
kv $fh mode $mode
kv $fh requested_site $site
kv $fh requested_bel $bel
kv $fh bel_after_constraint $bel_effective
kv $fh site_type [get_property SITE_TYPE $st]
kv $fh tile [get_tiles -of_objects $st]
kv $fh tile_type [get_property TYPE [get_tiles -of_objects $st]]
set n 0
foreach c $cells {
    kv $fh cell.$n.name      [get_property NAME $c]
    kv $fh cell.$n.ref       [get_property REF_NAME $c]
    kv $fh cell.$n.loc       [get_property LOC $c]
    kv $fh cell.$n.bel       [get_property BEL $c]
    kv $fh cell.$n.lock_pins [get_property -quiet LOCK_PINS $c]
    kv $fh cell.$n.init      [get_property -quiet INIT $c]
    foreach p [get_pins -of_objects $c] {
        kv $fh cell.$n.belpin.[lindex [split $p /] end] [get_bel_pins -quiet -of_objects $p]
    }
    incr n
}
# Every BEL of the site that ended up occupied -- the multi-LUT modes are the reason
# this is enumerated rather than derived from the requested BEL.
set n 0
foreach b [get_bels -of_objects $st] {
    set occ [get_cells -quiet -of_objects $b]
    if {$occ ne ""} {
        kv $fh occupied.$n.bel  $b
        kv $fh occupied.$n.cell [get_property NAME $occ]
        kv $fh occupied.$n.ref  [get_property REF_NAME $occ]
        incr n
    }
}
close $fh

puts "SPECIMEN_MODE $mode site=$site site_type=[get_property SITE_TYPE $st] tile=[get_tiles -of_objects $st]"
foreach c $cells {
    puts "SPECIMEN_CELL [get_property REF_NAME $c] loc=[get_property LOC $c] bel=[get_property BEL $c]"
}
puts "SPECIMEN_DONE"
