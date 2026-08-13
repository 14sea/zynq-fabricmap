#!/usr/bin/env bash
# Mutation test for the ICAP readback sequencer: break it one way at a time and require
# `tb_carrier_readback` to notice.
#
# WHY
# ---
# A bench that passes proves nothing on its own — erratum 004's bench passed for years
# against an RTL that implemented no readback protocol at all. What has to be shown is that
# the bench FAILS when the sequence is wrong, and separately for each way it can be wrong.
# The eight mutations below are exactly the erratum-004 ruling's list.
#
# Each mutation is applied to a COPY of the sources in a scratch directory, never to the
# working tree: a mutation left behind is worse than no mutation testing at all.
#
#   scripts/mutate_carrier_readback.sh
#
# Every mutant carries the outcome it is EXPECTED to produce, and the script fails if any
# of them does something else. Most must be killed. One is expected to survive, and that is
# the interesting one: because the sequencer MEASURES the read pipeline instead of pinning
# it, shortening the flush is absorbed rather than fatal — so the mutant is equivalent, and
# recording it as an expected survivor is the difference between a property and a hole. The
# case that does kill it is the same mutation pushed past the probe's 64-word cap.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CARRIER="$REPO/vivado/carrier"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

SRC=(carrier_stream.v carrier_crc32.v icape2_model.v tb_carrier_readback.v)

survivors=0
killed=0

# mutate <name> <description> <anchor> <replacement> [expect: kill|survive] [model-flush]
mutate() {
    local name="$1" desc="$2" find="$3" repl="$4"
    local expect="${5:-kill}" flush="${6:-32}"
    local dir="$WORK/$name"
    mkdir -p "$dir"
    for f in "${SRC[@]}"; do cp "$CARRIER/$f" "$dir/"; done
    cp "$CARRIER/tb_envelope0.hex" "$dir/"

    if ! FIND="$find" REPL="$repl" python3 - "$dir/carrier_stream.v" <<'PY'
import os, sys
path = sys.argv[1]
src = open(path).read()
find, repl = os.environ["FIND"], os.environ["REPL"]
if src.count(find) != 1:
    sys.exit(f"anchor matched {src.count(find)} times, expected exactly 1: {find!r}")
open(path, "w").write(src.replace(find, repl))
PY
    then
        echo "  $name: ANCHOR FAILED — the mutation was never applied"
        survivors=$((survivors + 1))
        return
    fi

    # Run at a NON-ZERO read latency: with latency 0 a sequencer that pins the skip to 0
    # is an equivalent mutant, and an equivalent mutant surviving would be read as a hole
    # in the bench rather than as the tautology it is.
    if ! ( cd "$dir" && iverilog -g2012 -s tb_carrier_readback \
            "-Ptb_carrier_readback.RB_LATENCY=32'd3" \
            "-Ptb_carrier_readback.MODEL_FLUSH=32'd${flush}" -o m.vvp "${SRC[@]}" \
            > compile.log 2>&1 ); then
        # A mutant that does not compile is not evidence about the bench.
        echo "  $name: DID NOT COMPILE (not counted)"
        sed 's/^/      /' "$dir/compile.log" | head -5
        survivors=$((survivors + 1))
        return
    fi

    ( cd "$dir" && timeout 900 vvp m.vvp > run.log 2>&1 ) || true
    local outcome how
    if grep -q 'READBACK TB: OK' "$dir/run.log"; then outcome=survive; else outcome=kill; fi

    if [ "$outcome" = "$expect" ]; then
        if [ "$outcome" = kill ]; then
            # HOW it died is the evidence: a mutant that dies at the sync probe and one
            # that dies at a frame CRC are different findings about the bench.
            how="$(grep -m1 'measured latency' "$dir/run.log" | sed 's/READBACK TB: //')"
            echo "  $name: killed — $how"
        else
            echo "  $name: survived, as expected — $desc"
        fi
        killed=$((killed + 1))
    else
        if [ "$outcome" = survive ]; then
            echo "  $name: SURVIVED — $desc went unnoticed"
        else
            echo "  $name: KILLED but was expected to survive — $desc"
        fi
        survivors=$((survivors + 1))
    fi
}

echo "mutants of the readback sequence:"

mutate no_rcfg "the RCFG command" \
    "6'd3:    icap_din <= br8(W_RCFG);" \
    "6'd3:    icap_din <= br8(W_NOOP);"

mutate wrong_far "the readback FAR" \
    "6'd1:    icap_din <= br8(frame_far(env, rb_frame));" \
    "6'd1:    icap_din <= br8(frame_far(env, rb_frame) + 32'd1);"

mutate short_fdro "the FDRO length" \
    "localparam integer RB_WORDS = 2 * FRAME_WORDS;                      // 202" \
    "localparam integer RB_WORDS = FRAME_WORDS;"

mutate no_dummy_discard "the dummy frame discard" \
    "rb_skip <= {1'b0, rb_lat} + SKIP_FRAME;" \
    "rb_skip <= {1'b0, rb_lat};"

mutate dummy_off_by_one "a dummy discard one frame too long" \
    "rb_skip <= {1'b0, rb_lat} + SKIP_FRAME;" \
    "rb_skip <= {1'b0, rb_lat} + 9'd202;"

# The device wants 32 clocks; the mutant sends 2. The readback still VERIFIES ALL FIFTEEN
# FRAMES — the other 30 clocks are consumed by the probe read, the probe measures a latency
# 30 words longer, and the frame read skips exactly that much more. Until 2026-08-13 this
# was an expected survivor for that reason.
#
# It is now killed, and by the telemetry alone: the engine reports the latency it measured,
# the bench knows what this device should have produced, and 33 is not 3. That is precisely
# what a telemetry field is for — the run still works, and the instrument still notices that
# the machine is not doing what it was built to do.
mutate short_flush "a 2-clock flush, which only the telemetry notices" \
    "localparam integer FLUSH_NOOPS = 32;" \
    "localparam integer FLUSH_NOOPS = 2;" \
    kill

# ...and the boundary: the same mutation against a device that wants 64 clocks pushes the
# probe past its 64-word cap, and the engine refuses with F_RBSYNC instead of reading
# rubbish. The cap is load-bearing even though the flush is not.
mutate short_flush_past_cap "a 2-clock flush against a 64-clock device" \
    "localparam integer FLUSH_NOOPS = 32;" \
    "localparam integer FLUSH_NOOPS = 2;" \
    kill 64

mutate csib_low_turn "the CSIB-High turnaround" \
    "                            RB_TRN: begin
                                icap_csib <= 1'b1;" \
    "                            RB_TRN: begin
                                icap_csib <= 1'b0;"

mutate no_bitswap "the ICAPE2 word ordering" \
    "                br8[b]      = d[7  - b];" \
    "                br8[b]      = d[b];"

mutate lat_hardcoded "the measured latency (pinned to 0 instead)" \
    "rb_lat           <= rb_lat_cnt;" \
    "rb_lat           <= 8'd0;"

# THE ERRATUM-005 DEFECT ITSELF, put back: pause the burst one clock in two. The old engine
# did this to let its byte-serial CRC drain, the old model called it a pause, and the board
# called it an abort. If this ever survives again, the model has stopped modelling it.
mutate csib_gap_in_burst "a CSIB gap in the middle of the FDRO burst" \
    "                            RB_DATA: begin
                                icap_csib <= 1'b0;" \
    "                            RB_DATA: begin
                                icap_csib <= icap_rd_valid;"

echo
echo "$killed as expected, $survivors unexpected"
[ "$survivors" -eq 0 ] || exit 1
