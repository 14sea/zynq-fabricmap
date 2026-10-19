#!/usr/bin/env python3
"""Mutants for unit 2b-4 (the gate tool): hermetic tree copies; a kill only with Ran N > 0 and FAILED, the failing tests named.
The copy carries b4/, the pinned host modules the tests compare against by import, the formal inputs, the 38 exclusion sources,
the architecture document and the three top files of the committed S = 32 exploration (read-only reference of one test) — no other
evidence. Each mutant breaks ONE contract of the gate tool, its verifier or the harness's gate mode, and the tests it names are
run inside the copy. NO PRODUCTION SET IS DERIVED: the tests guard b4_seeds.master_seed / pair_seeds and run on hermetic roots."""
import json, re, shutil, subprocess, sys, tempfile, pathlib, time


def _repo_root() -> pathlib.Path:
    for start in (pathlib.Path.cwd(), pathlib.Path(__file__).resolve().parent):
        for cand in (start, *start.parents):
            if (cand / "b4/host/b4_seeds.py").is_file():
                return cand
    raise SystemExit("run from inside the zynq_fabricmap repository: no ancestor holds b4/host/b4_seeds.py")


R = _repo_root()
sys.path.insert(0, str(R / "b4/host"))
import b4_seeds as bs  # noqa: E402

SIM3 = "evidence/b4/sim/b4-sim-3_20261019T121833Z"
COPY = ["b4", "host/b1_carto.py", "host/b1_model.py", "host/b2_landscape.py", "host/b2_maps.py", "host/b2_gate.py", "host/b2_search.py", "docs/b4_architecture.md", "docs/ff_latch_probe.md",
        "gate_runs/run_2026_08_05_ff/certificate.json", "evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json",
        bs.EXPOSURE_RECEIPT_REL, f"{SIM3}/seeds.json", f"{SIM3}/manifest.json", f"{SIM3}/sim_report.json"] + [f[0] for f in bs.FIELDS]
GATE, GV, SIM = "b4/host/b4_gate.py", "b4/host/b4_gate_verify.py", "b4/host/b4_sim.py"
T = "b4.tests."
J, E = T + "test_b4_gate.TheJudge.", T + "test_b4_gate.EndToEnd."


class EditMiss(Exception):
    """A mutant's target text is not in the file exactly once: the mutant is not applied and the battery records the miss."""


def edit(rel, edits):
    def apply(tree):
        f = tree / rel; s = f.read_text()
        for old, new in edits:
            if s.count(old) != 1:
                raise EditMiss(f"{rel}: {old[:70]!r} occurs {s.count(old)} times")
            s = s.replace(old, new)
        f.write_text(s)
    return apply


