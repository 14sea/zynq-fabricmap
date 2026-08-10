# Claim B round-1 carrier constraints.
#
# Placement scopes are EXACT, per carrier design §3, and they are not one rule twice:
#   flush columns  -> no cell of any kind, and routing must be empty
#   target columns -> no cell except the six named evolvable LUT BELs
#
# A pblock is an instruction to the tools and is not evidence; §4's checks read the ROUTED
# design and are what actually decides.

# ---------------------------------------------------------------- the evolvable LUTs
set_property BEL A6LUT [get_cells evolvable_0]
set_property LOC SLICE_X2Y25 [get_cells evolvable_0]
set_property BEL D6LUT [get_cells evolvable_1]
set_property LOC SLICE_X2Y25 [get_cells evolvable_1]
set_property BEL A6LUT [get_cells evolvable_2]
set_property LOC SLICE_X9Y25 [get_cells evolvable_2]
set_property BEL D6LUT [get_cells evolvable_3]
set_property LOC SLICE_X9Y25 [get_cells evolvable_3]
set_property BEL A6LUT [get_cells evolvable_4]
set_property LOC SLICE_X8Y25 [get_cells evolvable_4]
set_property BEL D6LUT [get_cells evolvable_5]
set_property LOC SLICE_X8Y25 [get_cells evolvable_5]

# LOCK_PINS is contract, not tuning: the certified addresses are the INIT bits under this
# exact mapping. A permuted mapping puts the same truth table on different bits.
# unrolled: XDC does not accept `foreach`
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_0]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_1]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_2]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_3]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_4]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_5]

# ------------------------------------------------------- keep everything else outside
# The scorer/guard/control region: the frozen preferred region (carrier design §9).
create_pblock pb_logic
add_cells_to_pblock pb_logic [get_cells -quiet -hierarchical -filter \
    {PRIMITIVE_GROUP != LUT || NAME !~ "evolvable_*"}]
resize_pblock pb_logic -add {SLICE_X12Y0:SLICE_X43Y49}
set_property CONTAIN_ROUTING false [get_pblocks pb_logic]

# The four column segments. PROHIBIT is per-site, and the six evolvable BELs are excluded
# from the target-column prohibition by listing the sites individually.
# Flush and target column segments are enforced by the pblock above plus the routed-design
# checks in isolation_checks.tcl. A PROHIBIT list is not used here: XDC accepts no `if`,
# and a bare set_property over an empty site list is an error rather than a no-op — the
# routed-design check is the evidence anyway (design §4), so the constraint file does not
# pretend to be one.
