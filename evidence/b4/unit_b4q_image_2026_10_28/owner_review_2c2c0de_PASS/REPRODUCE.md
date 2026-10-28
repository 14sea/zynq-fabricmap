# Reproduce baseline, counterexamples and the approved repair

No command connects/powers a board, loads an image, uses physical PCAP or derives production seeds. Use disposable detached clones. This review's baseline clone is /tmp/owner_b4q_r4_vv0dliwh at 2c2c0dec; the separately patched clone is /tmp/owner_b4q_approved_fix_vptfvsn0 at the same commit with exactly the three-file owner patch. Review files are under /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28. Substitute paths in a copied review package for another run. Generation directories must be fresh; scripts write reports beside themselves.

Copy the pre-existing ignored builds/b4/b4_core_funcsim.v fixture from the canonical checkout into each clone; snapshot.json records its hash. No synthesis was performed. Existing pinned xPack/embeddedsw inputs are read in place. The tests' temporary image OUT is separate from build/b4q_image.

## Baseline

From an unbuilt baseline clone, the full invocation below yields 79 tests then an app setUpModule error because seqcut was not built (tests_fresh_checkout.txt). This real failure is retained, not rewritten as success. Explicitly build `make -C firmware/b4q seqcut`, then `python3 -B -m unittest tests.test_b4q_app` passes 22 tests (tests_app_after_prebuild.txt).

```sh
python3 -B -m unittest tests.test_b4carrier_benches tests.test_b4carrier_records tests.test_b4carrier_regmap tests.test_b4q_derive tests.test_b4q_emu tests.test_b4q_schema tests.test_b4q_view tests.test_b4q_firmware tests.test_b4q_session tests.test_b4q_wire tests.test_b4q_app
python3 -B host/b4q_build_evidence.py --build --out /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/build_evidence.json
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/prior_archive_probes.py /tmp/owner_b4q_r4_vv0dliwh
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/exchange_probes.py /tmp/owner_b4q_r4_vv0dliwh
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/terminal_archive_probes.py /tmp/owner_b4q_r4_vv0dliwh
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/end_reply_probes.py /tmp/owner_b4q_r4_vv0dliwh
make -C firmware/b4q seqcut
python3 -B -m unittest tests.test_b4q_app
python3 -B host/b4q_console_e2e.py build/owner_console_e2e
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/verify_cases.py /tmp/owner_b4q_r4_vv0dliwh
python3 -B host/b4q_a7.py build/owner_console_e2e/valid
make -C firmware/b4q xcheck
```

Original actual-app terminal observer:

```sh
cc -std=c99 -O2 -D_POSIX_C_SOURCE=200809L -DB4Q_APP_IDLE_POLLS=400000u -DB4Q_APP_REPLY_POLLS=200000u -DB4Q_APP_HB_EVERY=50000u -I firmware/b4q -I firmware/b4q/target firmware/b4q/target/b4q_app_host.c /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/terminal_app_fixture.c firmware/b4q/target/b4q_wire.c firmware/b4q/target/b4q_psmap.c firmware/b4q/b4q_tx.c firmware/b4q/b4q_derive.c firmware/b4q/b4q_cmd.c -Wl,--wrap=b4q_emit -o build/owner_terminal_apphost
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/terminal_app_probe.py /tmp/owner_b4q_r4_vv0dliwh
```

The fixture injects only the publishing counter before the original EV P4 event. App, transaction core and HAL are the actual delivered sources. After END the observer answers HAL requests only, with no new TX/signature. The final closed-console exception is expected. The earlier-cut owner fixture permits one diagnostic read but observes no writes/submissions; the author's limit-minus-one scenario terminates one event later and has zero reads too.

## Exact approved repair

In a NEW, unbuilt clone at the baseline commit, copy the netlist dependency, then apply the supplied patch and run the same complete unittest command. No manual seqcut build is needed: the corrected setup declares it. The independent result was 102 tests OK (patched_tests.txt).

```sh
git apply /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/owner_followup.patch
python3 -B -m unittest tests.test_b4carrier_benches tests.test_b4carrier_records tests.test_b4carrier_regmap tests.test_b4q_derive tests.test_b4q_emu tests.test_b4q_schema tests.test_b4q_view tests.test_b4q_firmware tests.test_b4q_session tests.test_b4q_wire tests.test_b4q_app
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_2c2c0de_2026_10_28/verify_approved_followup.py /tmp/owner_b4q_approved_fix_vptfvsn0
bash -n evidence/b4/unit_b4q_image_2026_10_28/assemble.sh
git diff --check
```

patched_checks/ scripts run the modified verifier in fresh processes against the baseline archives and regenerated cases. They retain separate logs from the baseline run. Both low-sequence exhaustion cases now reject; the 38 real archives retain agreement. STOPPED-after-sent-QUIT and observer-position probes are retained as nongating scope limits, not claimed as validation failures or physical timing facts.

## Author landing procedure

The canonical checkout has NOT had the patch applied by this reviewer. The author may apply the same patch and run the read-only hash checker there. Follow README section 4: exact repaired hashes, unchanged other runtime/protected paths/imports, and narrow docs/evidence closure changes. The owner's complete patched-code run is already supplied; exact landing does not require another full run or review. A different functional patch is not this approval.
