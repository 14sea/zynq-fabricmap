#!/usr/bin/env bash
# Run the carrier's simulation benches under iverilog, including the readback sweep.
#
# WHY THIS EXISTS AS A SCRIPT
# ---------------------------
# The readback bench is parameterised: the same run must pass whatever the device's read
# pipeline turns out to be, because that number cannot be established in simulation. Running
# it by hand cost this round an hour — a shell quoting slip made `iverilog -P` silently fail
# and the DEFAULT configuration ran seven times while the output looked like a sweep.
#
# So every configuration is verified BY CONTENT: the bench prints the parameters it was
# actually elaborated with, and this script refuses the run unless that line matches what it
# asked for. A sweep that did not sweep is a failure here, not a pass.
#
#   scripts/run_carrier_benches.sh [--quick]
#
# `--quick` runs one configuration of the readback bench instead of the sweep.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CARRIER="$REPO/vivado/carrier"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

quick=0
[ "${1:-}" = "--quick" ] && quick=1

mkdir -p "$WORK/run"
for fixture in "$CARRIER/tb_envelope0.hex" \
               "$CARRIER/generated/carrier_targets.hex" \
               "$CARRIER/generated/carrier_vector_order.hex"; do
    [ -f "$fixture" ] && cp "$fixture" "$WORK/run/"
done

fails=0
ran=0

run_bench() {           # run_bench <name> <top> <extra-iverilog-args...>
    local name="$1" top="$2"; shift 2
    local out="$WORK/$name.log"
    ran=$((ran + 1))
    if ! iverilog -g2012 -o "$WORK/$name.vvp" -s "$top" "$@" 2> "$out.compile"; then
        echo "  $name: COMPILE FAILED"
        sed 's/^/    /' "$out.compile"
        fails=$((fails + 1))
        return
    fi
    # `$readmemh` resolves against the CWD, and the fixtures live in two different
    # directories (the envelope beside the sources, the scorer's tables under generated/).
    # One run directory holding both is less brittle than a per-bench cd.
    ( cd "$WORK/run" && timeout 900 vvp "$WORK/$name.vvp" ) > "$out" 2>&1 || true
    if grep -qE ': OK$' "$out" && ! grep -q 'FAILURE' "$out"; then
        echo "  $name: OK"
    else
        echo "  $name: FAILED"
        grep -E '^FAIL|TB:' "$out" | head -12 | sed 's/^/    /'
        fails=$((fails + 1))
    fi
}

echo "device model:"
run_bench model tb_icape2_model "$CARRIER/tb_icape2_model.v" "$CARRIER/icape2_model.v"

echo "readback against the model:"
if [ "$quick" = 1 ]; then
    configs=("0 32")
else
    # latency, flush. The design must not care about either. The ruling pins latency 0 and
    # 12 exactly, so both are run at flush 32 where the device owes no residual flush.
    configs=("0 32" "1 32" "3 32" "7 32" "12 32" "0 40" "5 48" "12 64")
fi

for cfg in "${configs[@]}"; do
    lat="${cfg% *}"; flush="${cfg#* }"
    name="readback_l${lat}_f${flush}"
    run_bench "$name" tb_carrier_readback \
        "-Ptb_carrier_readback.RB_LATENCY=32'd${lat}" \
        "-Ptb_carrier_readback.MODEL_FLUSH=32'd${flush}" \
        "$CARRIER/tb_carrier_readback.v" "$CARRIER/carrier_stream.v" \
        "$CARRIER/carrier_crc32.v" "$CARRIER/icape2_model.v"
    # BY CONTENT: the bench prints what it was elaborated with. If the override did not
    # take, the run above may well have said OK — for the wrong configuration.
    want="READBACK TB (latency ${lat}, flush ${flush})"
    if ! grep -qF "$want" "$WORK/$name.log"; then
        echo "    parameters did not take: wanted \"$want\", got:"
        grep -F 'READBACK TB (' "$WORK/$name.log" | sed 's/^/      /'
        fails=$((fails + 1))
    fi
done

echo "the older benches (unchanged scope):"
run_bench stream tb_carrier_stream "$CARRIER/tb_carrier_stream.v" \
    "$CARRIER/carrier_stream.v" "$CARRIER/carrier_crc32.v" "$CARRIER/icape2_model.v"
run_bench integration tb_carrier_integration "$CARRIER/tb_carrier_integration.v" \
    "$CARRIER/carrier_stream.v" "$CARRIER/carrier_crc32.v" "$CARRIER/carrier_scorer.v" \
    "$CARRIER/icape2_model.v"
run_bench known_answer tb_claimb_known_answer "$CARRIER/tb_claimb_known_answer.v" \
    "$CARRIER/carrier_scorer.v"
run_bench crc tb_crc "$CARRIER/tb_carrier_crc32.v" "$CARRIER/carrier_crc32.v"
run_bench axi3 tb_carrier_axi3 "$CARRIER/tb_carrier_axi3.v" "$CARRIER/carrier_axi3_lite.v"
run_bench axil tb_carrier_axil "$CARRIER/tb_carrier_axil.v" "$CARRIER/carrier_axil.v"

# tb_carrier_scorer fails 30 identically before and after every change in this area —
# pre-existing and out of scope (see the project's standing note). tb_carrier_chain is a
# board-replay diagnostic with no pass/fail verdict, so neither is run here.

echo
if [ "$fails" -eq 0 ]; then
    echo "all $ran bench runs OK"
else
    echo "$fails of $ran bench runs FAILED"
    exit 1
fi
