# B4 carrier v2 constraints. The target cells are pinned to the certified site and its BELs (the 21 certified
# addresses are the configuration bits of exactly these eight storage elements); everything else is kept out of
# the target and flush column segments by the pblock of build_b4.tcl and judged by isolation_checks_b4.tcl on
# the ROUTED design (a constraint is an instruction, not evidence).

# ---------------------------------------------------------------- the target slice SLICE_X2Y25
set_property LOC SLICE_X2Y25 [get_cells target/target_lut_a]
set_property BEL A6LUT       [get_cells target/target_lut_a]
set_property LOC SLICE_X2Y25 [get_cells target/target_lut_b]
set_property BEL B6LUT       [get_cells target/target_lut_b]
set_property LOC SLICE_X2Y25 [get_cells target/target_lut_c]
set_property BEL C6LUT       [get_cells target/target_lut_c]
set_property LOC SLICE_X2Y25 [get_cells target/target_lut_d]
set_property BEL D6LUT       [get_cells target/target_lut_d]
set_property LOC SLICE_X2Y25 [get_cells target/target_ff_aff]
set_property BEL AFF         [get_cells target/target_ff_aff]
set_property LOC SLICE_X2Y25 [get_cells target/target_ff_a5ff]
set_property BEL A5FF        [get_cells target/target_ff_a5ff]
set_property LOC SLICE_X2Y25 [get_cells target/target_ff_bff]
set_property BEL BFF         [get_cells target/target_ff_bff]
set_property LOC SLICE_X2Y25 [get_cells target/target_ff_b5ff]
set_property BEL B5FF        [get_cells target/target_ff_b5ff]
set_property LOC SLICE_X2Y25 [get_cells target/target_ff_cff]
set_property BEL CFF         [get_cells target/target_ff_cff]
set_property LOC SLICE_X2Y25 [get_cells target/target_ff_c5ff]
set_property BEL C5FF        [get_cells target/target_ff_c5ff]
set_property LOC SLICE_X2Y25 [get_cells target/target_ff_dff]
set_property BEL DFF         [get_cells target/target_ff_dff]
set_property LOC SLICE_X2Y25 [get_cells target/target_ff_d5ff]
set_property BEL D5FF        [get_cells target/target_ff_d5ff]
# the pass-through LUTs read their D on A1 (I0): LOCK_PINS is contract, as for the B1 carrier
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells target/target_lut_a]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells target/target_lut_b]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells target/target_lut_c]
set_property LOCK_PINS {I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6} [get_cells target/target_lut_d]

# ---------------------------------------------------------------- the slice clock is a fabric net
# The engine drives the slice's CLK pin from a register (a level the host sets step by step): not a clock in the
# timing sense. It takes general routing to the CLK pin, and the paths into and out of the target elements are
# not timed — the engine samples HOLD cycles after it moves anything.
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets -of_objects [get_pins target/target_ff_aff/C]]
set_false_path -to   [get_cells target/target_ff_*]
set_false_path -from [get_cells target/target_ff_*]

# ---------------------------------------------------------------- the init event
set_property LOC STARTUP_X0Y0 [get_cells startup]

# ---------------------------------------------------------------- the clock
create_clock -period 20.000 -name fclk0 [get_pins ps7/FCLKCLK[0]]
