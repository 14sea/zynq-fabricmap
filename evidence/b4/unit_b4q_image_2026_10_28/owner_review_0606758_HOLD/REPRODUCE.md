# Reproduce this owner review

All execution is host-only. Use a detached disposable clone at 0606758275f5828cd3594c3b689866e6a1060ce6, not the canonical checkout. This review used /tmp/owner_b4q_repair_i_m6wlns. Artifacts are in /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28; substitute these two paths for another run, and copy the review package first if preserving this run.

The tests require the pre-existing ignored builds/b4/b4_core_funcsim.v fixture. Copy it unchanged from the canonical checkout; snapshot.json records its source/hash. Synthesis was not rerun. Pinned xPack/embeddedsw dependencies are read in place. Build products and archive copies stay under the clone's ignored build/ or temporary directories. Use a fresh clone for repeat generation, because probe directories are required not to exist.

From the detached clone:

```sh
python3 -B -m unittest tests.test_b4carrier_benches tests.test_b4carrier_records tests.test_b4carrier_regmap tests.test_b4q_derive tests.test_b4q_emu tests.test_b4q_schema tests.test_b4q_view tests.test_b4q_firmware tests.test_b4q_session tests.test_b4q_wire tests.test_b4q_app
python3 -B host/b4q_build_evidence.py --build --out /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28/build_evidence.json
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28/archive_probes.py /tmp/owner_b4q_repair_i_m6wlns
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28/prior_console_probes.py /tmp/owner_b4q_repair_i_m6wlns
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28/host_callback_probe.py /tmp/owner_b4q_repair_i_m6wlns
python3 -B host/b4q_console_e2e.py build/owner_console_e2e
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28/verify_cases.py /tmp/owner_b4q_repair_i_m6wlns
python3 -B host/b4q_a7.py build/owner_console_e2e/valid
make -C firmware/b4q xcheck
```

The tests' setUpModule builds native binaries before the console probes. Their Image test builds to its own temporary OUT, separate from build/b4q_image. No source mutations or mutant tests ran in parallel with these checks. No independent mutant battery was run; the submitted 27-mutant log is identified as an author record.

Original-C probes, including the new near-limit fixture:

```sh
cc -std=c99 -O2 -DB4Q_APP_REPLY_POLLS=10000u -DB4Q_APP_HB_EVERY=1000u -I firmware/b4q -I firmware/b4q/target /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28/wrap_probe.c firmware/b4q/target/b4q_wire.c firmware/b4q/target/b4q_psmap.c firmware/b4q/b4q_tx.c firmware/b4q/b4q_derive.c firmware/b4q/b4q_cmd.c -o build/owner_wrap_probe
build/owner_wrap_probe
cc -std=c99 -O2 -DB4Q_APP_REPLY_POLLS=10000u -I firmware/b4q -I firmware/b4q/target /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28/prior_wait_probe.c firmware/b4q/target/b4q_wire.c firmware/b4q/target/b4q_psmap.c firmware/b4q/b4q_tx.c firmware/b4q/b4q_derive.c firmware/b4q/b4q_cmd.c -o build/owner_wait_probe
build/owner_wait_probe 0
build/owner_wait_probe 1
build/owner_wait_probe 2
cc -std=c99 -O2 -I firmware/b4q /home/test/zynq_fabricmap/build/wip/owner_review_0606758_2026_10_28/prior_parser_probe.c firmware/b4q/b4q_cmd.c -o build/owner_parser_probe
build/owner_parser_probe
```

prior_wait_probe.c and prior_console_probes.py are the previous owner fixtures, not rewritten product implementations. The wait modes now stop at 30,000 polls without hitting the fixture's emergency cap; the six parser cases now refuse; the duplicate and after-stop cases now return status 7 with zero new signature/trace events. The near-limit fixture injects internal sequence/line/kick counter state explicitly; it demonstrates a mechanism boundary, not billions of real emitted lines or a measured physical timeout.

archive_probes.py copies the submitted valid archive before every edit, re-frames changed payloads with valid CRCs and launches the actual verifier in a fresh process. It keeps the baseline and missing-log-only control beside the coordinated source/transaction/reply/identity negatives. Its exact changed fields and subprocess exit codes are retained. No result is manufactured into a new valid O/F/X.

identity_checks.py may be run with the canonical repository as its read-only argument. It normalises the reviewer clone path specified in its source; adjust that one path for a different clone. Its build source/read-only inventory checks do not call production seed derivation functions.
