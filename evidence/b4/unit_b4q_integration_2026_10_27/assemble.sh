#!/usr/bin/env bash
# The evidence of the B4Q integration unit, assembled from fresh runs (nothing copied from an earlier run):
#   the firmware build record and the cross-compile check; the fidelity report; the e2e scenarios (every record, trace, PCAP log, the
#   access logs gzip-compressed) with the fresh-process verification of each; the A7 report of the valid session; the import check of
#   the frozen b4/ (untouched); the protected paths against the branch base.
set -euo pipefail
R=$(cd "$(dirname "$0")/../../.." && pwd)
U=$R/evidence/b4/unit_b4q_integration_2026_10_27
E=$R/build/b4q_e2e_evidence
cd "$R"
{ echo "HEAD $(git rev-parse HEAD)"; echo "UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$U/run_header.txt"
bash firmware/b4q/build.sh > /dev/null
cp build/b4q_firmware/build.json "$U/firmware_build.json"
(cd firmware/b4q && make xcheck) > "$U/xcheck.txt" 2>&1 || true
python3 -B host/b4q_emu_fidelity.py --json "$U/fidelity.json" > "$U/fidelity.txt" 2>&1 || true
rm -rf "$E"; python3 -B host/b4q_e2e.py "$E" > "$U/e2e_run.log" 2>&1
rm -rf "$U/e2e"; mkdir -p "$U/e2e"
for d in "$E"/*/; do
  n=$(basename "$d")
  python3 -B host/b4q_verify.py "$d" --json "$d/verify.json" > "$d/verify.txt" 2>&1 || echo "verify exit $? for $n" >> "$U/e2e_run.log"
  mkdir -p "$U/e2e/$n"
  cp -r "$d"/tx_* "$U/e2e/$n/" 2>/dev/null || true
  for f in manifest.json summary.json verify.json verify.txt session_open.json notary_log.json trace.jsonl pcap_log.jsonl events.jsonl a5_verdict.json a8_cross.json a2_rows.json; do
    [ -f "$d/$f" ] && cp "$d/$f" "$U/e2e/$n/"
  done
  gzip -c "$d/accesses.jsonl" > "$U/e2e/$n/accesses.jsonl.gz"
done
cp "$E/e2e_summary.json" "$U/e2e/"
python3 -B host/b4q_a7.py "$E/valid" > "$U/a7_valid.txt" 2>&1 || true
python3 -B evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py > "$U/import_check.txt" 2>&1 || true
{ echo "git diff --name-status dd8a7b9 HEAD -- b4/host b4/schemas b4/hypothesis rtl builds vivado tb sim b3 firmware/b1 firmware/b2 evidence/b4/sim evidence/b4/gate evidence/b4/gonogo gate_runs manifests"; git diff --name-status dd8a7b9 HEAD -- b4/host b4/schemas b4/hypothesis rtl builds vivado tb sim b3 firmware/b1 firmware/b2 evidence/b4/sim evidence/b4/gate evidence/b4/gonogo gate_runs manifests; echo "(end — empty means untouched)"; } > "$U/protected_paths.txt"
du -sh "$U/e2e" >> "$U/run_header.txt"
echo assembled
