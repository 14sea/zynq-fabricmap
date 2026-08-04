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

# Pin the target cells. `LOCK_PINS` on every LUT for the reason `docs/mux_groups.md`
# records: Vivado permutes I0..I5 onto A1..A6 and rewrites INIT, so without it the LUT
# content bits are not where the frozen rule says they are.
#
# Cells are selected by REF_NAME and a name glob rather than by their generate-block
# paths: those paths contain square brackets, which are Tcl command substitution AND
# glob metacharacters, and getting that escaping subtly wrong is a silent no-op — the
# same failure mode build_lutram.tcl hit twice.
set lut_bels   {A6LUT B6LUT C6LUT D6LUT A5LUT B5LUT C5LUT D5LUT}
set store_bels {AFF A5FF BFF B5FF CFF C5FF DFF D5FF}

if {$mode <= 3} {
    # `target_lut` now lives inside a generate block, so it must be found by glob
    # rather than by bare name — the same "matched nothing, constrained nothing,
    # exited 0" failure build_lutram.tcl records twice.
    set luts   [get_cells -hierarchical -filter {NAME =~ "*target_lut"}]
    if {[llength $luts] != 1} { error "expected one target LUT, got [llength $luts]" }
    set stores [get_cells -hierarchical -filter {NAME =~ "*storage" && IS_PRIMITIVE && \
                                                 PRIMITIVE_LEVEL != "MACRO"}]
    if {[llength $stores] != 1} { error "expected one storage cell, got [llength $stores]" }
    set store_bels [list $bel]
} else {
    # x6LUT group first, then x5LUT group, matching $lut_bels.
    set luts [concat [lsort [get_cells -hierarchical -filter {NAME =~ "*g_hi*" && IS_PRIMITIVE}]] \
                     [lsort [get_cells -hierarchical -filter {NAME =~ "*g_lo*" && IS_PRIMITIVE}]]]
    set stores [lsort [get_cells -hierarchical -filter {NAME =~ "*g_store*" && IS_PRIMITIVE}]]
    if {[llength $luts] != 8} { error "expected 8 LUT5, got [llength $luts]" }
    set want [expr {$mode < 6 ? 8 : 4}]
    if {[llength $stores] != $want} {
        error "expected $want storage cells, got [llength $stores]"
    }
    # The 4-element modes occupy the four MAIN storage elements. The 5FF BELs are type
    # FF_INIT and Vivado refuses to place an LDCE on one, so a "first four" BEL list
    # would ask for A5FF and fail for a reason that has nothing to do with the question.
    if {$want == 4} { set store_bels {AFF BFF CFF DFF} }
}

# BEL before LOC: with LOC first Vivado picks a BEL itself and the next cell then
# collides with that choice ("bel is occupied"), which is how this script failed the
# first time the full-slice modes were built.
set k 0
foreach c $luts {
    set_property BEL [lindex $lut_bels $k] $c
    set_property LOC $site $c
    if {[get_property REF_NAME $c] eq "LUT6"} {
        set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $c
    } else {
        set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5} $c
    }
    incr k
}
set k 0
set bel_effective ""
foreach c $stores {
    set want_bel [lindex $store_bels $k]
    catch {set_property BEL $want_bel $c}
    set_property LOC $site $c
    set got [get_property BEL $c]
    if {![string match "*$want_bel" $got]} {
        puts "SPECIMEN_WARN requested BEL $want_bel but cell reads $got -- constraint did not take"
    }
    if {$k == 0} { set bel_effective $got }
    incr k
}
set lut  [lindex $luts 0]
set cell [lindex $stores 0]

# The Q-reduction LUTs of the full-slice modes go into the anchor tile, so the reduction
# is bit-identical between the two endpoints of a pair and contributes nothing to it.
if {$mode > 3} {
    set r1 [get_cells -hierarchical -filter {NAME =~ "*q_reduce1"}]
    set r2 [get_cells -hierarchical -filter {NAME =~ "*q_reduce2"}]
    set_property LOC $asite $r1
    set_property BEL C6LUT  $r1
    set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $r1
    set_property LOC $asite $r2
    set_property BEL D6LUT  $r2
    set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} $r2
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
kv $fh storage_count [llength $stores]
kv $fh lut_count [llength $luts]
kv $fh storage_ref [get_property REF_NAME $cell]
kv $fh storage_loc [get_property LOC $cell]
kv $fh storage_bel [get_property BEL $cell]
kv $fh storage_init [get_property -quiet INIT $cell]
# Every storage element, not just the first: on the full-slice modes the question is
# what the whole slice did, and a per-cell record is what makes "all eight landed where
# they were asked to" checkable instead of assumed.
set n 0
foreach c $stores {
    kv $fh store.$n.name [get_property NAME $c]
    kv $fh store.$n.ref  [get_property REF_NAME $c]
    kv $fh store.$n.loc  [get_property LOC $c]
    kv $fh store.$n.bel  [get_property BEL $c]
    kv $fh store.$n.init [get_property -quiet INIT $c]
    incr n
}
set n 0
foreach c $luts {
    kv $fh lut.$n.name [get_property NAME $c]
    kv $fh lut.$n.ref  [get_property REF_NAME $c]
    kv $fh lut.$n.loc  [get_property LOC $c]
    kv $fh lut.$n.bel  [get_property BEL $c]
    incr n
}
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
