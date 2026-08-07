# Readback for the formal `clb_ff_config` specimens, shared by the place-and-route flow
# and by the derived (cell-property) flow so both record exactly the same facts.
#
# This file emits RAW FACTS ONLY. It does not classify nets as dedicated or shared and it
# does not compare anything: the tiering of `docs/ff_builder_design.md` §5.3 is computed
# on the Python side from this file, so it can be tested without Vivado and so a change in
# the classification rule never silently changes what was recorded.
#
# Flat TAB-separated key/value rather than JSON: composing JSON in Tcl breaks on brace
# counting, and a half-written readback is worse than none.

proc kv {fh k v} { puts $fh "$k\t$v" }

proc ff_props {} {
    return {IS_C_INVERTED IS_G_INVERTED IS_CLR_INVERTED IS_PRE_INVERTED IS_R_INVERTED \
            IS_S_INVERTED IS_CE_INVERTED IS_GE_INVERTED IS_D_INVERTED}
}

# The six anchor/keeper cells, by top-level name. They are NOT inside generate blocks, so
# a bare name is safe here — unlike the target cells, which are.
proc ak_cells {} {
    return {anchor_lut1 anchor_lut2 anchor_ff anchor_ff2 q_reduce1 q_reduce2}
}

proc emit_cell_facts {fh prefix c} {
    kv $fh $prefix.name      [get_property NAME $c]
    kv $fh $prefix.ref       [get_property REF_NAME $c]
    kv $fh $prefix.loc       [get_property LOC $c]
    kv $fh $prefix.bel       [get_property BEL $c]
    kv $fh $prefix.init      [get_property -quiet INIT $c]
    kv $fh $prefix.lock_pins [get_property -quiet LOCK_PINS $c]
    foreach p [ff_props] {
        kv $fh $prefix.prop.$p [get_property -quiet $p $c]
    }
    # Local driver/sink identity at each pin: which net, on which BEL pin, in which
    # direction. This is tier 1 — it catches a rewired cell without asserting anything
    # about the rest of that net, which is the distinction revision 3 had to make.
    foreach pin [get_pins -of_objects $c] {
        set leaf [lindex [split $pin /] end]
        set net  [get_nets -quiet -of_objects $pin]
        kv $fh $prefix.pin.$leaf.net    $net
        kv $fh $prefix.pin.$leaf.dir    [get_property DIRECTION $pin]
        kv $fh $prefix.pin.$leaf.belpin [get_bel_pins -quiet -of_objects $pin]
    }
}

proc emit_readback {outdir site asite asite2 part variant mode idx} {
    set st [get_sites $site]
    set fh [open $outdir/readback.tsv w]

    kv $fh schema          ff_formal_readback/1
    kv $fh part            $part
    kv $fh vivado_version  [version -short]
    kv $fh variant         $variant
    kv $fh mode            $mode
    kv $fh idx             $idx
    kv $fh site            $site
    kv $fh anchor_site     $asite
    kv $fh keeper_site     $asite2
    kv $fh tile            [get_tiles -of_objects $st]
    kv $fh tile_type       [get_property TYPE [get_tiles -of_objects $st]]
    kv $fh site_type       [get_property SITE_TYPE $st]

    # ---- target cells -----------------------------------------------------------
    set stores [lsort [get_cells -hierarchical -filter {NAME =~ "*g_store*" && IS_PRIMITIVE \
                                                        && PRIMITIVE_LEVEL != "MACRO"}]]
    set luts [concat [lsort [get_cells -hierarchical -filter {NAME =~ "*g_hi*" && IS_PRIMITIVE}]] \
                     [lsort [get_cells -hierarchical -filter {NAME =~ "*g_lo*" && IS_PRIMITIVE}]]]
    kv $fh storage_count [llength $stores]
    kv $fh lut_count     [llength $luts]
    set n 0
    foreach c $stores { emit_cell_facts $fh store.$n $c ; incr n }
    set n 0
    foreach c $luts   { emit_cell_facts $fh lut.$n $c   ; incr n }

    # ---- anchor and keeper cells -------------------------------------------------
    foreach name [ak_cells] {
        set c [get_cells -quiet $name]
        if {$c eq ""} { error "anchor/keeper cell $name not found" }
        emit_cell_facts $fh ak.$name $c
    }

    # ---- every net: driver, sinks, route, pips -----------------------------------
    # Sinks and pips are sorted here so that an ordering difference between two runs is
    # never mistaken for a structural one. ROUTE_STATUS is recorded as a COMPLETION flag
    # only — two builds can both say ROUTED over entirely different paths, which is why
    # the route string and pip list are recorded at all.
    set n 0
    foreach net [get_nets -hierarchical] {
        set drv   [get_pins -quiet -of_objects $net -filter {DIRECTION == OUT}]
        set snk   [lsort [get_pins -quiet -of_objects $net -filter {DIRECTION == IN}]]
        set prts  [lsort [get_ports -quiet -of_objects $net]]
        kv $fh net.$n.name         [get_property NAME $net]
        kv $fh net.$n.driver       $drv
        kv $fh net.$n.sinks        $snk
        kv $fh net.$n.ports        $prts
        kv $fh net.$n.route_status [get_property -quiet ROUTE_STATUS $net]
        kv $fh net.$n.route        [get_property -quiet ROUTE $net]
        kv $fh net.$n.pips         [lsort [get_pips -quiet -of_objects $net]]
        incr n
    }
    kv $fh net_count $n

    # ---- occupied BELs of the target site ----------------------------------------
    # If a variant pulls a cell into the site that its pair partner does not, that is a
    # structural difference the diff would otherwise be blamed for.
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
    kv $fh occupied_count $n

    # ---- route pinning ------------------------------------------------------------
    # Fails if no first-phase snapshot was captured, rather than writing a readback that
    # would look complete without one.
    emit_routepin $fh
    close $fh
}

