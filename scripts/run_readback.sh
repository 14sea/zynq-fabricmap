#!/usr/bin/env bash
# Re-read the netlist edge of every mux specimen from its routed checkpoint.
#
# Completion is signalled by a marker file rather than by process detection: a
# `pgrep -f <script>` watcher matches its own command line and never fires, which cost
# this project one silently skipped pass — the readbacks looked regenerated and were
# not. Three rules make the marker trustworthy:
#
#   1. the marker is per-run and is removed before the run starts, so a stale file from
#      an earlier run can never be mistaken for this one finishing;
#   2. it is written only when every specimen succeeded AND its output is on disk, and
#      it is created atomically (write to a temp file, then mv);
#   3. it records the run id and the success/failure counts, so a reader can tell a
#      complete run from a partial one instead of inferring it from existence.
#
#   scripts/run_readback.sh <build-dir> <run-id>
set -euo pipefail

BUILD="${1:?usage: run_readback.sh <build-dir> <run-id>}"
RUN_ID="${2:?usage: run_readback.sh <build-dir> <run-id>}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER="$BUILD/READBACK_DONE.$RUN_ID.json"
TCL="$REPO/vivado/specimen/readback_ff.tcl"

rm -f "$MARKER"
ok=0; fail=0; failed=()

for d in "$BUILD"/SLICE*/; do
    name="$(basename "$d")"
    rm -f "$d/ff_readback.json"
    if ( cd "$d" && timeout 600 "$REPO/scripts/run_vivado.sh" -mode batch -nojournal \
            -notrace -log rb.log -source "$TCL" -tclargs "$PWD" > rb.out 2>&1 ) \
       && [ -s "$d/ff_readback.json" ] \
       && grep -q FF_READBACK_DONE "$d/rb.out"; then
        ok=$((ok + 1))
    else
        fail=$((fail + 1)); failed+=("$name")
    fi
done

total=$(find "$BUILD" -maxdepth 1 -name 'SLICE*' -type d | wc -l)
printf 'readback %s: %d ok, %d failed, of %d\n' "$RUN_ID" "$ok" "$fail" "$total"

if [ "$fail" -eq 0 ] && [ "$ok" -eq "$total" ]; then
    tmp="$(mktemp "$BUILD/.marker.XXXXXX")"
    printf '{"run_id": "%s", "expected": %d, "ok": %d, "failed": %d, "failed_names": []}\n' \
        "$RUN_ID" "$total" "$ok" "$fail" > "$tmp"
    mv -f "$tmp" "$MARKER"          # atomic: readers see it complete or not at all
    echo "marker: $MARKER"
else
    printf 'incomplete — no marker written. failed: %s\n' "${failed[*]:-none}" >&2
    exit 1
fi
