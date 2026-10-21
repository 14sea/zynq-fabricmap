# B4 carrier v2 isolation checks on the ROUTED design — the B1 carrier's vivado/carrier/isolation_checks.tcl (pinned,
# unchanged there) re-aimed at the v2 target: the twelve target cells in the target column segment of SLICE_X2Y25,
# nothing in the flush columns, the route inventory as EVIDENCE (erratum 001 stands), plus the v2-specific verdicts:
#   * the sampling path: every x5FF element's D enters the site through its bypass pin (AX .. DX) and every main
#     element's D comes from its LUT6's O6; every Q leaves the site (AQ .. DQ, AMUX .. DMUX);
#   * persistence: every b4_gsr_reg / b4_slot_ram bit is a RAM32X1S cell (LUTRAM, GSR-immune) — none became a
#     flip-flop; the expected count is checked;
#   * exactly one STARTUPE2, its GSR pin driven by the engine; ICAPE2 = 0.
proc tiles_of {pattern} { return [get_tiles -quiet $pattern] }
proc cells_in {tiles} {
    set sites [get_sites -quiet -of_objects $tiles]
    if {![llength $sites]} { return {} }
    return [get_cells -quiet -of_objects $sites]
}
set ::B4_TARGET_CELLS {target/target_lut_a target/target_lut_b target/target_lut_c target/target_lut_d
    target/target_ff_aff target/target_ff_a5ff target/target_ff_bff target/target_ff_b5ff
    target/target_ff_cff target/target_ff_c5ff target/target_ff_dff target/target_ff_d5ff}
