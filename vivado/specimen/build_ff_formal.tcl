# Build one formal `clb_ff_config` implementation node: synth + place + route +
# checkpoint + bitstream + readback. One invocation == one place-and-route.
#
#   vivado -mode batch -source build_ff_formal.tcl \
#          -tclargs <outdir> <site> <asite> <asite2> <variant> <mode> <idx>
#
# Every `get_cells` here goes through `pick`, which takes the expected count and errors
# out unless exactly that many cells matched. There is no `catch` that continues and no
# warn-and-proceed path: Vivado has silently built the wrong thing and exited 0 three
# times in this repo (a macro child that took no LOC, a `set_property BEL` no-op on a
# macro, a cell moved into a generate block that a bare name stopped matching).

set outdir  [lindex $argv 0]
set site    [lindex $argv 1]
set asite   [lindex $argv 2]
set asite2  [lindex $argv 3]
set variant [lindex $argv 4]
set mode    [lindex $argv 5]
set idx     [lindex $argv 6]

set part xc7z010clg400-1
set here [file dirname [file normalize [info script]]]
source $here/ff_formal_readback.tcl
file mkdir $outdir

proc pick {pattern want {extra ""}} {
    set filter "NAME =~ \"$pattern\""
    if {$extra ne ""} { set filter "$filter && $extra" }
    set cells [get_cells -hierarchical -filter $filter]
    if {[llength $cells] != $want} {
        error "expected $want cells matching $pattern, got [llength $cells]: $cells"
    }
    return $cells
}

create_project -in_memory -part $part
read_verilog $here/specimen_ff_formal.v
synth_design -top specimen_ff_formal -part $part -flatten_hierarchy none \
             -generic MODE=$mode -generic IDX=$idx

# Fixed pins, identical in every variant. This eliminates one CAUSE of IO-ring movement
# (differing port sets trimming different IBUFs); it does not establish that the IO ring
# was implemented identically.
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

# ---- anchors and keeper -------------------------------------------------------------
# BEL before LOC everywhere: with LOC first the placer picks a BEL itself and the next
# cell collides with that choice ("bel is occupied").
set lock6 {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6}
set lock5 {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5}

foreach {name bel where} [list \
        anchor_lut1 A6LUT $asite \
        anchor_lut2 B6LUT $asite \
        q_reduce1   C6LUT $asite \
        q_reduce2   D6LUT $asite \
        anchor_ff   AFF   $asite \
        anchor_ff2  AFF   $asite2] {
    set c [pick $name 1]
    set_property BEL $bel $c
    set_property LOC $where $c
    if {[get_property REF_NAME $c] eq "LUT6"} { set_property LOCK_PINS $lock6 $c }
}

# ---- target cells --------------------------------------------------------------------
# `LOCK_PINS` on every LUT: Vivado permutes I0..I5 onto A1..A6 and rewrites INIT, so
# without it the LUT content bits are not where the frozen rule says they are.
set lut_bels {A6LUT B6LUT C6LUT D6LUT A5LUT B5LUT C5LUT D5LUT}
set luts [concat [lsort [pick "*g_hi*" 4 {IS_PRIMITIVE}]] \
                 [lsort [pick "*g_lo*" 4 {IS_PRIMITIVE}]]]
set k 0
foreach c $luts {
    set_property BEL [lindex $lut_bels $k] $c
    set_property LOC $site $c
    set_property LOCK_PINS $lock5 $c
    incr k
}

# Four-element variants occupy the four MAIN storage elements. The 5FF BELs are type
# FF_INIT and Vivado refuses an LDCE on one, so a "first four" BEL list would fail for a
# reason that has nothing to do with the question being asked.
if {$mode == 5 || $mode == 6} {
    set want 4
    set store_bels {AFF BFF CFF DFF}
} else {
    set want 8
    set store_bels {AFF A5FF BFF B5FF CFF C5FF DFF D5FF}
}
set stores [lsort [pick "*g_store*" $want {IS_PRIMITIVE && PRIMITIVE_LEVEL != "MACRO"}]]
set k 0
foreach c $stores {
    set want_bel [lindex $store_bels $k]
    set_property BEL $want_bel $c
    set_property LOC $site $c
    set got [get_property BEL $c]
    # Requested-versus-resolved is a HARD failure. The freeze says a site exists and is
    # not prohibited; whether it can host this cell is Vivado's answer, and it is read
    # back rather than assumed.
    if {![string match "*/$want_bel" $got] && ![string match "*$want_bel" $got]} {
        error "cell [get_property NAME $c]: requested BEL $want_bel, resolved to $got"
    }
    incr k
}

place_design

# ---- route pinning -------------------------------------------------------------------
# Two specimens of one committed pair differ in the target slice and nowhere else, yet on
# 2026-08-06 the router answered the surrounding congestion differently and put `w1` on
# another path, failing T2 at SLICE_X25Y25. The dedicated nets are therefore routed FIRST,
# into a fabric where nothing else is routed — their endpoints are fully constrained and
# identical in every variant, so the target's contents cannot present as congestion —
# and then frozen. Reproduced and removed on a non-committed site of the same geometry in
# `evidence/ff_route_pin_sacrificial_2026_08_06/`; whether it repairs SLICE_X25Y25 is a
# question only a full run can answer.
set expect_dedicated {w1 w2 qr1 q_OBUF anchor_o_OBUF anchor_o2_OBUF q anchor_o anchor_o2}
set dedicated [require_dedicated $expect_dedicated]

# Three of the nine are pad nets with no interconnect route at all — Vivado skips them as
# intrasite. Routing is attempted for the six that have a route; the other three are read
# back and REQUIRED to be intrasite, so "not routed" is asserted rather than assumed.
set routable {}
set intrasite {}
foreach name $dedicated {
    set n [get_nets $name]
    if {[get_property -quiet ROUTE_STATUS $n] eq "INTRASITE"} {
        lappend intrasite $name
    } else {
        lappend routable $name
    }
}
route_design -nets [get_nets $routable]
foreach name $intrasite {
    set st [get_property -quiet ROUTE_STATUS [get_nets $name]]
    if {$st ne "INTRASITE"} { error "$name was expected to stay intrasite, reads $st" }
}
set_property IS_ROUTE_FIXED 1 [get_nets $routable]
foreach name $routable {
    set fx [get_property -quiet IS_ROUTE_FIXED [get_nets $name]]
    if {$fx ne "1"} { error "$name did not take IS_ROUTE_FIXED, reads '$fx'" }
}

routepin_capture_first $dedicated $routable $intrasite

route_design

write_checkpoint -force $outdir/base.dcp
write_bitstream -force $outdir/spec.bit

emit_readback $outdir $site $asite $asite2 $part $variant $mode $idx

puts "SPECIMEN_VARIANT $variant site=$site storage=[llength $stores] luts=[llength $luts]"
puts "SPECIMEN_DONE"
