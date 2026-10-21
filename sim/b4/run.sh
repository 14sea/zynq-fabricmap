#!/usr/bin/env bash
# Host-only simulation of the B4 carrier v2 (iverilog):
#   * the instrument's SipHash bench, unchanged, over the verbatim p3_siphash.v (as sim/b1/run.sh);
#   * tb_b4_core over b4_core with the bench's fabric (the hypothesis model), one run per scenario;
#   * tb_b4_unisim over b4_core with the RTL target (vendor FDPE / LUT6 / RAM32X1S / STARTUPE2 models + glbl).
# Exit status = pass/fail. Logs in sim/b4/out/. Reads the fixture from tb/b4/b4_fixture.vh (gen_b4_fixture.py).
set -u
cd "$(dirname "$0")/../.."
PS=${PSORACLE_ROOT:-/home/test/zynq_psoracle}
UNI=${UNISIM_ROOT:-/home/test/Xilinx/2025.2/data/verilog/src}
RTL="rtl/b1/p3_siphash.v rtl/b4/b4_gsr_reg.v rtl/b4/b4_slot_ram.v rtl/b4/b4_gsr_ram32.v rtl/b4/b4_axi_gate.v rtl/b4/b4_axil.v rtl/b4/b4_gate.v rtl/b4/b4_engine.v rtl/b4/b4_core.v"
SCENARIOS="regs flow fault_not_armed fault_nokey fault_unsigned fault_wrong_commit fault_wrong_key fault_sequence fault_double_arm fault_realisable a5 a5_persist a5_wrong_context a5_flag_without_injection open_close_refused p9 p9_ok busy_refused step_atomic backpressure read_during_window read_at_launch session post_fault"
python3 -B tb/b4/gen_b4_fixture.py >/dev/null || exit 1
mkdir -p sim/b4/out
rc=0
iverilog -g2012 -o sim/b4/out/siphash.vvp rtl/b1/p3_siphash.v $PS/tb/tb_p3_siphash.v || exit 1
r1=$(cd $PS && vvp -N "$OLDPWD/sim/b4/out/siphash.vvp" | grep -E '^TB_'); echo "tb_p3_siphash (verbatim): $r1"; [ "$r1" = TB_PASS ] || rc=1
iverilog -g2012 -I tb/b4 -o sim/b4/out/core.vvp -y $UNI/unisims $RTL tb/b4/b4_target_slice_model.v tb/b4/tb_b4_core.v 2> sim/b4/out/core.compile.log || { cat sim/b4/out/core.compile.log; exit 1; }
for s in $SCENARIOS; do
    r=$(vvp -N sim/b4/out/core.vvp +SCENARIO=$s 2>&1 | grep -E '^TB_|^FAIL' | tee sim/b4/out/$s.result | tail -1)
    printf 'tb_b4_core %-20s %s\n' "$s:" "$r"; [ "$r" = "TB_PASS $s" ] || rc=1
done
iverilog -g2012 -I tb/b4 -o sim/b4/out/unisim.vvp -y $UNI/unisims $UNI/glbl.v $RTL rtl/b4/b4_target_slice.v tb/b4/tb_b4_unisim.v 2> sim/b4/out/unisim.compile.log || { cat sim/b4/out/unisim.compile.log; exit 1; }
vvp -N sim/b4/out/unisim.vvp 2>&1 | grep -E '^TB_|^FAIL|^GSR_PULSE' > sim/b4/out/unisim.result; grep -E '^GSR_PULSE' sim/b4/out/unisim.result; r2=$(tail -1 sim/b4/out/unisim.result); echo "tb_b4_unisim (RTL core):     $r2"; [ "$r2" = "TB_PASS unisim" ] || rc=1
# the PS path through the pinned AXI3 shim
iverilog -g2012 -I tb/b4 -o sim/b4/out/axi3.vvp -y $UNI/unisims $RTL vivado/carrier/carrier_axi3_lite.v tb/b4/b4_target_slice_model.v tb/b4/tb_b4_axi3.v 2> sim/b4/out/axi3.compile.log || { cat sim/b4/out/axi3.compile.log; exit 1; }
r3=$(vvp -N sim/b4/out/axi3.vvp 2>&1 | grep -E '^TB_|^FAIL' | tee sim/b4/out/axi3.result | tail -1); echo "tb_b4_axi3 (shim):           $r3"; [ "$r3" = "TB_PASS axi3" ] || rc=1
# the same vendor-model bench over the GSR-aware post-synthesis NETLIST of the core (vivado/b4/netlist_core.tcl: every flip-flop a vendor FDxE under glbl.GSR)
NET=builds/b4/b4_core_funcsim.v
if [ -f $NET ]; then
    iverilog -g2012 -I tb/b4 -o sim/b4/out/netlist.vvp -y $UNI/unisims $UNI/glbl.v $NET rtl/b4/b4_target_slice.v tb/b4/tb_b4_unisim.v 2> sim/b4/out/netlist.compile.log || { cat sim/b4/out/netlist.compile.log | head -20; exit 1; }
    vvp -N sim/b4/out/netlist.vvp 2>&1 | grep -E '^TB_|^FAIL|^GSR_PULSE' > sim/b4/out/netlist.result; grep -E '^GSR_PULSE' sim/b4/out/netlist.result; r4=$(tail -1 sim/b4/out/netlist.result); echo "tb_b4_unisim (NETLIST core): $r4"; [ "$r4" = "TB_PASS unisim" ] || rc=1
else
    echo "tb_b4_unisim (NETLIST core): SKIPPED — $NET absent (run vivado/b4/netlist_core.tcl)"; rc=1
fi
exit $rc
