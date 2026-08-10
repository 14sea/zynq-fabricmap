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

# POSITIVE CONTROL. A query that returns nothing answers "clean" for both a clean design
# and a broken question — which is exactly how the first version reported the six
# evolvable LUTs missing from tiles they are in. Before judging anything, the checker must
# SEE what it knows is there; if it cannot, it fails rather than passing.
proc positive_control {target_tiles} {
    set problems {}
    set expected {evolvable_0 evolvable_1 evolvable_2 evolvable_3 evolvable_4 evolvable_5}
    set seen [cells_in $target_tiles]
    set names {}
    foreach c $seen { lappend names [get_property NAME $c] }
    foreach e $expected {
        if {[lsearch -exact $names $e] < 0} {
            lappend problems "positive control: $e was not seen in the target columns"
        }
    }
    # and their named data nets must be visible too
    set nets {}
    foreach e $expected {
        foreach pin [get_pins -quiet -of_objects [get_cells -quiet $e]] {
            set n [get_nets -quiet -of_objects $pin]
            if {[llength $n]} { lappend nets [get_property NAME $n] }
        }
    }
    if {![llength $nets]} {
        lappend problems "positive control: no data nets found on the evolvable LUTs"
    }
    return $problems
}

# Net ownership by ROUTED RESOURCE, not by logical net. A net is "in" a column segment
# when a PIP or node it actually uses is in that segment; a logical net whose name merely
# appears in a tile query may be routed nowhere near it, and — more importantly — a net
# that IS routed through cannot be excused by being global or constant without an argument
# about frame ownership. So nothing is filtered by name here.
proc nets_routed_through {tiles} {
    set hits {}
    set nodes [get_nodes -quiet -of_objects $tiles]
    if {[llength $nodes]} {
        foreach n [get_nets -quiet -of_objects $nodes] {
            lappend hits [get_property NAME $n]
        }
    }
    set pips [get_pips -quiet -of_objects $tiles]
    if {[llength $pips]} {
        foreach n [get_nets -quiet -of_objects $pips] {
            lappend hits [get_property NAME $n]
        }
    }
    return [lsort -unique $hits]
}

# MEMBERSHIP ORACLE. `llength [get_cells -of_objects $pblock]` is NOT the leaf-primitive
# count — it read 36 while all 865 primitives carried PBLOCK=pb_logic — so it must not be
# used to decide whether the constraint applies. Ask the cells themselves, and ask the
# pblock whether it is even a boundary.
proc pblock_problems {} {
    set problems {}
    set pb [get_pblocks -quiet pb_logic]
    if {![llength $pb]} { return [list "pb_logic does not exist"] }
    if {[get_property IS_SOFT $pb] != 0} {
        lappend problems "pb_logic is SOFT: the placer may cross it, so the range is a preference"
    }
    set expected [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE && NAME !~ "evolvable_*"}]
    set outside {}
    foreach c $expected {
        if {[get_property PBLOCK $c] ne "pb_logic"} { lappend outside [get_property NAME $c] }
    }
    if {[llength $outside]} {
        lappend problems "[llength $outside] primitive(s) are not in pb_logic, e.g. [lrange $outside 0 4]"
    }
    set pc [get_property PRIMITIVE_COUNT $pb]
    if {$pc != [llength $expected]} {
        lappend problems "pb_logic PRIMITIVE_COUNT $pc but [llength $expected] primitives were expected"
    }
    return $problems
}

proc carrier_isolation_checks {outdir} {
    set problems {}
    foreach p [pblock_problems] { lappend problems $p }

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

    # ---- 1b. positive control, before any verdict is trusted
    foreach p [positive_control $target_tiles] { lappend problems $p }

    # ---- 2. net ownership, judged on routed resources
    #
    # The target is NOT "the residual set is exactly the twelve". It is:
    #
    #   (a) the residual set is a SUBSET of the mechanically derived allowlist, and
    #   (b) every net in it had to cross, judged from where its endpoints are PLACED.
    #
    # (b) matters because a data net whose endpoints are both on one side of a flush
    # column has no business detouring through it, and a rule that only checked membership
    # would wave that through. Nothing here is a hard-coded count: how many nets must cross
    # follows from the placement, and writing "12" or "10" into the checker would make the
    # expected answer the rule.
    set flush_nets [nets_routed_through $flush_tiles]
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
    foreach n [nets_routed_through $target_tiles] {
        if {[lsearch -exact $allow $n] < 0} {
            lappend problems "net routed through a target column is not an evolvable data net: $n"
        }
    }

    # (b) a crossing net must have endpoints on BOTH sides of the column it crosses.
    # `must_cross` is derived per net from the placed cells' SLICE X coordinates against
    # the flush column's own X range; a net that did not have to cross and did is a detour
    # and is refused with the rest.
    foreach n $flush_nets {
        if {[lsearch -exact $allow $n] < 0} {
            lappend problems "net crosses a flush column and is not on the allowlist: $n"
            continue
        }
        set net [get_nets -quiet $n]
        set xs {}
        foreach c [get_cells -quiet -of_objects $net] {
            set loc [get_property LOC $c]
            if {[regexp {SLICE_X(\d+)Y} $loc -> x]} { lappend xs $x }
        }
        if {![llength $xs]} { continue }
        set lo [lindex [lsort -integer $xs] 0]
        set hi [lindex [lsort -integer $xs] end]
        # the flush CLB column occupies SLICE_X4..X5; a net entirely left of it or
        # entirely right of it had no reason to be in it
        if {($hi < 4) || ($lo > 5)} {
            lappend problems \
                "allowlisted net $n detours through a flush column: its endpoints are all\
                 on one side (SLICE_X $lo..$hi)"
        }
    }

    set fh [open $outdir/isolation.txt w]
    puts $fh "allowed evolvable data nets:"
    foreach n $allow { puts $fh "  $n" }
    puts $fh "target cells: [llength $target_cells]  flush cells: [llength $flush_cells]"
    puts $fh "flush nets:   [llength $flush_nets]"
    puts $fh "flush crossers (must all be allowlisted, and must all have had to cross):"
    foreach n $flush_nets { puts $fh "  $n" }
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
