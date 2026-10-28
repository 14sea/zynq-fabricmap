#!/usr/bin/env bash
# The evidence of the B4Q runner unit (host-only, 2026-10-28), assembled from fresh runs (nothing copied from an earlier run): the
# build evidence of the v2 image (two clean builds), the host builds and the cortex-a9 compile check, the console e2e under BOTH
# sources (the emulated backend's logs; the PS evidence log pulled through the console) with fresh-process verifications, the runner
# e2e over the device surrogate on a PTY with its verifications, the A7 report of the valid PS-source session, the import check of
# the frozen b4/, the protected paths against main (e34432ea). The mutant battery and the tests are run apart (mutants.txt,
# tests_b4q.txt) because the battery edits sources in place and restores them.
set -euo pipefail
R=$(cd "$(dirname "$0")/../../.." && pwd)
U=$R/evidence/b4/unit_b4q_runner_2026_10_28
EM=$R/build/b4q_console_evidence_emulated
PS=$R/build/b4q_console_evidence_ps
RN=$R/build/b4q_runner_evidence
cd "$R"
{ echo "HEAD $(git rev-parse HEAD)"; echo "UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$U/run_header.txt"
python3 -B host/b4q_build_evidence.py --build --out "$U/build_evidence.json" > "$U/build_evidence.txt" 2>&1
bash firmware/b4q/build.sh > /dev/null
make -C firmware/b4q BUILD="$R/build/b4q_firmware" apphost wiretwin waittwin seqcut > "$U/host_build.txt" 2>&1
(cd firmware/b4q && make BUILD="$R/build/b4q_firmware" xcheck) > "$U/xcheck.txt" 2>&1 || true
rm -rf "$EM" "$PS" "$RN"
python3 -B host/b4q_console_e2e.py "$EM" > "$U/e2e_emulated_run.log" 2>&1
python3 -B host/b4q_console_e2e.py --source ps-evidence-log-v1 "$PS" > "$U/e2e_ps_run.log" 2>&1
python3 -B host/b4q_runner_e2e.py "$RN" > "$U/e2e_runner_run.log" 2>&1 || echo "runner e2e exit $?" >> "$U/e2e_runner_run.log"
keep() {   # $1 = source root, $2 = destination
  rm -rf "$2"; mkdir -p "$2"
  for d in "$1"/*/; do
    n=$(basename "$d")
    [ -f "$d/manifest.json" ] && { python3 -B host/b4q_verify.py "$d" --json "$d/verify.json" > "$d/verify.txt" 2>&1 || echo "verify exit $? for $n" >> "$2/verify_exits.txt"; }
    mkdir -p "$2/$n"
    cp -r "$d"/tx_* "$2/$n/" 2>/dev/null || true
    for f in manifest.json summary.json verify.json verify.txt session_open.json notary_log.json trace.jsonl pcap_log.jsonl events.jsonl console.jsonl uboot.json a5_verdict.json; do
      [ -f "$d/$f" ] && cp "$d/$f" "$2/$n/"
    done
    [ -f "$d/accesses.jsonl" ] && gzip -c "$d/accesses.jsonl" > "$2/$n/accesses.jsonl.gz"
    if [ -d "$d/raw" ]; then mkdir -p "$2/$n/raw"; for f in evidence_log.bin pulls.json console.bin console_tx.bin; do [ -f "$d/raw/$f" ] && cp "$d/raw/$f" "$2/$n/raw/"; done; fi
    [ -f "$d/private/surrogate_log.jsonl" ] && { mkdir -p "$2/$n/private"; cp "$d/private/surrogate_log.jsonl" "$2/$n/private/"; }   # the surrogate's own log: never the runner's input
  done
  [ -f "$1/e2e_summary.json" ] && cp "$1/e2e_summary.json" "$2/"
}
keep "$EM" "$U/e2e_emulated"
keep "$PS" "$U/e2e_ps"
keep "$RN" "$U/e2e_runner"
python3 -B host/b4q_a7.py "$PS/valid" > "$U/a7_valid_ps.txt" 2>&1 || true
python3 -B evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py > "$U/import_check.txt" 2>&1 || true
PROT="b4/host b4/schemas b4/hypothesis rtl builds vivado tb sim b3 firmware/b1 firmware/b2 evidence/b4/sim evidence/b4/gate evidence/b4/gonogo gate_runs manifests evidence/b4/unit_b4q_integration_2026_10_27 evidence/b4/unit_b4q_image_2026_10_28 firmware/b4q/b4q_tx.c"
{ echo "git diff --name-status e34432ea HEAD -- $PROT"; git diff --name-status e34432ea HEAD -- $PROT; echo "(end — empty means untouched since main e34432ea; b4q_tx.c unchanged)"; } > "$U/protected_paths.txt"
du -sh "$U/e2e_emulated" "$U/e2e_ps" "$U/e2e_runner" >> "$U/run_header.txt"
echo assembled
