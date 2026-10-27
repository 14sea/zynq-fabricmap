# The GSR-aware netlist of the B4 carrier v2 core for the vendor-model bench (sim/b4/run.sh, tb_b4_unisim over
# builds/b4/b4_core_funcsim.v): b4_core synthesised ALONE, out of context, and written as a functional-simulation netlist —
# every flip-flop a vendor FDxE that sees glbl.GSR, every LUTRAM a RAM32X1S, the constants driven by the netlist's own
# GND / VCC cells (a `write_verilog -cell` of the implemented top leaves the cell's constant nets undriven, which was
# found when that first export read Z on the response bits). Host-only.
#   vivado -mode batch -source vivado/b4/netlist_core.tcl -tclargs <outdir>
set outdir [lindex $argv 0]
set part   xc7z010clg400-1
set here   [file dirname [file normalize [info script]]]
set repo   [file dirname [file dirname $here]]
file mkdir $outdir
create_project -in_memory -part $part
add_files -norecurse [list $repo/rtl/b4/b4_core.v $repo/rtl/b4/b4_axil.v $repo/rtl/b4/b4_gate.v $repo/rtl/b4/b4_engine.v \
    $repo/rtl/b4/b4_gsr_reg.v $repo/rtl/b4/b4_slot_ram.v $repo/rtl/b4/b4_gsr_ram32.v $repo/rtl/b4/b4_axi_gate.v $repo/rtl/b1/p3_siphash.v]
synth_design -top b4_core -part $part -mode out_of_context -flatten_hierarchy none
set ffs [llength [get_cells -hierarchical -filter {REF_NAME =~ "FD*"}]]
set rams [llength [get_cells -hierarchical -filter {REF_NAME == RAM32X1S}]]
write_verilog -force -mode funcsim $outdir/b4_core_funcsim.v
set sha [lindex [exec sha256sum $outdir/b4_core_funcsim.v] 0]
set fh [open $outdir/b4_core_funcsim.json w]
puts $fh "{\"schema\": \"b4_core_funcsim\", \"schema_version\": \"1.0.0\", \"top\": \"b4_core\", \"mode\": \"post-synthesis, out of context\", \"vivado\": \"[version -short]\","
puts $fh " \"flip_flops\": $ffs, \"ram32x1s\": $rams, \"netlist_sha256\": \"$sha\"}"
close $fh
puts "B4 CORE NETLIST OK -> $outdir/b4_core_funcsim.v ($sha) FFs=$ffs RAM32X1S=$rams"
