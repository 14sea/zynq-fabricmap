# PROBE ONLY — sacrificial site, deliberate congestion.
#
# The mine instance cannot exhibit the routing freedom that failed T2 at `SLICE_X25Y25`:
# its nine dedicated nets take one route under every variant and every router directive.
# This probe therefore moves to a NON-COMMITTED site of the same geometry and creates the
# congestion itself, so the failure class can be reproduced and then shown to be removed.
#
#   vivado -mode batch -source probe_congest.tcl -tclargs \
#          <outdir> <site> <asite> <asite2> <variant> <mode> <idx> <flow> <directive> \
#          <congest> <congest_sites>
#
# congest       : how many DONT_TOUCH LUT6 cells to add as routing demand
# congest_sites : space-separated SLICE sites to place them in (checked by the driver to
#                 be non-committed)
#
# The specimen source is read UNMODIFIED. Congestion is added to the synthesized netlist
# here, so nothing about the specimen's own cells or its nine dedicated nets changes —
# only the demand on the interconnect around them.

set outdir      [lindex $argv 0]
set site        [lindex $argv 1]
set asite       [lindex $argv 2]
set asite2      [lindex $argv 3]
set variant     [lindex $argv 4]
set mode        [lindex $argv 5]
set idx         [lindex $argv 6]
set flow        [lindex $argv 7]
set directive   [lindex $argv 8]
set congest     [lindex $argv 9]
set csites      [lindex $argv 10]

set part xc7z010clg400-1
set spec [file normalize [file dirname [info script]]/../../specimen]
source $spec/ff_formal_readback.tcl
file mkdir $outdir

set dedicated {w1 w2 qr1 q_OBUF anchor_o_OBUF anchor_o2_OBUF q anchor_o anchor_o2}

proc pick {pattern want {extra ""}} {
    set filter "NAME =~ \"$pattern\""
    if {$extra ne ""} { set filter "$filter && $extra" }
    set cells [get_cells -hierarchical -filter $filter]
    if {[llength $cells] != $want} {
        error "expected $want cells matching $pattern, got [llength $cells]: $cells"
    }
    return $cells
}

proc snap {fh tag nets} {
    foreach name $nets {
        set n [get_nets -quiet $name]
        if {$n eq ""} { error "dedicated net $name does not exist" }
        set drv [get_pins -quiet -of_objects $n -filter {DIRECTION == OUT}]
        set snk [lsort [get_pins -quiet -of_objects $n -filter {DIRECTION == IN}]]
        puts $fh "$tag.$name.route\t[get_property -quiet ROUTE $n]"
        puts $fh "$tag.$name.pips\t[lsort [get_pips -quiet -of_objects $n]]"
        puts $fh "$tag.$name.status\t[get_property -quiet ROUTE_STATUS $n]"
        puts $fh "$tag.$name.fixed\t[get_property -quiet IS_ROUTE_FIXED $n]"
        puts $fh "$tag.$name.driver\t$drv"
        puts $fh "$tag.$name.sinks\t$snk"
    }
}

create_project -in_memory -part $part
read_verilog $spec/specimen_ff_formal.v
synth_design -top specimen_ff_formal -part $part -flatten_hierarchy none \
             -generic MODE=$mode -generic IDX=$idx

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
    if {![string match "*/$want_bel" $got] && ![string match "*$want_bel" $got]} {
        error "cell [get_property NAME $c]: requested BEL $want_bel, resolved to $got"
    }
    incr k
}

# ---- congestion ------------------------------------------------------------------
# Added to the synthesized netlist, never to the specimen source. Each cell pulls all six
# input nets into a slice near the anchor, so the switchboxes the dedicated nets pass
# through carry real demand. Outputs are left dangling on purpose: DONT_TOUCH keeps the
# cells, and an unloaded output adds no further nets to route.
set cbels {A6LUT B6LUT C6LUT D6LUT}
set placed 0
for {set c 0} {$c < $congest} {incr c} {
    set target_site [lindex $csites [expr {$c / [llength $cbels]}]]
    set target_bel  [lindex $cbels   [expr {$c % [llength $cbels]}]]
    if {$target_site eq ""} { error "ran out of congestion sites at cell $c" }
    set cell [create_cell -reference LUT6 cong_$c]
    set_property INIT 64'h6996966996696996 $cell
    set_property DONT_TOUCH TRUE $cell
    for {set k 0} {$k < 6} {incr k} {
        connect_net -net [get_nets i_IBUF[$k]] -objects [get_pins cong_$c/I$k]
    }
    set_property BEL $target_bel $cell
    set_property LOC $target_site $cell
    incr placed
}
puts "PROBE_CONGEST placed=$placed requested=$congest"

place_design

set fh [open $outdir/probe_routes.tsv w]
puts $fh "flow\t$flow"
puts $fh "directive\t$directive"
puts $fh "variant\t$variant"
puts $fh "site\t$site"
puts $fh "congest\t$congest"
puts $fh "congest_placed\t$placed"

if {$flow eq "pinned"} {
    set nets [get_nets $dedicated]
    if {[llength $nets] != [llength $dedicated]} {
        error "expected [llength $dedicated] dedicated nets, got [llength $nets]"
    }
    route_design -nets $nets
    snap $fh "first_pass" $dedicated
    set_property IS_ROUTE_FIXED 1 $nets
    route_design -directive $directive
} else {
    route_design -directive $directive
    snap $fh "first_pass" $dedicated
}

snap $fh "final" $dedicated
close $fh

write_checkpoint -force $outdir/base.dcp
emit_readback $outdir $site $asite $asite2 $part $variant $mode $idx

puts "PROBE_VARIANT $variant flow=$flow directive=$directive congest=$congest"
puts "PROBE_DONE"