MUTANTS = [
 ("G1 the budget rule without B* reported PASS",
  edit(GATE, [('"eligible_budgets": [], "status": "FAIL",', '"eligible_budgets": [], "status": "PASS",')]),
  [J + "test_no_b_star_leaves_the_dependent_rows_not_assessable_and_the_gate_cannot_pass", E + "test_a_valid_fail_archive_without_b_star_is_judged_fail_and_verifies_clean"]),
 ("G2 K5's Cohen's d read from F - R instead of delta1 = O - R",
  edit(GATE, [('dval, dspec = _stat_value(k5.get("cohen_d_delta1"))', 'dval, dspec = _stat_value(v["deltas"]["F_minus_R"]["cohen_d"])')]),
  [J + "test_k5_is_delta1_o_minus_r_not_f_minus_r"]),
 ("G3 K6's S = 200 condition dropped",
  edit(GATE, [("s_ok, n_ok = S == S_GATE, ", "s_ok, n_ok = True, ")]),
  [J + "test_k6_fails_when_s_is_not_the_planned_200"]),
 ("G4 a fixture batch can be formal",
  edit(GATE, [('    if doc.get("fixture") is not False:\n        r.append("a fixture batch")\n', "")]),
  [J + "test_the_formal_identity_on_a_pure_document", E + "test_a_valid_fail_archive_without_b_star_is_judged_fail_and_verifies_clean"]),
 ("G5 the verifier skips the deep re-verification of the batch archive",
  edit(GV, [("        if deep:\n            try:\n                bf = sv.verify_run_dir(bdir, deep=True)", "        if False:\n            try:\n                bf = sv.verify_run_dir(bdir, deep=True)")]),
  [E + "test_the_coordinated_tamper_of_the_evidence_is_caught_by_the_archive_re_verification"]),
 ("G6 the verifier does not hold the rows to the recomputed ones",
  edit(GV, [('    if _j(j["rows"]) != _j(doc["rows"]):\n        diff = [a["id"] for a, c in zip(j["rows"], doc["rows"]) if _j(a) != _j(c)]\n        F.add(bg.REPORT_JSON, f"the rows are not the ones recomputed from the evidence: {diff}")\n', "")]),
  [E + "test_every_tamper_of_the_gate_report_is_named_with_the_digests_refreshed"]),
 ("G7 K9: a semantic with no median (not assessable) is not a failure",
  edit(GATE, [("""            na.append(f"{sem} ({rec['not_assessable_seeds']} seeds not assessable)")""", "            pass")]),
  [J + "test_each_row_fails_on_its_own_number_and_the_verdict_names_it"]),
 ("G8 K3: a non-readable D / F ratio (non-positive denominator) is read as satisfied",
  edit(GATE, [('        if not (df.get("readable") is True and _num(df.get("ratio")) and df["ratio"] <= T["K3"]["ratio_max"]):',
               '        if df.get("readable") is True and not (_num(df.get("ratio")) and df["ratio"] <= T["K3"]["ratio_max"]):')]),
  [J + "test_each_row_fails_on_its_own_number_and_the_verdict_names_it"]),
 ("G9 the harness's exploration mode accepts a gate label",
  edit(SIM, [("        elif not isinstance(label, str) or not LABEL_RE.match(label):", "        elif not isinstance(label, str) or not (LABEL_RE.match(label) or GATE_LABEL_RE.match(label)):")]),
  [T + "test_b4_sim.Preflight.test_refusals_write_nothing", E + "test_refusals_write_nothing_and_the_derivation_is_never_reached"]),
 ("G10 the verifier treats a report that recorded self-validation findings as clean",
  edit(GV, [('    if doc["self_validation"] != {}:\n        F.add(bg.REPORT_JSON, "the report recorded self-validation findings: its judgement did not stand (never clean)")\n    elif _j(j["verdict"])',
             '    if _j(j["verdict"])')]),
  [E + "test_every_tamper_of_the_gate_report_is_named_with_the_digests_refreshed"]),
 ("G11 K5: a +inf Cohen's d is a failure",
  edit(GATE, [('d_ok = dspec == "+inf" or (', "d_ok = (")]),
  [J + "test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes"]),
 ("G12 the markdown rendering is not bound",
  edit(GV, [("        if disk[bg.REPORT_MD].read_bytes() != md:", "        if False:")]),
  [E + "test_every_tamper_of_the_gate_report_is_named_with_the_digests_refreshed"]),
 ("G13 an incomplete batch judged FAIL",
  edit(GATE, [('        return all_na(f"the batch is {status}: no pooled summary, nothing is judged", "not_assessable", f"the batch is {status}", status,',
               '        return all_na(f"the batch is {status}: no pooled summary, nothing is judged", "not_assessable", f"the batch is {status}", "FAIL" if status == "incomplete" else status,')]),
  [J + "test_an_invalid_or_incomplete_batch_is_that_verdict_with_nothing_judged", E + "test_an_invalid_and_an_incomplete_batch_are_those_verdicts"]),
 ("G14 the production run accepts another S than 200",
  edit(GATE, [("        if count != S_GATE:", "        if False:")]),
  [E + "test_refusals_write_nothing_and_the_derivation_is_never_reached", E + "test_the_cli_is_production_only_with_no_fixture_path"]),
 ("G15 K2's non-rejection threshold read as > 0.90 instead of >= 0.90",
  edit(GATE, [('nr_ok = _num(nr) and nr >= T["K2"]["x_minus_r_nonrejection_min"]', 'nr_ok = _num(nr) and nr > T["K2"]["x_minus_r_nonrejection_min"]')]),
  [J + "test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes"]),
 ("G16 K9 (a) read as > 0.90 instead of >= 0.90",
  edit(GATE, [('a_ok = _num(frac) and frac >= T["K9"]["seeds_with_all_seven_positive_controls_min"]', 'a_ok = _num(frac) and frac > T["K9"]["seeds_with_all_seven_positive_controls_min"]')]),
  [J + "test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes"]),
 ("G17 K10 read as > 0.50 instead of >= 0.50",
  edit(GATE, [('ok = _num(frac) and frac >= T["K10"]["interacting_seeds_over_S_min"]', 'ok = _num(frac) and frac > T["K10"]["interacting_seeds_over_S_min"]')]),
  [J + "test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes"]),
 ("G18 the verifier does not hold the archive's identity to the recorded one",
  edit(GV, [('''        if not (rep["label"] == b["label"] and rep["count"] == b["count"] and rep["fixture"] == b["fixture"] and rep["status"] == b["status"] and rep["head"] == b["head"] and rep["generated_utc"] == b["generated_utc"]):
            F.add("batch", "the archive's identity (label / count / fixture / status / HEAD / time) is not the recorded one")
''', "")]),
  [E + "test_every_tamper_of_the_gate_report_is_named_with_the_digests_refreshed"]),
 ("G19 judge_batch accepts an exploration-labelled archive",
  edit(GATE, [("    if not (GATE_LABEL_RE.match(label) or FIXTURE_LABEL_RE.match(label)):", "    if False:")]),
  [E + "test_refusals_write_nothing_and_the_derivation_is_never_reached"]),
 ("G20 a synthetic summary may carry a production or gate label",
  edit(GATE, [('    if not (isinstance(doc["label"], str) and FIXTURE_LABEL_RE.match(doc["label"])):', '    if not isinstance(doc["label"], str):')]),
  [J + "test_the_synthetic_summary_s_own_findings", E + "test_refusals_write_nothing_and_the_derivation_is_never_reached", E + "test_the_synthetic_evidence_is_bound_and_re_judged"]),
 ("G21 the summary contract does not check that B* is the cheapest eligible budget",
  edit(GATE, [('        if cb["value"] != want:', "        if False:")]),
  [J + "test_a_summary_that_breaks_its_contract_is_invalid_never_judged"]),
 ("G22 standing_for returns the exploration's text for a gate label",
  edit(SIM, [("    return STANDING_GATE if isinstance(label, str) and GATE_LABEL_RE.match(label) else STANDING", "    return STANDING")]),
  [J + "test_standing_for_the_harness_s_labels"]),
 ("G23 the production run accepts a label other than the pinned gate label",
  edit(GATE, [("        if label != PINNED_GATE_LABEL:", "        if False:")]),
  [E + "test_refusals_write_nothing_and_the_derivation_is_never_reached", E + "test_the_cli_is_production_only_with_no_fixture_path"]),
 ("G24 the report validator accepts a PASS verdict beside a failing row",
  edit(GATE, [('''            if not (br["status"] == "PASS" and all(x == "PASS" for x in statuses)):
                f.append("verdict PASS with the budget rule or a row not PASS")
''', "")]),
  [E + "test_every_tamper_of_the_gate_report_is_named_with_the_digests_refreshed"]),
 ("G25 K7 (b) read as > 11 instead of >= 11",
  edit(GATE, [('b_ok = _num(m) and m >= T["K7"]["o_prefix_median_not_unknown_min"]', 'b_ok = _num(m) and m > T["K7"]["o_prefix_median_not_unknown_min"]')]),
  [J + "test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes"]),
 ("G26 K4's ceiling margin read as < 57.6 instead of <= 57.6",
  edit(GATE, [('k4["median_best_Omega"] <= T["K4"]["omega_median_max"]', 'k4["median_best_Omega"] < T["K4"]["omega_median_max"]')]),
  [J + "test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes"]),
 ("G27 K5's power read as > 0.90 instead of >= 0.90",
  edit(GATE, [('p_ok = _num(power) and power >= T["K5"]["power_min"]', 'p_ok = _num(power) and power > T["K5"]["power_min"]')]),
  [J + "test_the_boundaries_written_with_an_equal_sign_pass_and_an_infinite_d_passes"]),
 ("G28 the verifier does not re-hash the batch's sim_report.json",
  edit(GV, [('        if _sha(raw) != b["sha256"]:\n            F.add("batch", "sim_report.json does not hash to the recorded digest")\n', "")]),
  [E + "test_every_tamper_of_the_gate_report_is_named_with_the_digests_refreshed"]),
 ("G29 the verdict can be PASS although a row is not assessable",
  edit(GATE, [('    if not fails and not na and out["budget_rule"]["status"] == "PASS":', '    if not fails and out["budget_rule"]["status"] == "PASS":')]),
  [J + "test_no_b_star_leaves_the_dependent_rows_not_assessable_and_the_gate_cannot_pass"]),
]