# ---------------------------------------------------------------------------------------
# Route pinning (design addendum 2026-08-07)
# ---------------------------------------------------------------------------------------
# The dedicated nets are routed before anything else and then frozen, so that two
# specimens of one committed pair cannot route them differently — the failure that stopped
# the 2026-08-06 holdout run. Everything here is RAW: which nets were computed, what they
# carried before the second routing pass and what they carry after. Nothing decides
# anything; the Python side recomputes the classification independently from `readback.tsv`
# and compares, so a drift between the two is a loud failure rather than a shared mistake.

proc cell_of_pin {pin} {
    set p [string trim $pin]
    set p [string trim $p "{}"]
    set slash [string last "/" $p]
    if {$slash < 0} { return $p }
    return [string range $p 0 [expr {$slash - 1}]]
}

# The anchor/keeper subgraph, extended by output buffers an anchor/keeper cell drives —
# the same rule the Python `classify_nets` applies to the readback.
proc ak_extended {} {
    set ak [ak_cells]
    set ext $ak
    foreach net [get_nets -hierarchical] {
        set drv [get_pins -quiet -of_objects $net -filter {DIRECTION == OUT}]
        if {[lsearch -exact $ak [cell_of_pin $drv]] < 0} { continue }
        foreach sink [get_pins -quiet -of_objects $net -filter {DIRECTION == IN}] {
            set cell [cell_of_pin $sink]
            if {[string match "*_OBUF_inst" $cell]} { lappend ext $cell }
        }
    }
    return [lsort -unique $ext]
}

proc dedicated_from_netlist {} {
    set ext [ak_extended]
    set out {}
    foreach net [get_nets -hierarchical] {
        set drv [get_pins -quiet -of_objects $net -filter {DIRECTION == OUT}]
        if {$drv eq "" || [lsearch -exact $ext [cell_of_pin $drv]] < 0} { continue }
        set inside 1
        foreach sink [get_pins -quiet -of_objects $net -filter {DIRECTION == IN}] {
            if {[lsearch -exact $ext [cell_of_pin $sink]] < 0} { set inside 0 ; break }
        }
        if {$inside} { lappend out [get_property NAME $net] }
    }
    return [lsort $out]
}

# Fail loudly rather than pin whatever happens to be there.
proc require_dedicated {expected} {
    set got [dedicated_from_netlist]
    if {$got ne [lsort $expected]} {
        error "dedicated set recomputed from the netlist is {$got}, expected {[lsort $expected]}"
    }
    return $got
}

# The first-phase snapshot is taken before the full routing pass and kept in a global
# array; `emit_routepin` takes the final one itself, at the moment it writes, so there is
# no window in which a "final" record could be captured before routing finished. Both go
# into `readback.tsv` under the `routepin.` namespace, which means the record is pinned by
# that artifact's hash in the stamp and verified by `verified_state` — no sidecar file and
# no change to the attestation schema.

proc routepin_fields {} { return {route pips driver sinks status fixed} }

proc routepin_read {name} {
    set n [get_nets -quiet $name]
    if {$n eq ""} { error "dedicated net $name does not exist" }
    set drv [get_pins -quiet -of_objects $n -filter {DIRECTION == OUT}]
    set snk [lsort [get_pins -quiet -of_objects $n -filter {DIRECTION == IN}]]
    return [list \
        route  [get_property -quiet ROUTE $n] \
        pips   [lsort [get_pips -quiet -of_objects $n]] \
        driver $drv \
        sinks  $snk \
        status [get_property -quiet ROUTE_STATUS $n] \
        fixed  [get_property -quiet IS_ROUTE_FIXED $n]]
}

proc routepin_capture_first {nets routable intrasite} {
    global ROUTEPIN
    array unset ROUTEPIN
    foreach name $nets {
        array set one [routepin_read $name]
        foreach field [routepin_fields] { set ROUTEPIN(first.$name.$field) $one($field) }
        array unset one
    }
    set ROUTEPIN(nets)      $nets
    set ROUTEPIN(routable)  $routable
    set ROUTEPIN(intrasite) $intrasite
}

proc emit_routepin {fh} {
    global ROUTEPIN
    if {![info exists ROUTEPIN(nets)]} {
        error "no first-phase route-pin snapshot was captured — refusing to write a\
               readback that would look complete"
    }
    set nets $ROUTEPIN(nets)
    if {[llength $nets] != 9} {
        error "route-pin snapshot covers [llength $nets] nets, expected 9"
    }
    puts $fh "routepin.schema\tff_formal_routepin/2"
    puts $fh "routepin.dedicated\t$nets"
    puts $fh "routepin.routable\t$ROUTEPIN(routable)"
    puts $fh "routepin.intrasite\t$ROUTEPIN(intrasite)"
    foreach name $nets {
        foreach field [routepin_fields] {
            if {![info exists ROUTEPIN(first.$name.$field)]} {
                error "route-pin record is missing first.$name.$field"
            }
            puts $fh "routepin.first.$name.$field\t$ROUTEPIN(first.$name.$field)"
        }
    }
    # The final phase is read here, not earlier: this proc runs after the full routing
    # pass, so "final" cannot be a value captured before routing finished.
    foreach name $nets {
        array set one [routepin_read $name]
        foreach field [routepin_fields] {
            puts $fh "routepin.final.$name.$field\t$one($field)"
        }
        array unset one
    }
}
