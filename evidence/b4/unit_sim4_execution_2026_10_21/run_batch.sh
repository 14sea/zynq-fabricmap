#!/bin/bash
# The one production batch initiation of b4-sim-4 (owner's ruling 2026-10-21, section 3). Run from the repository root ONLY after
# operator_stop_check.py exited 0 on the same day. Captures stdout / stderr / exit outside the tracked tree. No retry.
set -u
R=/home/test/zynq_fabricmap; W=$R/build/wip/sim4_execution
cd "$R" || exit 99
if [ -f "$W/run_header.txt" ]; then echo "REFUSED: run_header.txt exists — a batch was already initiated; no second attempt" >&2; exit 98; fi
CMD='python3 -B b4/host/b4_sim.py --label b4-sim-4 --seeds 32 --deadline-s 3600'
{ echo "HEAD $(git rev-parse HEAD)"; echo "CMD $CMD"; echo "START_UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$W/run_header.txt"
$CMD > "$W/run_stdout.txt" 2> "$W/run_stderr.txt"; EXIT=$?
{ echo "EXIT $EXIT"; echo "END_UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$W/run_exit.txt"
echo "batch exit $EXIT"; exit $EXIT
