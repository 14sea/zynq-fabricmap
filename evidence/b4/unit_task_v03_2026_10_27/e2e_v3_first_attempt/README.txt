The first run of e2e_v3_fixtures.py on the final tree (bf02746), kept as its run.log and summary.json only (the case archives were
regenerable and are not kept): every case as expected EXCEPT the driver's own `old_archives.untouched` check, which — copied from the
v0.2.0 driver — asserted that the repository's `evidence/b4/gonogo/` namespace does not exist. It exists since the committed b4-sim-4
decision of 2026-10-21 (adce027). The product was untouched (every committed archive byte-identical before and after); the driver's
assumption was stale. The driver was corrected (the five committed directories and the three namespaces' listings compared before and
after; the v0.2.0 archive b4-sim-4 and its go / no-go record added as the other-identity refusal cases) and run again: e2e_v3 /
e2e_v3_repeat. Nothing of the product changed between this attempt and the rerun.

A second attempt (the corrected `untouched` check) was stopped before its normalisation stage once its `old_archives` line showed the
new `b4-sim-4_gonogo_dir` probe marked not-named: the gonogo verifier refuses the v0.2.0 decision record at its policy-shape check
("policy: not the table's" — the v0.2.0 record's policy block carries `alpha_go`) BEFORE it reaches the identity comparison, so the
driver's needle "not this tool's" did not match a refusal that is nevertheless by name. The driver now accepts either text and records
which step refused. The product was not changed. No artefact of that stopped attempt is kept (nothing had been concluded).
