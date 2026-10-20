#!/usr/bin/env python3
"""Mutants of the protocol v0.2.0 tool unit: hermetic tree copies; a kill only with Ran N > 0 and FAILED, the failing tests named
(the owner's proportionality ruling of 2026-10-20, rule 1: EDIT-MISS, BASELINE-NOT-GREEN and Ran 0 never count as killed). The copy carries
b4/, the pinned host modules the tests compare against by import, the formal inputs, the 38 exclusion sources, the architecture document
and the top files of the two committed v0.1.16 archives (read-only references of the refusal tests) — no other evidence. Each mutant
breaks ONE contract of the v0.2.0 tool (task-v0.2, the target setup and its persistence, the PublicTask boundary, K9's two
applicabilities, the go / no-go policy, the protocol identity and the version refusal, the consumed labels), and the tests it names are
run inside the copy. NO PRODUCTION SET IS DERIVED: the tests guard b4_seeds.master_seed / pair_seeds and run on hermetic roots.
The import table of the copy is refreshed after the mutation so that the identity's inventory check does not mask the contract
under test (an unrefreshed table would make every mutant a trivial IdentityRefusal); M20 tests the inventory check itself."""
import hashlib, json, re, shutil, subprocess, sys, tempfile, pathlib, time


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
GATE1 = "evidence/b4/sim/b4-gate-1_20261020T102526Z"
GATE1_DIR = "evidence/b4/gate/b4-gate-1_20261020T102526Z"
COPY = ["b4", "host/b1_carto.py", "host/b1_model.py", "host/b2_landscape.py", "host/b2_maps.py", "host/b2_gate.py", "host/b2_search.py", "docs/b4_architecture.md", "docs/ff_latch_probe.md",
        "gate_runs/run_2026_08_05_ff/certificate.json", "evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json",
        bs.EXPOSURE_RECEIPT_REL, f"{SIM3}/seeds.json", f"{SIM3}/manifest.json", f"{SIM3}/sim_report.json", f"{GATE1}/seeds.json", f"{GATE1}/manifest.json", f"{GATE1}/sim_report.json",
        f"{GATE1_DIR}/gate_report.json", f"{GATE1_DIR}/gate_report.md"] + [f[0] for f in bs.FIELDS]
LAND, TGT, EXEC, ENG, REP, K9, SIM, SCH, VER, GATE, GV, GG, PROT, SEEDS, TH = ("b4/host/b4_landscape.py", "b4/host/b4_target.py", "b4/host/b4_execution.py", "b4/host/b4_engine.py",
                                                                           "b4/host/b4_replay.py", "b4/host/b4_k9.py", "b4/host/b4_sim.py", "b4/host/b4_sim_schema.py", "b4/host/b4_sim_verify.py",
                                                                           "b4/host/b4_gate.py", "b4/host/b4_gate_verify.py", "b4/host/b4_gonogo.py", "b4/host/b4_protocol.py", "b4/host/b4_seeds.py",
                                                                           "b4/host/b4_thresholds.py")