def run(tree, tests):
    p = subprocess.run([sys.executable, "-B", "-m", "unittest", *tests], cwd=tree, capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"Ran (\d+) tests?", out)
    ran = int(m.group(1)) if m else 0
    failed = [x for x in re.findall(r"^(?:FAIL|ERROR): (\S+)", out, re.M)]
    status = "FAILED" if (p.returncode != 0 and ran > 0) else ("OK" if p.returncode == 0 else "NO-RUN")
    return ran, status, failed, out


def main(only=None):
    lines = []
    t0 = time.time()
    chosen = [m for m in MUTANTS if only is None or m[0].split()[0] in only]
    for name, apply, tests in chosen:
        with tempfile.TemporaryDirectory(prefix="b4gmut_") as tmp:
            tree = pathlib.Path(tmp)
            for rel in COPY:
                src = R / rel
                dst = tree / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
            base_ran, base_status, _, _ = run(tree, tests)
            if base_status != "OK" or base_ran == 0:
                lines.append(f"BASELINE-NOT-GREEN  {name}  [Ran {base_ran}, {base_status}]"); print(lines[-1], flush=True); continue
            try:
                apply(tree)
            except EditMiss as exc:
                lines.append(f"EDIT-MISS  {name}  [{exc}]"); print(lines[-1], flush=True); continue
            ran, status, failed, out = run(tree, tests)
            verdict = "KILLED" if (status == "FAILED" and ran > 0) else "SURVIVED"
            short = sorted({f.split(".")[-1] if "(" not in f else f.split(" ")[0] for f in failed})
            lines.append(f"{verdict}  {name}  [Ran {ran}, {status}]  {short}")
            print(lines[-1], flush=True)
    lines.append(f"# {sum(1 for l in lines if l.startswith('KILLED'))} / {len(chosen)} killed ({len(MUTANTS)} defined); {time.time() - t0:.0f} s")
    print(lines[-1])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    # usage: b4_gate_mutants.py [<out.txt> [G1,G2,...]]
    text = main(set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None)
    out = sys.argv[1] if len(sys.argv) > 1 else None
    if out:
        pathlib.Path(out).write_text(text)
