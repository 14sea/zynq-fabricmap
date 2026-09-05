#!/usr/bin/env bash
# Host-only simulation of the B1 carrier logic (iverilog): the instrument's SipHash bench,
# unchanged, over the verbatim p3_siphash.v; and tb_b1_core over the B1 gate / register file.
# Exit status = pass/fail. Reads the carrier constants from this repository's vivado/carrier
# (hash-equal to the instrument's imported copies: tests/test_b1_carrier.py).
set -u
cd "$(dirname "$0")/../.."
G=vivado/carrier/generated
PS=${PSORACLE_ROOT:-/home/test/zynq_psoracle}
python3 tb/b1/gen_b1_fixture.py >/dev/null || exit 1
mkdir -p sim/b1/out
iverilog -g2012 -o sim/b1/out/siphash.vvp rtl/b1/p3_siphash.v $PS/tb/tb_p3_siphash.v || exit 1
iverilog -g2012 -I tb/b1 -I $G -o sim/b1/out/core.vvp rtl/b1/p3_siphash.v rtl/b1/b1_arm_gate.v rtl/b1/b1_axil.v rtl/b1/b1_core.v \
    vivado/carrier/carrier_scorer.v tb/b1/tb_b1_core.v || exit 1
rc=0
r1=$(cd $PS && vvp -N "$OLDPWD/sim/b1/out/siphash.vvp" | grep -E '^TB_'); echo "tb_p3_siphash (verbatim): $r1"; [ "$r1" = TB_PASS ] || rc=1
r2=$(cd $G && vvp -N ../../../sim/b1/out/core.vvp | grep -E '^TB_|^FAIL'); echo "tb_b1_core:               $r2"; [ "$r2" = TB_PASS ] || rc=1
exit $rc
