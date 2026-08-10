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
# unrolled. XDC is Tcl and generally supports `foreach`; what failed is that construct in
# THIS constraint context ("Command 'foreach' is not supported in the xdc constraint file"
# for a file read as constraints). Not a blanket rule about the language.
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_0]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_1]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_2]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_3]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_4]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells evolvable_5]

# ------------------------------------------------------- keep everything else outside
# The scorer/guard/control region: the frozen preferred region (carrier design §9).
# The logic pblock is NOT created here. `add_cells_to_pblock` in an XDC runs at
# constraint-read time, before opt_design, and the cell set changes underneath it: of 865
# matching cells only 35 were captured, so the constraint was barely applied and the
# floorplan looked geometrically impossible when it had simply not been asked. It is
# created in build_carrier.tcl after opt_design instead.

# Flush and target column segments are enforced by the pblock created in build_carrier.tcl
# plus the routed-design checks in isolation_checks.tcl. No PROHIBIT list here: constraints
# are steering and the post-route checker is the authority (design §4).

# The clock. Without this the build reports "No user defined clocks" and every timing
# number in it is decorative — a report with no verdict power is not evidence of anything.
create_clock -period 20.000 -name fclk0 [get_pins ps7/FCLKCLK[0]]
