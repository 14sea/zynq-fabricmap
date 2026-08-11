# Carrier design §4, as amended by ARCHITECTURE ERRATUM 001 (docs/claimb_erratum_001_static_routes.md).
#
#   1. cell ownership     — exactly the six evolvable LUTs in the target columns, nothing at
#                           all in the flush columns.                        STILL A VERDICT.
#   2. route inventory    — the routed nodes, PIPs and nets of the touched regions, listed
#                           and hashed.                                      EVIDENCE ONLY.
#   3. INIT differential  — a POST-ROUTE ECO on the same routed DCP, never a re-route.
#
# WHY 2 IS NO LONGER A VERDICT. It was: "nothing of ours may be routed through a frame we
# write." Measured on this device that is unachievable — the carrier logic is at
# SLICE_X0..X1, the ICAPE2 site is on the right of the die, and the target and flush columns
# stand full-height between them, so every ICAP net must cross both (113 nets over the flush
# segments and 235 non-evolvable nets over the target segments, in the written rows alone).
# The right-hand floorplan fails the same way with the AXI bus instead. 7-series PR
# explicitly contemplates static routes inside a reconfigured region (UG909), so zero
# crossings was a stronger condition we adopted, not one silicon requires.
#
# The authority is now BIT INVARIANCE, in scripts/gate_candidate.py: every non-evolutionary
# bit of every written frame must equal the final carrier base. A net's name is not a safety
# argument; its configuration bits being unchanged is. So this file records what is routed
# there — it must never again decide it, and it must never exempt a net by name.

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
    # PRIMITIVE_COUNT is NOT the oracle and must not be a refusal. It read 1460 against
    # 1592 cells while every one of those cells carried PBLOCK=pb_logic — it does not count
    # the same set (PS7/ICAPE2-class primitives among them). The membership loop above is
    # the authority, exactly as this file already argues for CELL_COUNT. Reported so the
    # number is on the record and nobody chases it a second time.
    puts "pb_logic: PRIMITIVE_COUNT=[get_property PRIMITIVE_COUNT $pb]\
 cells-with-PBLOCK=[expr {[llength $expected] - [llength $outside]}] of [llength $expected]"
    return $problems
}

# sha256 over the SORTED, newline-joined names, so the digest is a property of the routed
# design and not of Tcl's enumeration order.
proc sha_of_list {outdir tag items} {
    set path [file join $outdir ".sha_$tag.tmp"]
    set fh [open $path w]
    foreach i $items { puts $fh $i }
    close $fh
    set h [lindex [exec sha256sum $path] 0]
    file delete -force $path
    return $h
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

    # ---- 2. route inventory — EVIDENCE, NOT A VERDICT (erratum 001)
    #
    # Enumerated and hashed so the record exists and any later change to it is visible.
    # Nothing here appends to `problems`: a net being present is not a finding, and a net
    # being absent is not a clearance. The question that decides safety is asked in
    # scripts/gate_candidate.py, over configuration bits.
    set flush_nets  [nets_routed_through $flush_tiles]
    set target_nets [nets_routed_through $target_tiles]

    # the evolvable data nets, recorded so the inventory can be read against them — NOT so
    # that membership excuses anything
    set allow {}
    foreach c $expected {
        foreach p [get_pins -quiet -of_objects [get_cells -quiet $c]] {
            set n [get_nets -quiet -of_objects $p]
            if {[llength $n]} { lappend allow [get_property NAME $n] }
        }
    }
    set allow [lsort -unique $allow]

    set target_foreign {}
    foreach n $target_nets {
        if {[lsearch -exact $allow $n] < 0} { lappend target_foreign $n }
    }

    # ---- the evidence file. Hashes are over the SORTED, newline-joined resource names, so
    # the digest is a property of the routed design and not of Tcl's enumeration order.
    set node_names {}
    foreach t [concat $target_tiles $flush_tiles] {
        foreach nd [get_nodes -quiet -of_objects $t] { lappend node_names [get_property NAME $nd] }
    }
    set node_names [lsort -unique $node_names]
    set pip_names {}
    foreach t [concat $target_tiles $flush_tiles] {
        foreach pp [get_pips -quiet -of_objects $t] { lappend pip_names [get_property NAME $pp] }
    }
    set pip_names [lsort -unique $pip_names]

    set fh [open $outdir/isolation.txt w]
    puts $fh "ARCHITECTURE ERRATUM 001 is in force: the route inventory below is EVIDENCE."
    puts $fh "It is not a verdict and it exempts nothing by name. The safety judgement is"
    puts $fh "bit invariance against the final carrier base, in scripts/gate_candidate.py."
    puts $fh ""
    puts $fh "VERDICTS (cell ownership only)"
    puts $fh "  target cells: [llength $target_cells] (must be exactly 6)"
    puts $fh "  flush cells:  [llength $flush_cells] (must be 0)"
    puts $fh ""
    puts $fh "EVIDENCE"
    puts $fh "  evolvable data nets:        [llength $allow]"
    puts $fh "  nets over flush segments:   [llength $flush_nets]"
    puts $fh "  nets over target segments:  [llength $target_nets]"
    puts $fh "  of those, non-evolvable:    [llength $target_foreign]"
    puts $fh "  routed nodes sha256:        [sha_of_list $outdir nodes $node_names] ([llength $node_names] nodes)"
    puts $fh "  routed pips  sha256:        [sha_of_list $outdir pips $pip_names] ([llength $pip_names] pips)"
    puts $fh "  flush net inventory sha256: [sha_of_list $outdir flushnets $flush_nets]"
    puts $fh "  target net inventory sha256:[sha_of_list $outdir targetnets $target_nets]"
    puts $fh ""
    puts $fh "evolvable data nets:"
    foreach n $allow { puts $fh "  $n" }
    puts $fh "flush segment net inventory:"
    foreach n $flush_nets { puts $fh "  $n" }
    puts $fh "target segment net inventory (foreign nets marked *):"
    foreach n $target_nets {
        if {[lsearch -exact $allow $n] < 0} { puts $fh "  * $n" } else { puts $fh "    $n" }
    }
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
    puts "CELL ISOLATION OK: target=[llength $target_cells] flush=[llength $flush_cells];\
 route inventory recorded (flush [llength $flush_nets], target [llength $target_nets],\
 foreign [llength $target_foreign]) -> $outdir/isolation.txt"
}
