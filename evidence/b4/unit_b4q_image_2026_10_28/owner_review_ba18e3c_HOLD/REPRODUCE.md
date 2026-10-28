# Reproduction notes

Run with Python 3 and the repository's documented compiler/vendor dependencies. No step connects a board. Use a detached disposable clone at ba18e3ca8c7260450a40daa2d7651cbc19c1f707; do not run mutation scripts against the canonical tree. This review used /tmp/owner_b4q_image_2skt9o2b; replace that path for another run. Review artifacts were written to /home/test/zynq_fabricmap/build/wip/owner_review_ba18e3c_2026_10_28.

Copy the already existing ignored builds/b4/b4_core_funcsim.v into the clone to run the accepted bench prerequisite. Its hash/source are in snapshot.json. Its compilation/simulation is rerun; synthesis is not. Build evidence reads the pinned toolchain and embeddedsw dependency paths in place, without editing them.

From the detached clone:

```sh
make -C firmware/b4q host apphost wiretwin twin
python3 -B host/b4q_build_evidence.py --build --out /home/test/zynq_fabricmap/build/wip/owner_review_ba18e3c_2026_10_28/build_evidence.json
python3 -B -m unittest tests.test_b4carrier_benches tests.test_b4carrier_records tests.test_b4carrier_regmap tests.test_b4q_derive tests.test_b4q_emu tests.test_b4q_schema tests.test_b4q_view tests.test_b4q_firmware tests.test_b4q_session tests.test_b4q_wire tests.test_b4q_app
python3 -B host/b4q_console_e2e.py build/owner_console_e2e
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_ba18e3c_2026_10_28/archive_probes.py /tmp/owner_b4q_image_2skt9o2b
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_ba18e3c_2026_10_28/console_probes.py /tmp/owner_b4q_image_2skt9o2b
python3 -B host/b4q_a7.py build/owner_console_e2e/valid
make -C firmware/b4q xcheck
```

The generation/probe directories must not already exist; choose a fresh detached clone for another run. archive_probes.py regenerates its report paths in this review directory, so copy the review package elsewhere first if preserving this exact run.

Original-C fixture builds (from the clone):

```sh
cc -std=c99 -O2 -DB4Q_APP_REPLY_POLLS=10000u -I firmware/b4q -I firmware/b4q/target /home/test/zynq_fabricmap/build/wip/owner_review_ba18e3c_2026_10_28/wait_probe.c firmware/b4q/target/b4q_wire.c firmware/b4q/target/b4q_psmap.c firmware/b4q/b4q_tx.c firmware/b4q/b4q_derive.c firmware/b4q/b4q_cmd.c -o build/owner_wait_probe
cc -std=c99 -O2 -I firmware/b4q /home/test/zynq_fabricmap/build/wip/owner_review_ba18e3c_2026_10_28/parser_probe.c firmware/b4q/b4q_cmd.c -o build/owner_parser_probe
build/owner_wait_probe 0
build/owner_wait_probe 1
build/owner_wait_probe 2
build/owner_parser_probe
```

Mode 0 is silent: application returns -1 at 30,000 readiness polls. Modes 1 and 2 intentionally exit **77 at the review fixture's 100,001st poll**, recording failure of the application's declared bound. Mode 1 streams valid, increasing-sequence SIGNREPLY frames to another req id; mode 2 streams an overlong unterminated line. Source files are not edited. Host console and MMIO are injected fixtures; the small poll budget is a compile-time test setting, not a measured physical timeout.

console_probes.py exercises the actual unmodified b4q_apphost. The duplicate case changes only which TX frame the fixture sends. The after-stop case first establishes that the ordinary transaction API refuses, then deliberately injects at the lower console boundary. Its raw next RESULT is not submitted as a valid new O/F/X; the probe reports the new signature/MMIO activity and return status as the failure.

The submitted mutant script also ran on the disposable clone only, with its output path redirected to this review directory. Its 240-second timeouts for removed-bound mutants are the script's own test limits, unrelated to any experiment deadline. The completed result is recorded separately in mutants.txt: 11/11 killed, no survivor/edit-miss. Final xcheck and console_probes were run again after the script restored the clone's sources. No mutation was made in the canonical repository.

To rerun identity_checks.py on the canonical read-only tree, first adjust its reviewer-clone path normalisation if using another checkout; its original JSON is preserved as evidence of this run.

console_probes_first.json retains the initial identical two scenarios. Its field name new_mmio_accesses actually counted backend trace events, including marks. The final probe calls that quantity new_trace_events and adds the host-receiver sequence fixture; the numerical values are unchanged.
