#!/usr/bin/env bash
# The evidence of the B4Q PS-image unit, assembled from fresh runs (nothing copied from an earlier run): the build evidence (two clean
# builds), the host builds and the cortex-a9 compile check, the console e2e scenarios with their fresh-process verifications and their
# console logs (the access logs gzip-compressed), the A7 report of the valid console session, the import check of the frozen b4/, the
# protected paths against the closed integration unit (e267405) and against main (dd8a7b9).
set -euo pipefail
R=$(cd "$(dirname "$0")/../../.." && pwd)
U=$R/evidence/b4/unit_b4q_image_2026_10_28
E=$R/build/b4q_console_evidence
cd "$R"
{ echo "HEAD $(git rev-parse HEAD)"; echo "UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$U/run_header.txt"
python3 -B host/b4q_build_evidence.py --build --out "$U/build_evidence.json" > "$U/build_evidence.txt" 2>&1
bash firmware/b4q/build.sh > /dev/null
make -C firmware/b4q BUILD="$R/build/b4q_firmware" apphost wiretwin > "$U/host_build.txt" 2>&1
(cd firmware/b4q && make BUILD="$R/build/b4q_firmware" xcheck) > "$U/xcheck.txt" 2>&1 || true
rm -rf "$E"; python3 -B host/b4q_console_e2e.py "$E" > "$U/e2e_run.log" 2>&1
rm -rf "$U/e2e"; mkdir -p "$U/e2e"
for d in "$E"/*/; do
  n=$(basename "$d")
  python3 -B host/b4q_verify.py "$d" --json "$d/verify.json" > "$d/verify.txt" 2>&1 || echo "verify exit $? for $n" >> "$U/e2e_run.log"
  mkdir -p "$U/e2e/$n"
  cp -r "$d"/tx_* "$U/e2e/$n/" 2>/dev/null || true
  for f in manifest.json summary.json verify.json verify.txt session_open.json notary_log.json trace.jsonl pcap_log.jsonl events.jsonl console.jsonl a5_verdict.json; do
    [ -f "$d/$f" ] && cp "$d/$f" "$U/e2e/$n/"
  done
  gzip -c "$d/accesses.jsonl" > "$U/e2e/$n/accesses.jsonl.gz"
done
cp "$E/e2e_summary.json" "$U/e2e/"
python3 -B host/b4q_a7.py "$E/valid" > "$U/a7_valid_console.txt" 2>&1 || true
python3 -B evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py > "$U/import_check.txt" 2>&1 || true
PROT="b4/host b4/schemas b4/hypothesis rtl builds vivado tb sim b3 firmware/b1 firmware/b2 evidence/b4/sim evidence/b4/gate evidence/b4/gonogo gate_runs manifests evidence/b4/unit_b4q_integration_2026_10_27"
{ echo "git diff --name-status e267405 HEAD -- $PROT"; git diff --name-status e267405 HEAD -- $PROT; echo "(end — empty means untouched since the closed integration unit)";
  echo; echo "git diff --name-status dd8a7b9 HEAD -- b4/host b4/schemas b4/hypothesis rtl builds vivado tb sim b3 firmware/b1 firmware/b2"; git diff --name-status dd8a7b9 HEAD -- b4/host b4/schemas b4/hypothesis rtl builds vivado tb sim b3 firmware/b1 firmware/b2; echo "(end — only the authorised manifest correction may appear)"; } > "$U/protected_paths.txt"
du -sh "$U/e2e" >> "$U/run_header.txt"
echo assembled