T = "b4.tests."


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
 ("M1 the private plan is persisted AFTER the first target call",
  edit(SIM, [('''        digests = {"task_setup.json": self.write(f"pair_{r:03d}/task_setup.json", setup, sc.task_setup_findings)["sha256"]}
        plan["task"] = "in_progress"
        port = self.port_factory(fabric, SETUP_ROLE, r)
        parts = bl.public_parts(l)
        recs: dict[str, dict] = {}
        for phase, stim, name in (("target", parts["stimulus"], "target_search.json"), ("target_holdout", parts["holdout_stimulus"], "target_holdout.json")):
            self.dl.check()                                                     # a deadline here is `incomplete` with what was written kept
            try:
                rec = bt.observe_target(port, setup["planted_genome"], stim, mapping.addresses, phase)''',
             '''        digests = {}
        plan["task"] = "in_progress"
        port = self.port_factory(fabric, SETUP_ROLE, r)
        parts = bl.public_parts(l)
        recs: dict[str, dict] = {}
        for phase, stim, name in (("target", parts["stimulus"], "target_search.json"), ("target_holdout", parts["holdout_stimulus"], "target_holdout.json")):
            self.dl.check()                                                     # a deadline here is `incomplete` with what was written kept
            try:
                rec = bt.observe_target(port, setup["planted_genome"], stim, mapping.addresses, phase)
                if "task_setup.json" not in digests:
                    digests["task_setup.json"] = self.write(f"pair_{r:03d}/task_setup.json", setup, sc.task_setup_findings)["sha256"]''')]),
  [T + "test_b4_sim.InvalidStops.test_a_domain_at_the_target_setup_is_target_invalid_with_the_plan_kept"]),
 ("M2 the first setup observation is not saved before the second call",
  edit(SIM, [('''            digests[name] = self.write(f"pair_{r:03d}/{name}", doc, lambda d, ph=phase: sc.target_observation_findings(d, ph))["sha256"]   # saved at once, before the next call
            recs[phase] = doc
            plan["task"] = "partial"''',
             '''            recs[phase] = doc
            plan["task"] = "partial"
        for phase, name in (("target", "target_search.json"), ("target_holdout", "target_holdout.json")):
            digests[name] = self.write(f"pair_{r:03d}/{name}", recs[phase], lambda d, ph=phase: sc.target_observation_findings(d, ph))["sha256"]''')]),
  [T + "test_b4_sim.IncompleteStops.test_an_interrupt_or_the_deadline_between_the_two_setup_observations_keeps_the_first"]),
 ("M3 the planted configuration's storage_kind bit is not fixed to flip-flop",
  edit(LAND, [('''    free = [b for b in range(n_bits) if b != storage_kind_bit]''', '''    free = [b for b in range(n_bits) if b != (storage_kind_bit + 1) % n_bits]''')]),
  [T + "test_b4_landscape.TheGenerator.test_the_planted_rule_by_hand", T + "test_b4_target.ThePlan.test_the_plan_is_the_seed_s_the_rule_s_and_the_mapping_s"]),
 ("M4 a zero draw (the base) is redrawn",
  edit(LAND, [('''    draw = Rng((seed ^ SALT_TARGET) & 0xFFFFFFFF).uniform(1 << (n_bits - 1))''',
              '''    rng = Rng((seed ^ SALT_TARGET) & 0xFFFFFFFF)
    draw = rng.uniform(1 << (n_bits - 1))
    while draw == 0:
        draw = rng.uniform(1 << (n_bits - 1)) or 1''')]),
  [T + "test_b4_landscape.TheGenerator.test_the_planted_rule_by_hand"]),
 ("M5 a None in a planted trace is read as 0 (the mask narrowed by silence)",
  edit(LAND, [('''        if q is None:
            raise TargetRefusal(f"the planted configuration reads None at step {s}, element {e}: not a target under T-i (invalid, not narrowed)")''',
              '''        if q is None:
            q = 0''')]),
  [T + "test_b4_landscape.TheGenerator.test_the_targets_are_read_from_the_planted_trace_and_a_none_is_refused", T + "test_b4_target.ThePlan.test_a_none_in_a_planted_trace_is_refused_never_narrowed"]),
 ("M6 the task digest does not cover the target's source commitment",
  edit(EXEC, [('''"holdout_target": list(self.holdout_target), "holdout_weights": list(self.holdout_weights), "target_source_sha256": self.target_source_sha256})''',
              '''"holdout_target": list(self.holdout_target), "holdout_weights": list(self.holdout_weights)})''')]),
  [T + "test_b4_landscape.TheGenerator.test_the_public_task_carries_no_seed_and_its_digest_covers_the_source_commitment"]),
 ("M7 the harness smuggles the landscape seed into the public task's label",
  edit(TGT, [('''    return bl.make_task(tuple(plan_doc["addresses"]), parts, target, holdout_target, target_source_sha256(rec_search, rec_holdout))''',
             '''    return bl.make_task(tuple(plan_doc["addresses"]), parts, target, holdout_target, target_source_sha256(rec_search, rec_holdout), label=f"b4-task-{plan_doc['landscape_seed']}")''')]),
  [T + "test_b4_sim.CompleteBatch.test_the_task_setup_files_the_planted_target_and_the_arms_task"]),
 ("M8 K9's conditional applicability ignores the SR mode (equals the all-panel rule)",
  edit(K9, [('''        cond = bool(base["applicable"] and sr[0] and sr[1])''', '''        cond = bool(base["applicable"])''')]),
  [T + "test_b4_k9.ThePanel.test_applicability_denominators_by_hand_and_from_the_configuration", T + "test_b4_k9.TheComputation.test_the_formal_model_end_to_end_on_an_exposed_seed"]),
 ("M9 the conditional rule adds pairs the all-panel rule excluded",
  edit(K9, [('''        cond = bool(base["applicable"] and sr[0] and sr[1])''', '''        cond = bool(sr[0] and sr[1])''')]),
  [T + "test_b4_k9.ThePanel.test_applicability_denominators_by_hand_and_from_the_configuration"]),
 ("M10 the judged record is the all-panel one",
  edit(K9, [('''    return {"judged_estimand": JUDGED_ESTIMAND, "per_semantic": cond_sem, "per_address": cond_addr, "uncovered_applicable_pairs": cond_unc,''',
             '''    return {"judged_estimand": JUDGED_ESTIMAND, "per_semantic": all_sem, "per_address": cond_addr, "uncovered_applicable_pairs": cond_unc,''')]),
  [T + "test_b4_k9.TheComputation.test_the_formal_model_end_to_end_on_an_exposed_seed"]),
 ("M11 the pooled summary's judged K9 block is computed from the all-panel rows",
  edit(SIM, [('''    k9s, k9s_all = k9_block("k9"), k9_block("k9_all_panel")''', '''    k9s, k9s_all = k9_block("k9_all_panel"), k9_block("k9_all_panel")''')]),
  [T + "test_b4_sim.TheSummaryAndTheValidators.test_on_hand_rows_including_an_infinite_cohen_d"]),
 ("M12 the gate's K9 row judges the all-panel medians",
  edit(GATE, [('''        rec = k["per_semantic"][sem]
        m = rec["median_coverage_over_all_S"]
        per[sem] = {"median_coverage_over_all_S": m,''', '''        rec = k["per_semantic_all_panel"][sem]
        m = rec["median_coverage_over_all_S"]
        per[sem] = {"median_coverage_over_all_S": m,''')]),
  [T + "test_b4_gate.TheJudge.test_k9_judges_the_conditional_record_and_carries_the_all_panel_one_beside_it"]),
 ("M13 the summary contract accepts a K9 block without the all-panel record",
  edit(GATE, [('''    if _exact(k9s, {"judged_estimand", "per_semantic", "per_semantic_all_panel", "seeds_with_all_seven_positive_controls", "fraction_of_S"}, f, "k9"):''',
               '''    if isinstance(k9s, dict) and {"judged_estimand", "per_semantic", "seeds_with_all_seven_positive_controls", "fraction_of_S"} <= set(k9s) and (k9s.setdefault("per_semantic_all_panel", k9s["per_semantic"]) or True):''')]),
  [T + "test_b4_gate.TheJudge.test_k9_judges_the_conditional_record_and_carries_the_all_panel_one_beside_it"]),
 ("M14 the go / no-go policy's alpha read as 0.5",
  edit(GG, [('''    p_ok = _num(om["sign_test_p"]) and om["sign_test_p"] <= T["alpha_go"]''', '''    p_ok = _num(om["sign_test_p"]) and om["sign_test_p"] <= 0.5''')]),
  [T + "test_b4_gonogo.ThePolicy.test_each_condition_fails_on_its_own_number_and_the_boundaries"]),
 ("M15 the go / no-go policy drops positives > negatives",
  edit(GG, [('''    pos_ok = om["positives"] > om["negatives"]''', '''    pos_ok = True''')]),
  [T + "test_b4_gonogo.ThePolicy.test_each_condition_fails_on_its_own_number_and_the_boundaries"]),
 ("M16 the go / no-go precondition ignores S",
  edit(GG, [('''"S_is_32": report["count"] == T["S"],''', '''"S_is_32": True,''')]),
  [T + "test_b4_gonogo.ThePolicy.test_no_decision_when_the_precondition_is_not_met_and_nothing_is_interpreted", T + "test_b4_gonogo.EndToEnd.test_a_fixture_batch_of_two_pairs_is_no_decision_written_verified_and_never_of_record"]),
 ("M17 the go / no-go policy's K9 statistic reads the all-panel medians",
  edit(GG, [('''    med = {sem: s["k9"]["per_semantic"][sem]["median_coverage_over_all_S"] for sem in k9.SEMANTICS}''',
             '''    med = {sem: s["k9"]["per_semantic_all_panel"][sem]["median_coverage_over_all_S"] for sem in k9.SEMANTICS}''')]),
  [T + "test_b4_gonogo.ThePolicy.test_each_condition_fails_on_its_own_number_and_the_boundaries"]),
 ("M18 the document's revision enters the protocol digest",
  edit(PROT, [('''INFORMATIONAL = ("architecture_revision",)''', '''INFORMATIONAL = ()''')]),
  [T + "test_b4_protocol.TheIdentity.test_it_is_deterministic_complete_and_excludes_the_document_revision_from_the_digest", T + "test_b4_thresholds.ThePins.test_the_document_version_is_informational_outside_the_table_and_outside_the_method_digest"]),
 ("M19 the thresholds digest includes the table's source text",
  edit(PROT, [('''    t.pop("source", None)''', '''    pass''')]),
  [T + "test_b4_protocol.TheIdentity.test_it_is_deterministic_complete_and_excludes_the_document_revision_from_the_digest", T + "test_b4_thresholds.ThePins.test_the_document_version_is_informational_outside_the_table_and_outside_the_method_digest"]),
 ("M20 the inventory is not held to the import table",
  edit(PROT, [('''        if not isinstance(entry, dict) or entry.get("sha256") != got:''', '''        if False:''')]),
  [T + "test_b4_protocol.TheIdentity.test_a_tree_that_is_not_its_inventory_is_refused_by_name"]),
 ("M21 the identity comparison skips a component",
  edit(PROT, [('''    for k in sorted(set(digest_view(archived)) | set(digest_view(rebuilt))):''', '''    for k in sorted((set(digest_view(archived)) | set(digest_view(rebuilt))) - {"k9", "task"}):''')]),
  [T + "test_b4_protocol.TheIdentity.test_the_comparison_names_the_differing_components", T + "test_b4_sim.TheArchiveVerifier.test_the_setup_records_are_bound_and_every_tamper_is_named"]),
 ("M22 the archive verifier skips the identity gate",
  edit(VER, [('''    if not isinstance(pr, dict) or "identity" not in pr:
        F.add("protocol", bp.refusal_for_missing(man0 if isinstance(man0, dict) else {})); return F.d''', '''    if False:
        pass''')]),
  [T + "test_b4_sim.TheArchiveVerifier.test_the_setup_records_are_bound_and_every_tamper_is_named"]),
 ("M23 the archive verifier does not reconstruct the task setup from the kept records",
  edit(VER, [('''            F.add(pre + "task setup", *bt.setup_findings(sd["task_setup.json"], sd.get("target_search.json"), sd.get("target_holdout.json"), sd.get("task.json"), mapping, formal_prov,
                                                        {"pair": r, "landscape_seed": plan["landscape_seed"], "operator_seed": plan["operator_seed"]}))''', '''            pass''')]),
  [T + "test_b4_sim.TheArchiveVerifier.test_the_setup_records_are_bound_and_every_tamper_is_named"]),
 ("M24 the gate judges an archive of another version",
  edit(GATE, [('''    pf = archive_identity_findings(batch_dir)                          # FIRST: an archive of another method version (or none) is never judged by this tool
    if pf:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"{rel}: " + "; ".join(pf[:2])}''', '''    pf = []''')]),
  [T + "test_b4_gate.TheJudge.test_the_committed_v0_1_16_archives_are_another_method_version_never_judged_here"]),
 ("M25 the gate verifier does not compare the judgement's identity",
  edit(GV, [('''    if doc["identity"]["protocol_sha256"] != mine:''', '''    if False:''')]),
  [T + "test_b4_gate.EndToEnd.test_every_tamper_of_the_gate_report_is_named_with_the_digests_refreshed"]),
 ("M26 a consumed label is derived again",
  edit(SEEDS, [('''    if label in CONSUMED_LABELS:
        raise ConsumedLabelRefusal(''', '''    if False:
        raise ConsumedLabelRefusal(''')]),
  [T + "test_b4_seeds.TheExposureReceipt.test_retired_labels_are_refused_before_a_master_and_still_read_from_the_registry", T + "test_b4_sim.Preflight.test_a_retired_label_is_refused_before_the_tree_is_read"]),
 ("M27 the gate runs under the consumed label b4-gate-1",
  edit(GATE, [('''        if label in bs.CONSUMED_LABELS or label in bs.RETIRED_LABELS:''', '''        if label in bs.RETIRED_LABELS:''')]),
  [T + "test_b4_gate.EndToEnd.test_refusals_write_nothing_and_the_derivation_is_never_reached"]),
 ("M28 the non-triviality record is invented (always true)",
  edit(SIM, [('''            "target_equals_R_base_search_trace": r_base_grid is not None and ex.sha256_json(r_base_grid) == ex.sha256_json(target_search_grid), "written_utc": utc()}''',
             '''            "target_equals_R_base_search_trace": True, "written_utc": utc()}''')]),
  [T + "test_b4_sim.CompleteBatch.test_the_task_setup_files_the_planted_target_and_the_arms_task"]),
 ("M29 a setup port called more than twice is not named",
  edit(SIM, [('''        if port.calls != sum(bt.SETUP_COST.values()):''', '''        if False:''')]),
  [T + "test_b4_sim.InvalidStops.test_a_setup_that_observes_more_than_twice_is_named"]),
 ("M30 a DOMAIN at the setup is recorded as an ordinary domain stop",
  edit(SIM, [('''                raise Invalid("target_invalid", f"the target setup observation ({phase}) of the planted configuration was refused: DOMAIN — a contract break, never a redraw", role=SETUP_ROLE, stage="target_setup")''',
             '''                raise Invalid("domain", f"the target setup observation ({phase}) of the planted configuration was refused: DOMAIN — a contract break, never a redraw", role=SETUP_ROLE, stage="target_setup")''')]),
  [T + "test_b4_sim.InvalidStops.test_a_domain_at_the_target_setup_is_target_invalid_with_the_plan_kept"]),
 ("M31 the task state does not advance when the first setup observation is persisted (stays in_progress)",
  edit(SIM, [('''            recs[phase] = doc
            plan["task"] = "partial"''', '''            recs[phase] = doc''')]),
  [T + "test_b4_sim.IncompleteStops.test_an_interrupt_or_the_deadline_between_the_two_setup_observations_keeps_the_first", T + "test_b4_sim.InvalidStops.test_a_domain_at_the_target_setup_is_target_invalid_with_the_plan_kept"]),
 ("M32 the task validator does not hold the planted scores to the ceilings",
  edit(SCH, [('''        elif v["fitness"] != ceiling or v["none_cells"] != 0:
            f.append(f"{k}: the planted configuration reaches its own ceiling with no None (T-i: a None would have refused the target)")''', '''        elif False:
            pass''')]),
  [T + "test_b4_target.ThePlan.test_the_task_is_rebuilt_from_the_records_and_the_planted_configuration_scores_its_ceilings"]),
 ("M33 the replay does not hold the terminal event's task digest",
  edit(REP, [('''        if (t["task_digest"], t["operator_seed"], t["budget"]) != (r["task_digest"], r["operator_seed"], r["budget"]):''', '''        if (t["operator_seed"], t["budget"]) != (r["operator_seed"], r["budget"]):''')]),
  [T + "test_b4_replay.Replay.test_the_owner_s_nine_tampers_are_named"]),
 ("M34 a drift between the two setup observations is accepted",
  edit(SIM, [('''            if recs and rec["provenance_sha256"] != recs["target"]["provenance_sha256"]:''', '''            if False:''')]),
  [T + "test_b4_sim.InvalidStops.test_a_source_drift_inside_the_setup_and_a_setup_port_that_calls_more_than_twice"]),
 ("M35 the planned record's validator lets an arm start without a complete task setup",
  edit(SCH, [('''        if p["task"] != "complete" and (any(v != "not_started" for v in p["arms"].values()) or any(p[k] != "not_started" for k in ("k7", "k9", "k10"))):
            f.append(f"planned[{i}]: an arm or a diagnostic started without a complete task setup"); return''', '''        pass''')]),
  [T + "test_b4_sim.TheSummaryAndTheValidators.test_a_summary_with_a_verdict_key_is_refused_by_the_report_validator"]),
 ("M36 the pinned labels of the table are the consumed ones",
  edit(TH, [('''"gate_label": "b4-gate-2", "exploration_label": "b4-sim-4",''', '''"gate_label": "b4-gate-1", "exploration_label": "b4-sim-3",''')]),
  [T + "test_b4_thresholds.ThePins.test_the_numbers_are_the_document_s", T + "test_b4_thresholds.ThePins.test_every_pinned_text_is_in_its_row"]),
]


