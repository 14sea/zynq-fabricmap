# Carrier design §4: prove frame ownership from the ROUTED design, not from constraints.
#
#   1. cell ownership  — exactly the six evolvable LUTs in the target columns, nothing at
#                        all in the flush columns
#   2. net ownership   — empty over the flush columns; over the target columns only the
#                        enumerated evolvable data nets
#   3. INIT differential — a POST-ROUTE ECO on the same routed DCP, never a re-route
#
# A pblock constrains placement; routing is free to cross a region no cell occupies, which
# is why check 2 exists and why it is asked of the routed design.

proc tiles_of {pattern} { return [get_tiles -quiet $pattern] }

# Cells are reached through SITES, not tiles. `get_cells -of_objects <tile>` returns
# nothing, which the first version read as "no cells here" — a check that answers "clean"
# when it is asking the wrong question is worse than no check, and this one reported the
# six evolvable LUTs missing from tiles they are demonstrably in
# (evolvable_0 LOC=SLICE_X2Y25 TILE=CLBLL_L_X2Y25).
proc cells_in {tiles} {
    set sites [get_sites -quiet -of_objects $tiles]
    if {![llength $sites]} { return {} }
    return [get_cells -quiet -of_objects $sites]
}

proc carrier_isolation_checks {outdir} {
    set problems {}

    set target_tiles [concat [tiles_of CLBLL_L_X2Y*] [tiles_of INT_L_X2Y*] \
                             [tiles_of CLBLM_L_X6Y*] [tiles_of INT_L_X6Y*]]
    set flush_tiles  [concat [tiles_of CLBLM_R_X3Y*] [tiles_of INT_R_X3Y*] \
                             [tiles_of DSP_R_X7Y*]   [tiles_of INT_R_X7Y*]]

    # ---- 1. cell ownership
    set flush_cells [cells_in $flush_tiles]
    if {[llength $flush_cells]} {
        lappend problems "flush columns hold [llength $flush_cells] cell(s): $flush_cells"
    }
    set target_cells [cells_in $target_tiles]
    set expected {evolvable_0 evolvable_1 evolvable_2 evolvable_3 evolvable_4 evolvable_5}
    foreach c $target_cells {
        if {[lsearch -exact $expected [get_property NAME $c]] < 0} {
            lappend problems "unexpected cell in a target column: [get_property NAME $c]"
        }
    }
    if {[llength $target_cells] != 6} {
        lappend problems "target columns hold [llength $target_cells] cells, expected 6"
    }

    # ---- 2. net ownership
    set flush_nets [get_nets -quiet -of_objects $flush_tiles]
    if {[llength $flush_nets]} {
        lappend problems "flush columns carry [llength $flush_nets] net(s): $flush_nets"
    }
    set allow {}
    foreach c $expected {
        foreach p [get_pins -quiet -of_objects [get_cells -quiet $c]] {
            set n [get_nets -quiet -of_objects $p]
            if {[llength $n]} { lappend allow [get_property NAME $n] }
        }
    }
    set allow [lsort -unique $allow]
    foreach n [get_nets -quiet -of_objects $target_tiles] {
        if {[lsearch -exact $allow [get_property NAME $n]] < 0} {
            lappend problems "net crosses a target column but is not an evolvable data net: [get_property NAME $n]"
        }
    }

    set fh [open $outdir/isolation.txt w]
    puts $fh "allowed evolvable data nets:"
    foreach n $allow { puts $fh "  $n" }
    puts $fh "target cells: [llength $target_cells]  flush cells: [llength $flush_cells]"
    puts $fh "flush nets:   [llength $flush_nets]"
    if {[llength $problems]} {
        puts $fh "PROBLEMS:"
        foreach p $problems { puts $fh "  $p" }
    } else {
        puts $fh "NO PROBLEMS"
    }
    close $fh

    if {[llength $problems]} {
        foreach p $problems { puts "ISOLATION PROBLEM: $p" }
        error "isolation checks failed: [llength $problems] problem(s)"
    }
    puts "ISOLATION CHECKS OK ([llength $allow] evolvable data nets)"
}