proc positive_control {target_tiles} {
    set problems {}
    set seen [cells_in $target_tiles]
    set names {}
    foreach c $seen { lappend names [get_property NAME $c] }
    foreach e $::B4_TARGET_CELLS {
        if {[lsearch -exact $names $e] < 0} { lappend problems "positive control: $e was not seen in the target column" }
    }
    return $problems
}
proc nets_routed_through {tiles} {
    set hits {}
    set nodes [get_nodes -quiet -of_objects $tiles]
    if {[llength $nodes]} { foreach n [get_nets -quiet -of_objects $nodes] { lappend hits [get_property NAME $n] } }
    set pips [get_pips -quiet -of_objects $tiles]
    if {[llength $pips]} { foreach n [get_nets -quiet -of_objects $pips] { lappend hits [get_property NAME $n] } }
    return [lsort -unique $hits]
}
proc pblock_problems {} {
    set problems {}
    set pb [get_pblocks -quiet pb_logic]
    if {![llength $pb]} { return [list "pb_logic does not exist"] }
    if {[get_property IS_SOFT $pb] != 0} { lappend problems "pb_logic is SOFT" }
    set expected [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE && NAME !~ "target/target_*" && NAME != "startup" && NAME != "ps7"}]
    set outside {}
    foreach c $expected { if {[get_property PBLOCK $c] ne "pb_logic"} { lappend outside [get_property NAME $c] } }
    if {[llength $outside]} { lappend problems "[llength $outside] primitive(s) are not in pb_logic, e.g. [lrange $outside 0 4]" }
    return $problems
}
proc sha_of_list {outdir tag items} {
    set path [file join $outdir ".sha_$tag.tmp"]
    set fh [open $path w]
    foreach i $items { puts $fh $i }
    close $fh
    set h [lindex [exec sha256sum $path] 0]
    file delete -force $path
    return $h
}
# the site pin through which a cell pin's net enters / leaves SLICE_X2Y25
proc site_pin_of {cellpin} {
    set net [get_nets -quiet -of_objects [get_pins -quiet $cellpin]]
    if {![llength $net]} { return "" }
    set sp [get_site_pins -quiet -of_objects $net -filter {NAME =~ "SLICE_X2Y25/*"}]
    return [lsort [get_property NAME $sp]]
}
proc b4_isolation_checks {outdir} {
    set problems {}
    foreach p [pblock_problems] { lappend problems $p }
    set target_tiles [concat [tiles_of CLBLL_L_X2Y*] [tiles_of INT_L_X2Y*] [tiles_of CLBLM_L_X6Y*] [tiles_of INT_L_X6Y*]]
    set flush_tiles  [concat [tiles_of CLBLM_R_X3Y*] [tiles_of INT_R_X3Y*] [tiles_of DSP_R_X7Y*] [tiles_of INT_R_X7Y*]]
    # ---- 1. cell ownership
    set flush_cells [cells_in $flush_tiles]
    if {[llength $flush_cells]} { lappend problems "flush columns hold [llength $flush_cells] cell(s): $flush_cells" }
    set target_cells [cells_in $target_tiles]
    foreach c $target_cells {
        if {[lsearch -exact $::B4_TARGET_CELLS [get_property NAME $c]] < 0} { lappend problems "unexpected cell in a target column: [get_property NAME $c]" }
    }
    if {[llength $target_cells] != 12} { lappend problems "target columns hold [llength $target_cells] cells, expected 12" }
    foreach p [positive_control $target_tiles] { lappend problems $p }
    # ---- 1c. the placement of every target cell: the site and the BEL the certificate's addresses belong to
    foreach {c bel} {target/target_lut_a A6LUT target/target_lut_b B6LUT target/target_lut_c C6LUT target/target_lut_d D6LUT
                     target/target_ff_aff AFF target/target_ff_a5ff A5FF target/target_ff_bff BFF target/target_ff_b5ff B5FF
                     target/target_ff_cff CFF target/target_ff_c5ff C5FF target/target_ff_dff DFF target/target_ff_d5ff D5FF} {
        set cell [get_cells -quiet $c]
        if {[llength $cell] != 1} { lappend problems "$c: not exactly one cell"; continue }
        if {[get_property LOC $cell] ne "SLICE_X2Y25"} { lappend problems "$c is at [get_property LOC $cell], not SLICE_X2Y25" }
        if {[get_property BEL $cell] ne "SLICEL.$bel"} { lappend problems "$c is on BEL [get_property BEL $cell], not SLICEL.$bel" }
    }
    # ---- 1d. the sampling path: D in through the bypass pins (x5FF) / the LUT (main), Q out through the site pins
    set path_record {}
    foreach {c pin} {target/target_ff_a5ff AX target/target_ff_b5ff BX target/target_ff_c5ff CX target/target_ff_d5ff DX} {
        set sp [site_pin_of $c/D]
        lappend path_record "$c/D <- $sp"
        if {[lsearch -exact $sp "SLICE_X2Y25/$pin"] < 0} { lappend problems "$c/D does not enter the site through $pin (site pins: $sp)" }
    }
    foreach {c lut} {target/target_ff_aff target/target_lut_a target/target_ff_bff target/target_lut_b target/target_ff_cff target/target_lut_c target/target_ff_dff target/target_lut_d} {
        set dnet [get_nets -quiet -of_objects [get_pins $c/D]]
        set onet [get_nets -quiet -of_objects [get_pins $lut/O]]
        lappend path_record "$c/D = [get_property NAME $dnet] (LUT O: [get_property NAME $onet])"
        if {[get_property NAME $dnet] ne [get_property NAME $onet]} { lappend problems "$c/D is not driven by $lut/O" }
    }
    foreach {c pin} {target/target_ff_aff AQ target/target_ff_bff BQ target/target_ff_cff CQ target/target_ff_dff DQ
                     target/target_ff_a5ff AMUX target/target_ff_b5ff BMUX target/target_ff_c5ff CMUX target/target_ff_d5ff DMUX} {
        set sp [site_pin_of $c/Q]
        lappend path_record "$c/Q -> $sp"
        if {[lsearch -exact $sp "SLICE_X2Y25/$pin"] < 0} { lappend problems "$c/Q does not leave the site through $pin (site pins: $sp)" }
    }
    foreach pin {CLK CE SR} {
        set net [get_nets -quiet -of_objects [get_site_pins SLICE_X2Y25/$pin]]
        lappend path_record "SLICE_X2Y25/$pin <- [get_property NAME $net]"
        if {![llength $net]} { lappend problems "SLICE_X2Y25/$pin is not driven" }
    }
    # ---- 1e. persistence: the store is LUTRAM, and all of it
    set ram_cells [get_cells -hierarchical -filter {REF_NAME == RAM32X1S}]
    # key 128 + key_loaded 1 + nonce 64 + armed 1 + fault 4 + recovery 1 + flags 9 + gsr_count 8 + idx 10 + base_state 8 + pulse 4 + slots 8 + applied inputs 32
    set expected_ram [expr {128 + 1 + 64 + 1 + 4 + 1 + 9 + 8 + 10 + 8 + 4 + 8 + 32}]
    if {[llength $ram_cells] != $expected_ram} { lappend problems "RAM32X1S cells: [llength $ram_cells], expected $expected_ram (a store bit became something else?)" }
    set ff_in_store [get_cells -quiet -hierarchical -filter {REF_NAME =~ "FD*" && (NAME =~ "*_store*" || NAME =~ "*slots*")}]
    if {[llength $ff_in_store]} { lappend problems "flip-flops inside the persistent store: $ff_in_store" }
    set startups [get_cells -hierarchical -filter {REF_NAME == STARTUPE2}]
    if {[llength $startups] != 1} { lappend problems "STARTUPE2 cells: [llength $startups], expected 1" }
    set gsr_net [get_nets -quiet -of_objects [get_pins -quiet startup/GSR]]
    if {![llength $gsr_net]} { lappend problems "startup/GSR is not driven" }
    set icap [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ "ICAPE2*"}]]
    if {$icap != 0} { lappend problems "ICAPE2 cells: $icap, expected 0" }
    # ---- 2. route inventory — EVIDENCE, NOT A VERDICT (erratum 001)
    set flush_nets  [nets_routed_through $flush_tiles]
    set target_nets [nets_routed_through $target_tiles]
    set allow {}
    foreach c $::B4_TARGET_CELLS {
        foreach p [get_pins -quiet -of_objects [get_cells -quiet $c]] {
            set n [get_nets -quiet -of_objects $p]
            if {[llength $n]} { lappend allow [get_property NAME $n] }
        }
    }
    set allow [lsort -unique $allow]
    set target_foreign {}
    foreach n $target_nets { if {[lsearch -exact $allow $n] < 0} { lappend target_foreign $n } }
    set node_names {}
    foreach t [concat $target_tiles $flush_tiles] { foreach nd [get_nodes -quiet -of_objects $t] { lappend node_names [get_property NAME $nd] } }
    set node_names [lsort -unique $node_names]
    set pip_names {}
    foreach t [concat $target_tiles $flush_tiles] { foreach pp [get_pips -quiet -of_objects $t] { lappend pip_names [get_property NAME $pp] } }
    set pip_names [lsort -unique $pip_names]
    set fh [open $outdir/isolation.txt w]
    puts $fh "ARCHITECTURE ERRATUM 001 is in force: the route inventory below is EVIDENCE, not a verdict."
    puts $fh ""
    puts $fh "VERDICTS"
    puts $fh "  target cells: [llength $target_cells] (must be exactly 12, at SLICE_X2Y25 on their BELs)"
    puts $fh "  flush cells:  [llength $flush_cells] (must be 0)"
    puts $fh "  RAM32X1S:     [llength $ram_cells] (must be $expected_ram); flip-flops in the store: [llength $ff_in_store] (must be 0)"
    puts $fh "  STARTUPE2:    [llength $startups] (must be 1, GSR driven); ICAPE2: $icap (must be 0)"
    puts $fh "SAMPLING PATH"
    foreach r $path_record { puts $fh "  $r" }
    puts $fh "EVIDENCE"
    puts $fh "  target data nets:           [llength $allow]"
    puts $fh "  nets over flush segments:   [llength $flush_nets]"
    puts $fh "  nets over target segments:  [llength $target_nets]"
    puts $fh "  of those, foreign:          [llength $target_foreign]"
    puts $fh "  routed nodes sha256:        [sha_of_list $outdir nodes $node_names] ([llength $node_names] nodes)"
    puts $fh "  routed pips  sha256:        [sha_of_list $outdir pips $pip_names] ([llength $pip_names] pips)"
    puts $fh "  flush net inventory sha256: [sha_of_list $outdir flushnets $flush_nets]"
    puts $fh "  target net inventory sha256:[sha_of_list $outdir targetnets $target_nets]"
    puts $fh "target data nets:"
    foreach n $allow { puts $fh "  $n" }
    if {[llength $problems]} { puts $fh "PROBLEMS:"; foreach p $problems { puts $fh "  $p" } } else { puts $fh "NO PROBLEMS" }
    close $fh
    if {[llength $problems]} {
        foreach p $problems { puts "ISOLATION PROBLEM: $p" }
        error "isolation checks failed: [llength $problems] problem(s)"
    }
    puts "B4 CELL ISOLATION OK: target=[llength $target_cells] flush=[llength $flush_cells] ram=[llength $ram_cells] startup=[llength $startups] -> $outdir/isolation.txt"
}