def refresh_table(tree: pathlib.Path) -> None:
    """The mutated copy's import table refreshed to the copy's bytes (so that the identity's inventory check tests nothing but itself in M20)."""
    tab = json.loads((tree / "b4/IMPORT.json").read_text())
    for rel, e in tab["files"].items():
        p = tree / rel
        if p.is_file():
            e["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    (tree / "b4/IMPORT.json").write_text(json.dumps(tab, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


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
        with tempfile.TemporaryDirectory(prefix="b4v02mut_") as tmp:
            tree = pathlib.Path(tmp)
            for rel in COPY:
                src = R / rel
                dst = tree / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
            subprocess.run(["git", "init", "-q"], cwd=tree, check=True)
            base_ran, base_status, _, _ = run(tree, tests)
            if base_status != "OK" or base_ran == 0:
                lines.append(f"BASELINE-NOT-GREEN  {name}  [Ran {base_ran}, {base_status}]"); print(lines[-1], flush=True); continue
            try:
                apply(tree)
            except EditMiss as exc:
                lines.append(f"EDIT-MISS  {name}  [{exc}]"); print(lines[-1], flush=True); continue
            if name.split()[0] != "M20":
                refresh_table(tree)
            ran, status, failed, out = run(tree, tests)
            verdict = "KILLED" if (status == "FAILED" and ran > 0) else "SURVIVED"
            short = sorted({f.split(".")[-1] if "(" not in f else f.split(" ")[0] for f in failed})
            lines.append(f"{verdict}  {name}  [Ran {ran}, {status}]  {short}")
            print(lines[-1], flush=True)
    lines.append(f"# {sum(1 for l in lines if l.startswith('KILLED'))} / {len(chosen)} killed ({len(MUTANTS)} defined); {time.time() - t0:.0f} s")
    print(lines[-1])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    # usage: b4_v02_mutants.py [<out.txt> [M1,M2,...]]
    text = main(set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None)
    out = sys.argv[1] if len(sys.argv) > 1 else None
    if out:
        pathlib.Path(out).write_text(text)
