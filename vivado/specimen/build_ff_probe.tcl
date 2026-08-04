# Build one `specimen_ff_probe` mode. Exploration for the LATCH question only.
#
# One invocation == one synth + place + route + bitstream: LDCE and FDCE are different
# primitives, so there is no one-P&R trick here (that trick exists only for INIT, which
# is a cell property).
#
# The readback block matters as much as the bitstream. The plan's LATCH risk is about
# what ELSE moves when the storage kind changes, so the record has to show what Vivado
# actually built — resolved LOC/BEL, the control-pin connections it made, and which BELs
# of the site ended up occupied — rather than what the recipe asked for.
#
#   vivado -mode batch -source build_ff_probe.tcl -tclargs <outdir> <site> <mode> [bel] [anchor] [asite] [asite2]
set outdir [lindex $argv 0]
set site   [lindex $argv 1]
set mode   [lindex $argv 2]
set bel    [lindex $argv 3]
set anchor [lindex $argv 4]
set asite  [lindex $argv 5]
set asite2 [lindex $argv 6]
if {$bel    eq ""} { set bel AFF }
if {$anchor eq ""} { set anchor 1 }
if {$asite  eq ""} { set asite SLICE_X4Y20 }
if {$asite2 eq ""} { set asite2 SLICE_X2Y20 }

set part xc7z010clg400-1
set here [file dirname [file normalize [info script]]]
file mkdir $outdir

create_project -in_memory -part $part
read_verilog $here/specimen_ff_probe.v
synth_design -top specimen_ff_probe -part $part -flatten_hierarchy none \
             -generic MODE=$mode -generic ANCHOR=$anchor

# Fixed pins, so the IO ring is identical across modes and cannot itself be what moved.
set ipins {A20 B19 B20 C20 D18 D19}
for {set k 0} {$k < 6} {incr k} {
    set_property PACKAGE_PIN [lindex $ipins $k] [get_ports i[$k]]
}
set_property PACKAGE_PIN E18 [get_ports clk]
set_property PACKAGE_PIN E19 [get_ports ce]
set_property PACKAGE_PIN F16 [get_ports rst]
set_property PACKAGE_PIN F17 [get_ports o]
set_property PACKAGE_PIN D20 [get_ports q]
set_property PACKAGE_PIN F19 [get_ports anchor_o]
set_property PACKAGE_PIN F20 [get_ports anchor_o2]
set_property IOSTANDARD LVCMOS33 [get_ports *]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets -of_objects [get_pins bufg_inst/I]]

# Anchors pinned to fixed BELs in other tiles, so they are bit-identical in every mode.
if {$anchor} {
    set_property LOC $asite [get_cells g_anchor.anchor_lut1]
    set_property BEL A6LUT  [get_cells g_anchor.anchor_lut1]
    set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells g_anchor.anchor_lut1]
    set_property LOC $asite [get_cells g_anchor.anchor_lut2]
    set_property BEL B6LUT  [get_cells g_anchor.anchor_lut2]
    set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells g_anchor.anchor_lut2]
    set_property LOC $asite [get_cells g_anchor.anchor_ff]
    set_property BEL AFF    [get_cells g_anchor.anchor_ff]
    set_property LOC $asite2 [get_cells g_anchor.anchor_ff2]
    set_property BEL AFF     [get_cells g_anchor.anchor_ff2]
}

# The target LUT and the storage element, both pinned. `LOCK_PINS` on the LUT for the
# reason `docs/mux_groups.md` records: Vivado permutes I0..I5 onto A1..A6 and rewrites
# INIT, so without it the LUT content bits are not where the frozen rule says.
set lut [get_cells target_lut]
set_property LOC $site $lut
set_property BEL A6LUT $lut
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $lut

set cell [get_cells -hierarchical -filter {NAME =~ "*storage" && IS_PRIMITIVE && \
                                           PRIMITIVE_LEVEL != "MACRO"}]
