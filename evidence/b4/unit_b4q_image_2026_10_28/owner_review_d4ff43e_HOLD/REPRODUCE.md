# Host-only reproduction

Use a detached disposable clone at d4ff43e6feb45c238f4c2fd8c1d80b2df338cfb1. This review used /tmp/owner_b4q_r3_gskm2dvv; substitute that path for another run. Review outputs were written to /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28. Copy the review directory first if preserving this exact run: the scripts write their reports beside themselves. Generation directories must be fresh.

Copy the existing ignored builds/b4/b4_core_funcsim.v from the canonical checkout into the clone; snapshot.json records its exact source/hash. It is a dependency fixture, not fresh synthesis. The pinned compiler/vendor inputs are read in place. Every execution below is emulated or compiled host-side; no board, image loading or physical PCAP.

From the detached clone:

```sh
python3 -B -m unittest tests.test_b4carrier_benches tests.test_b4carrier_records tests.test_b4carrier_regmap tests.test_b4q_derive tests.test_b4q_emu tests.test_b4q_schema tests.test_b4q_view tests.test_b4q_firmware tests.test_b4q_session tests.test_b4q_wire tests.test_b4q_app
python3 -B host/b4q_build_evidence.py --build --out /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/build_evidence.json
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/prior_archive_probes.py /tmp/owner_b4q_r3_gskm2dvv
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/exchange_probes.py /tmp/owner_b4q_r3_gskm2dvv
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/prior_console_probes.py /tmp/owner_b4q_r3_gskm2dvv
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/host_callback_probe.py /tmp/owner_b4q_r3_gskm2dvv
python3 -B host/b4q_console_e2e.py build/owner_console_e2e
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/verify_cases.py /tmp/owner_b4q_r3_gskm2dvv
python3 -B host/b4q_a7.py build/owner_console_e2e/valid
make -C firmware/b4q xcheck
```

The unittest module builds native binaries before the standalone console probes. Its Image test uses a separate temporary OUT, so it does not conflict with build/b4q_image. No mutation battery ran concurrently (or at all in this independent review).

The old direct no-wrap fixture:

```sh
cc -std=c99 -O2 -DB4Q_APP_REPLY_POLLS=10000u -DB4Q_APP_HB_EVERY=1000u -I firmware/b4q -I firmware/b4q/target /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/prior_wrap_probe.c firmware/b4q/target/b4q_wire.c firmware/b4q/target/b4q_psmap.c firmware/b4q/b4q_tx.c firmware/b4q/b4q_derive.c firmware/b4q/b4q_cmd.c -o build/owner_wrap_probe
build/owner_wrap_probe
```

Actual-app active-transaction terminal test:

```sh
cc -std=c99 -O2 -D_POSIX_C_SOURCE=200809L -DB4Q_APP_IDLE_POLLS=400000u -DB4Q_APP_REPLY_POLLS=200000u -DB4Q_APP_HB_EVERY=50000u -I firmware/b4q -I firmware/b4q/target firmware/b4q/target/b4q_app_host.c /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/terminal_app_fixture.c firmware/b4q/target/b4q_wire.c firmware/b4q/target/b4q_psmap.c firmware/b4q/b4q_tx.c firmware/b4q/b4q_derive.c firmware/b4q/b4q_cmd.c -Wl,--wrap=b4q_emit -o build/owner_terminal_apphost
python3 -B /home/test/zynq_fabricmap/build/wip/owner_review_d4ff43e_2026_10_28/terminal_app_probe.py /tmp/owner_b4q_r3_gskm2dvv
```

terminal_app_fixture.c includes the original b4q_app.c without editing it. The linker wrapper changes only S.seq, once, immediately before the original EV P4 callback. No peripheral response, transaction function or terminal implementation is patched. B4Q_OWNER_CUT enables that state injection; the control runs the identical binary without it. The Python diagnostic sends one root TX, receives END, then supplies only HAL responses to observe subsequent effects. It sends no next TX or signature. Continuing to answer the emulated HAL models direct peripheral accesses that do not wait for an external console host on the real platform. A short observer timeout protects this fixture only, not any experiment policy. The expected final closed-console exception is retained.

exchange_probes.py copies the submitted valid archive for each case. It removes or annotates SIGNREPLY material and updates the stated cached counts where specified, then runs the actual verifier in a new process. The exact edits, raw results and controls are retained. The labelled-as-stale cases do not alter the actual request id: they test whether annotation alone bypasses acceptance checks.

identity_checks.py takes the canonical repo as a read-only argument and normalises this review's clone path when comparing build provenance. Adjust that path in a copied review package for another clone. No production master/pair seed functions are called by these probes.
