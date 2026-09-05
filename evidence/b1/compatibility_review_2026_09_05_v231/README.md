B1 v2.3.1 compatibility review evidence

Decision and limitations: [review](../../../docs/b1_compatibility_review_2026_09_05_v231.md).
The reviewed commit, manifest, image, ELF and carrier are bound in `review_metadata.json`.
`review_inputs_sha256.json` binds additional review inputs; `files_sha256.json` hashes the
other evidence files in this directory. The old image's HOLD evidence remains separate.

Run from the repository root, on the recorded compiler/BSP installation:

```sh
mkdir -p /tmp/b1_v231_compat
python3 evidence/b1/compatibility_review_2026_09_05_v231/collect.py
PYTHONPATH=tests python3 -m unittest test_b1_wire test_b1_carrier test_b1_build_evidence test_b1_leakage test_b1_twin test_b1_session test_b1_e2e test_b1_signer test_b1_records test_b1_hostapp
cc -std=c99 -O2 -Ifirmware/b1 evidence/b1/compatibility_review_2026_09_05_v231/payload_bound.c firmware/b1/b1_carto.c firmware/b1/b1_wire.c firmware/b1/p3_derive.c -o /tmp/b1_v231_compat/payload_bound
/tmp/b1_v231_compat/payload_bound
bash tb/b1/hostapp/build.sh /tmp/b1_v231_compat/hostapp
/tmp/b1_v231_compat/hostapp/hostapp opening
/tmp/b1_v231_compat/hostapp/hostapp probe
/tmp/b1_v231_compat/hostapp/hostapp closing
/tmp/b1_v231_compat/hostapp/hostapp ack_fail
/tmp/b1_v231_compat/hostapp/hostapp state_after_opening
/tmp/b1_v231_compat/hostapp/hostapp state_after_closing
```

`collect.py` writes temporary outputs to `/tmp/b1_v231_compat`, which must exist first.
It collects evidence and checks hashes; it does not issue a compatibility decision.
`stack_compile_flags.json` records the flags; `.su` files are compiler frame-size reports.
`stack_objects_match.json` records equality of `objdump -d` output, excluding the object
filename header, between each stack-instrumented object and the existing image build's
corresponding object. This checks code generation, not a complete stack-call-graph bound.

`payload_bound.c` is the earlier capacity scenario recompiled against the current sources.
Its synthetic fields are for capacity testing, not a valid scientific map or board run.
The application scenario outputs retain the limitation that prior SCORED candidates are
primed using the application's bookkeeping rather than executed through an actual PL.