if {[llength $cell] != 1} { error "expected exactly one storage cell, got [llength $cell]" }
set_property LOC $site $cell
catch {set_property BEL $bel $cell}
set bel_effective [get_property BEL $cell]
if {![string match "*$bel" $bel_effective]} {
    puts "SPECIMEN_WARN requested BEL $bel but cell reads $bel_effective -- constraint did not take"
}

place_design
route_design
write_checkpoint -force $outdir/base.dcp
write_bitstream -force $outdir/spec.bit

# ---- readback: what the tool actually did ----------------------------------------
# Flat TAB-separated key/value, not JSON: composing JSON in Tcl breaks on brace
# counting, and a half-written readback file is worse than none.
set st [get_sites $site]
set fh [open $outdir/readback.tsv w]
proc kv {fh k v} { puts $fh "$k\t$v" }
kv $fh part $part
kv $fh vivado_version [version -short]
kv $fh mode $mode
kv $fh requested_site $site
kv $fh requested_bel $bel
kv $fh bel_after_constraint $bel_effective
kv $fh anchor $anchor
kv $fh anchor_site $asite
kv $fh anchor_site2 $asite2
kv $fh site_type [get_property SITE_TYPE $st]
kv $fh tile [get_tiles -of_objects $st]
kv $fh tile_type [get_property TYPE [get_tiles -of_objects $st]]
kv $fh storage_ref [get_property REF_NAME $cell]
kv $fh storage_loc [get_property LOC $cell]
kv $fh storage_bel [get_property BEL $cell]
kv $fh storage_init [get_property -quiet INIT $cell]
# Pin-inversion properties are the control modes this class encodes, so they are read
# back rather than inferred from the primitive name: a latch that arrives with its gate
# inverted and a flip-flop that does not are two different control-set configurations,
# and the diff cannot tell that apart from the storage kind on its own.
foreach prop {IS_C_INVERTED IS_G_INVERTED IS_CLR_INVERTED IS_R_INVERTED \
              IS_CE_INVERTED IS_GE_INVERTED IS_D_INVERTED} {
    kv $fh storage_prop.$prop [get_property -quiet $prop $cell]
}
kv $fh lut_loc [get_property LOC $lut]
kv $fh lut_bel [get_property BEL $lut]
kv $fh lut_lock_pins [get_property -quiet LOCK_PINS $lut]

# The control modes this probe exists to compare. Each control pin is reported with the
# net that drives it, so "CE is really driven" is evidence rather than a recipe claim.
foreach pin [get_pins -of_objects $cell] {
    set leaf [lindex [split $pin /] end]
    set net [get_nets -quiet -of_objects $pin]
    kv $fh pin.$leaf.net $net
    kv $fh pin.$leaf.belpin [get_bel_pins -quiet -of_objects $pin]
    kv $fh pin.$leaf.route_status [get_property -quiet ROUTE_STATUS $net]
}

# Every BEL of the site that ended up occupied: if a mode pulls in a cell the other does
# not, that is a structural difference the diff would otherwise be blamed for.
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
# Anchors read back too: an anchor that silently moved between modes would reintroduce
# the structural variation it exists to remove, and the diff could not tell that apart
# from the mode change under test.
set n 0
if {$anchor} {
    foreach ac [get_cells -hierarchical -filter {NAME =~ "g_anchor*" && IS_PRIMITIVE}] {
        kv $fh anchor.$n.name [get_property NAME $ac]
        kv $fh anchor.$n.ref  [get_property REF_NAME $ac]
        kv $fh anchor.$n.loc  [get_property LOC $ac]
        kv $fh anchor.$n.bel  [get_property BEL $ac]
        incr n
    }
}
# Route status records COMPLETION only. Two builds can both say ROUTED over entirely
# different paths, so this does not establish that routing matched between modes.
set n 0
foreach net [get_nets -hierarchical] {
    kv $fh net.$n.name         [get_property NAME $net]
    kv $fh net.$n.route_status [get_property -quiet ROUTE_STATUS $net]
    incr n
}
close $fh

puts "SPECIMEN_MODE $mode site=$site ref=[get_property REF_NAME $cell] bel=[get_property BEL $cell]"
puts "SPECIMEN_DONE"
