#!/usr/bin/env python3
"""Mutants for unit 2b-4a (hermetic tree copies; a kill only with Ran N > 0 and FAILED, the failing tests named).
The copy carries b4/, the three pinned host modules the tests compare against by import, the formal inputs the loaders
re-hash, the 38 exclusion sources and the architecture document — no other evidence. Each mutant breaks ONE contract the
owner's ruling (2026-10-18, section 4.3) names, and the tests it names are run inside the copy."""
import json, re, shutil, subprocess, sys, tempfile, pathlib, time
def _repo_root() -> pathlib.Path:
    """The repository root: the first ancestor of the working directory (then of this file) holding b4/host/b4_seeds.py.
    Fails loudly instead of walking past / forever."""
    for start in (pathlib.Path.cwd(), pathlib.Path(__file__).resolve().parent):
        for cand in (start, *start.parents):
            if (cand / "b4/host/b4_seeds.py").is_file():
                return cand
    raise SystemExit("run from inside the zynq_fabricmap repository: no ancestor holds b4/host/b4_seeds.py")


R = _repo_root()
sys.path.insert(0, str(R / "b4/host"))
import b4_seeds as bs  # noqa: E402

COPY = ["b4", "host/b1_carto.py", "host/b1_model.py", "host/b2_landscape.py", "host/b2_maps.py", "host/b2_gate.py", "host/b2_search.py", "docs/b4_architecture.md", "docs/ff_latch_probe.md",
        "gate_runs/run_2026_08_05_ff/certificate.json", "evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json"] + [f[0] for f in bs.FIELDS]
SEEDS, CTL, SNAP, K9, K10, SIM, SCH, GS, TH, VER = ("b4/host/b4_seeds.py", "b4/host/b4_controls.py", "b4/host/b4_snapshot.py", "b4/host/b4_k9.py", "b4/host/b4_k10.py",
                                                    "b4/host/b4_sim.py", "b4/host/b4_sim_schema.py", "b4/host/b4_gate_stats.py", "b4/host/b4_thresholds.py", "b4/host/b4_sim_verify.py")
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


def multi(*applies):
    def apply(tree):
        for a in applies:
            a(tree)
    return apply


MUTANTS = [
 ("M1 the archived exploration sets are not pooled (evidence/b4/sim/*/seeds.json ignored)",
  edit(SEEDS, [("    for r in registry:\n        pooled.update(r.values)\n", "    for r in registry:\n        pass\n")]),
  [T + "test_b4_seeds.TheRegistry.test_every_archived_set_is_read_whatever_its_outcome", T + "test_b4_seeds.TheRegistry.test_a_fixture_set_in_the_registry_is_read_without_a_master"]),
 ("M2 a run directory with no seed record is skipped instead of refused",
  edit(SEEDS, [('            raise ExclusionSourceRefusal(f"{rel}: neither {SEEDS_FILE} nor {INIT_FAILED_FILE}; a run directory with no seed record is refused, never skipped")', "            continue")]),
  [T + "test_b4_seeds.TheRegistry.test_a_damaged_or_missing_seed_record_is_refused_never_skipped"]),
 ("M3 the pooled set screens the landscape position only",
  edit(SEEDS, [("        if l_seed in seen or o_seed in seen or l_seed == o_seed:", "        if l_seed in seen or l_seed == o_seed:")]),
  [T + "test_b4_seeds.ThePairs.test_the_copy_is_b2_s_pair_seeds", T + "test_b4_seeds.ThePairs.test_the_pooled_set_screens_both_positions"]),
 ("M4 a re-hashed historical source only warns",
  edit(SEEDS, [('        raise ExclusionSourceRefusal(f"{rel}: hashes to {got[:16]}…, not the recorded {expected_sha256[:16]}…")', "        pass")]),
  [T + "test_b4_seeds.TheHistoricalSources.test_a_rehashed_or_missing_source_is_refused_by_name"]),
 ("M5 f_frozen_view skips the replay",
  edit(CTL, [('    findings = br.replay(result, task)\n    _require(not findings, "the F record does not replay: " + "; ".join(findings[:5]))\n', "")]),
  [T + "test_b4_controls.FrozenView.test_a_tampered_record_is_refused"]),
 ("M6 D built from the oracle view instead of F's rebuilt map",
  edit(CTL, [("    fv = f_frozen_view(f_result, task)\n    seed = d_shuffle_seed", "    fv = bc.oracle_view(__import__('b4_ff_mapping').site_mapping())\n    seed = d_shuffle_seed")]),
  [T + "test_b4_controls.ControlD.test_d_is_the_seeded_relabelling_of_f_s_view_with_its_parent_kept"]),
 ("M7 the D shuffle seed drawn from the operator seed (not its own generator)",
  edit(CTL, [('    return _control_seed(D_LABEL, landscape_seed, operator_seed)', '    return _seed_int(operator_seed, "operator_seed")')]),
  [T + "test_b4_controls.ControlSeeds.test_the_two_formulas_by_hand"]),
 ("M8 K7's prefix takes B records (the base dropped: off by one)",
  edit(SNAP, [("    records = ledger[:budget + 1]", "    records = ledger[1:budget + 1]"), ('    if len(records) != budget + 1:', '    if len(records) != budget:'),
              ('    elif [e["phase"] for e in records] != ["base"] + ["search"] * budget:', '    elif [e["phase"] for e in records] != ["search"] * budget:'),
              ("    r = rebuild(result, task, upto=budget + 1)", "    r = rebuild(result, task, upto=budget)")]),
  [T + "test_b4_snapshot.HandLedger.test_the_prefix_states_by_hand", T + "test_b4_snapshot.RealRuns.test_o_s_prefix_at_every_grid_budget_up_to_its_evals"]),
 ("M9 F's search records fed to the cartographer as if the map kept learning",
  edit(SNAP, [('        learned = [e for e in ledger if e["phase"] in ("base", "probe")]', '        learned = [e for e in ledger if e["phase"] in ("base", "probe", "search")]')]),
  [T + "test_b4_snapshot.RealRuns.test_every_arm_mode_rebuilds_without_a_finding"]),
 ("M10 X's cartographer rebuilt from the TRUE genome (not relabelled)",
  edit(SNAP, [('            _ingest_checked(carto, e, bc.relabel_genome(e["genome"], perm), findings)', '            _ingest_checked(carto, e, e["genome"], findings)')]),
  [T + "test_b4_snapshot.RealRuns.test_every_arm_mode_rebuilds_without_a_finding"]),
 ("M11 K7 (a) checks only the last record's commitment",
  edit(SNAP, [('    if (e["map_version_after"], e["map_commitment_after"]) != (carto.version, carto.commitment()):\n        findings.append(f"seq {e[\'seq\']}: the recorded map version / commitment after is not the rebuilt one")',
               '    pass')]),
  [T + "test_b4_snapshot.HandLedger.test_a_tampered_middle_record_is_found_where_it_lies"]),
 ("M12 K9: a pair whose two traces are identical is dropped from the denominator",
  edit(K9, [('            rec.update(obs0=id0, obs1=id1, hit0=hit0, hit1=hit1, differences=diffs, covered=bool(diffs))',
             '            rec.update(obs0=id0, obs1=id1, hit0=hit0, hit1=hit1, differences=diffs, covered=bool(diffs) if diffs else None, applicable=bool(diffs))')]),
  [T + "test_b4_k9.TheComputation.test_the_formal_model_end_to_end_on_an_exposed_seed"]),
 ("M13 K9: ff_init left out of the seven (never a positive control)",
  edit(K9, [('        c["positive_control"] = c["covered"] > 0', '        c["positive_control"] = c["covered"] > 0 and s != "ff_init"')]),
  [T + "test_b4_k9.TheComputation.test_the_formal_model_end_to_end_on_an_exposed_seed", T + "test_b4_k9.TheComputation.test_recompute_names_a_tampered_record",
   T + "test_b4_k9.TheComputation.test_summarise_by_hand_an_empty_denominator_is_not_assessable_and_never_a_positive_control"]),
 ("M14 K9: an empty denominator recorded as 100 %",
  edit(K9, [('        c["fraction"] = (c["covered"] / c["applicable"]) if c["applicable"] else None\n        c["assessable"] = c["applicable"] > 0',
             '        c["fraction"] = (c["covered"] / c["applicable"]) if c["applicable"] else 1.0\n        c["assessable"] = True')]),
  [T + "test_b4_k9.TheComputation.test_recompute_names_a_tampered_record", T + "test_b4_sim.TheSummaryAndTheValidators.test_on_hand_rows_including_an_infinite_cohen_d",
   T + "test_b4_k9.TheComputation.test_summarise_by_hand_an_empty_denominator_is_not_assessable_and_never_a_positive_control"]),
 ("M15 K9 ignores the deadline check",
  edit(K9, [("        if check is not None:\n            try:\n                check()\n            except StopWork as exc:\n                stopped = {\"before_pair_index\": i, \"reason\": str(exc)}\n                break\n", "")]),
  [T + "test_b4_k9.TheComputation.test_the_deadline_stops_between_pairs_and_the_partial_is_kept", T + "test_b4_sim.IncompleteStops.test_the_deadline_inside_k9"]),
 ("M16 K10's driver absorbs a comparable = False return as 'not comparable' and continues",
  edit(K10, [("            raise CornerRefused(genome, exc) from exc            # four_corner does not catch this: no further corner is observed", "            raise")]),
  [T + "test_b4_k10.TheComputation.test_no_corner_is_observed_after_the_first_refused_one", T + "test_b4_sim.InvalidStops.test_a_control_failure_a_replay_finding_and_a_k10_domain"]),
 ("M17 K10's second background drawn from the generator's SECOND call",
  edit(K10, [("    return [0, rng.uniform(1 << 21)]", "    rng.uniform(1 << 21)\n    return [0, rng.uniform(1 << 21)]")]),
  [T + "test_b4_k10.Backgrounds.test_by_hand_from_the_salted_generator_s_first_call"]),
 ("M18 the statistics stage ignores the deadline",
  edit(SIM, [("        self.summary, self.stats_record = summarise_batch(self.rows, self.c[\"count\"], check=self.dl.check)", "        self.summary, self.stats_record = summarise_batch(self.rows, self.c[\"count\"], check=None)")]),
  [T + "test_b4_sim.IncompleteStops.test_the_deadline_in_the_statistics_and_an_interrupt"]),
 ("M19 after an invalid audit the harness goes on to the next pair",
  edit(SIM, [("        for r in range(count):\n            batch.run_pair(r)\n", "        for r in range(count):\n            try:\n                batch.run_pair(r)\n            except Invalid:\n                continue\n")]),
  [T + "test_b4_sim.InvalidStops.test_domain_in_the_second_pair_s_o_arm", T + "test_b4_sim.InvalidStops.test_a_control_failure_a_replay_finding_and_a_k10_domain"]),
 ("M20 the arm result is written only after the audit",
  edit(SIM, [('            self.write(f"pair_{r:03d}/arm_{role}.result.json", doc, None)\n            plan["arms"][role] = "written"\n            results[role] = d\n            self.dl.check()\n            completion = completion_findings(d, role, task, port.calls, views.get(role))\n            replay = br.replay(d, task)\n',
              '            results[role] = d\n            self.dl.check()\n            completion = completion_findings(d, role, task, port.calls, views.get(role))\n            replay = br.replay(d, task)\n            self.write(f"pair_{r:03d}/arm_{role}.result.json", doc, None)\n            plan["arms"][role] = "written"\n')]),
  [T + "test_b4_sim.InvalidStops.test_a_crashing_audit_does_not_lose_the_run_that_returned"]),
 ("M21 a dirty tree is recorded, not refused",
  edit(SIM, [('    if dirty:\n        raise Refusal(f"the tree is not clean ({len(dirty)} entries; the first: {dirty[0]!r}); there is no override")', "    if dirty:\n        pass")]),
  [T + "test_b4_sim.Preflight.test_refusals_write_nothing"]),
 ("M22 the input-drift checkpoint is a no-op",
  edit(SIM, [("    def hold_inputs(self, stage: str) -> None:\n        c = self.c\n", "    def hold_inputs(self, stage: str) -> None:\n        return None\n        c = self.c\n")]),
  [T + "test_b4_sim.InvalidStops.test_an_unexpected_exception_and_the_three_drifts"]),
 ("M23 a pooled summary written for an incomplete batch",
  multi(edit(SIM, [('                  "summary": self.summary if status == "complete" else None, "missing": missing', '                  "summary": self.summary if status == "complete" else (self.summary or {"partial": True}), "missing": missing')]),
        edit(SCH, [('        if doc["summary"] is not None:\n            f.append("a batch that did not complete carries no pooled numeric summary")', '        pass')])),
  [T + "test_b4_sim.IncompleteStops.test_the_deadline_inside_k9", T + "test_b4_sim.TheSummaryAndTheValidators.test_a_summary_with_a_verdict_key_is_refused_by_the_report_validator"]),
 ("M24 a final file overwritten instead of created exclusively",
  edit(SIM, [("        os.link(part, path)", "        os.replace(part, path); return {\"path\": path.name, \"sha256\": sha_bytes(data), \"size\": len(data)}")]),
  [T + "test_b4_sim.TheSummaryAndTheValidators.test_write_exclusive_never_overwrites_and_refuses_non_finite"]),
 ("M25 a non-finite statistic written as a JSON literal (no finite check, allow_nan)",
  edit(SIM, [("    nf = gs.finite_findings(doc)\n    if nf:\n        raise Invalid(\"schema\", f\"{path.name}: \" + \"; \".join(nf[:3]), stage=\"write\")\n", ""),
             ("    return (json.dumps(doc, indent=1, sort_keys=True, allow_nan=False) + \"\\n\").encode(\"utf-8\")", "    return (json.dumps(doc, indent=1, sort_keys=True, allow_nan=True) + \"\\n\").encode(\"utf-8\")")]),
  [T + "test_b4_sim.TheSummaryAndTheValidators.test_write_exclusive_never_overwrites_and_refuses_non_finite"]),
 ("M26 cohen_d's +inf written as 0 (encode_stat collapses it)",
  edit(GS, [('        if math.isinf(x):\n            return {"value": None, "special": "+inf" if x > 0 else "-inf"}', '        if math.isinf(x):\n            return {"value": 0, "special": None}')]),
  [T + "test_b4_gate_stats.CohenD.test_encoding_for_json", T + "test_b4_sim.TheSummaryAndTheValidators.test_on_hand_rows_including_an_infinite_cohen_d"]),
 ("M27 the power scan starts above n_min (a skipped candidate)",
  edit(GS, [("    for n in range(n_min, n_max + 1):\n        if check is not None:", "    for n in range(n_min + 1, n_max + 1):\n        if check is not None:")]),
  [T + "test_b4_gate_stats.Bootstrap.test_the_chunked_scan_equals_the_unchunked_one_and_stops_between_n"]),
 ("M28 the sign test's ties counted in n (the copy altered)",
  edit(GS, [("    n = pos + neg\n    if n == 0:\n        return 1.0, pos, neg, len(deltas)", "    n = len(deltas)\n    if pos + neg == 0:\n        return 1.0, pos, neg, len(deltas)")]),
  [T + "test_b4_gate_stats.TheCopy.test_the_source_text_of_every_copied_function_is_the_original_s", T + "test_b4_gate_stats.SignTest.test_by_hand"]),
 ("M29 the thresholds table's S changed to 199 (the document untouched)",
  edit(TH, [('    "K6": {"S_gate": 200,', '    "K6": {"S_gate": 199,')]),
  [T + "test_b4_thresholds.ThePins.test_the_numbers_are_the_document_s"]),
 ("M30 the report validator lets a verdict-like key through",
  edit(SCH, [('        verdict_like = re.compile(r"(^|_)(pass|passed|fail|failed|verdict|holds)($|_)")', '        verdict_like = re.compile(r"(^|_)(never_matches_anything)($|_)")')]),
  [T + "test_b4_sim.TheSummaryAndTheValidators.test_a_summary_with_a_verdict_key_is_refused_by_the_report_validator"]),
 ("M31 the harness accepts the gate's label",
  edit(SIM, [('LABEL_RE = re.compile(r"^b4-sim-[1-9][0-9]*$")', 'LABEL_RE = re.compile(r"^b4-(sim|gate)-[1-9][0-9]*$")')]),
  [T + "test_b4_sim.Preflight.test_refusals_write_nothing"]),
 ("M32 the harness runs on the mechanics fixture hypothesis (a fixture source in the formal CLI path)",
  edit(SIM, [("        hypothesis = hy.load()\n        mapping = bm.site_mapping()", "        hypothesis = hy.load().with_reading(\"clock_mode\", \"not_inverted\", \"not_inverted\", \"mechanics\", context=\"latch\")\n        mapping = bm.site_mapping()"),
             ('    if hypothesis.fixture is not False or hypothesis.sha256 != hy.HYPOTHESIS_SHA256:\n        raise Refusal("the hypothesis is not the formal one")', "    pass")]),
  [T + "test_b4_sim.CompleteBatch.test_complete_with_every_file_typed_and_no_verdict"]),
 ("M33 F1: the fixture schedule accepts a value that is not already exposed",
  edit(SIM, [("                if v not in bs.FIXTURE_VALUES:\n                    f.append", "                if False:\n                    f.append")]),
  [T + "test_b4_sim.TheSummaryAndTheValidators.test_the_fixture_schedule_s_own_findings", T + "test_b4_sim.Preflight.test_refusals_write_nothing"]),
 ("M34 F1: a production label runs on a fixture schedule (the label check inverted)",
  edit(SIM, [('        if not isinstance(label, str) or not FIXTURE_LABEL_RE.match(label):\n            raise Refusal(f"a batch with a FixtureSchedule carries a mechanics label', '        if False:\n            raise Refusal(f"a batch with a FixtureSchedule carries a mechanics label'),
             ('        if f or schedule.label != label:', '        if f:')]),
  [T + "test_b4_sim.Preflight.test_refusals_write_nothing"]),
 ("M35 F1: the harness derives a production master even for a fixture batch",
  edit(SIM, [("        if c[\"schedule\"] is None:\n            master = bs.master_seed(c[\"label\"], hy.HYPOTHESIS_SHA256)", "        if True:\n            master = bs.master_seed(c[\"label\"], hy.HYPOTHESIS_SHA256)")]),
  [T + "test_b4_sim.CompleteBatch.test_the_freezing_order_the_fixture_seeds_and_the_manifest"]),
 ("M36 F1: a fixture seeds document with a production label passes the seeds validator",
  edit(SEEDS, [('    elif fixture is not bool(FIXTURE_LABEL_RE.match(doc["label"])):\n        f.append("label: a fixture set has a b4-mech-<n> label and a production set has not")', "    elif False:\n        pass")]),
  [T + "test_b4_seeds.TheRegistry.test_the_fixture_form_of_the_seeds_document", T + "test_b4_seeds.TheRegistry.test_the_seeds_document_shape"]),
 ("M37 F7: the namespace chain is not checked for symlinks",
  edit(SIM, [('    for anc in namespace_chain(root):\n        if anc.is_symlink():\n            raise Refusal(f"{anc.relative_to(root)} is a symlink: the exploration namespace must be a real directory chain under the root")', "    for anc in namespace_chain(root):\n        if False:\n            pass")]),
  [T + "test_b4_sim.Preflight.test_a_symlinked_namespace_is_refused_at_every_level"]),
 ("M38 F6: a malformed returned RunResult is dropped instead of quarantined",
  edit(SIM, [('                self.quarantine(f"pair_{r:03d}/arm_{role}.result.QUARANTINE.json", r, role, "engine_return", f, doc)\n                raise Invalid("schema", f"arm_{role}.result.json: the returned RunResult does not validate (quarantined): "', '                raise Invalid("schema", f"arm_{role}.result.json: the returned RunResult does not validate (quarantined): "')]),
  [T + "test_b4_sim.InvalidStops.test_a_malformed_returned_result_is_quarantined_not_lost"]),
 ("M39 F6: the K9 partial is not kept on a refusal",
  edit(SIM, [('            kept = self._keep_partial(r, "k9", getattr(exc, "k9_partial", None), lambda doc: sc.k9_findings(doc, task), "K9", "refusal")', '            kept = self._keep_partial(r, "k9", None, lambda doc: sc.k9_findings(doc, task), "K9", "refusal")')]),
  [T + "test_b4_sim.InvalidStops.test_a_refusal_inside_k9_keeps_the_partial"]),
 ("M40 F6: K9 raises without carrying its partial",
  edit(K9, [("        except BaseException as exc:  # noqa: BLE001 — the evidence obtained so far travels with the exception, whatever it is\n            if isinstance(exc, KeyboardInterrupt):", "        except BaseException as exc:  # noqa: BLE001\n            raise\n            if isinstance(exc, KeyboardInterrupt):")]),
  [T + "test_b4_k9.TheComputation.test_a_refusal_inside_a_pair_carries_the_partial_and_a_truncated_complete_record_is_named", T + "test_b4_sim.InvalidStops.test_a_refusal_inside_k9_keeps_the_partial"]),
 ("M41 F4: a self-validation finding does not turn a complete batch invalid",
  edit(SIM, [("        if status == \"complete\" and self_validation:\n            first = next(iter(self_validation.items()))", "        if False:\n            first = next(iter(self_validation.items()))")]),
  [T + "test_b4_sim.InvalidStops.test_self_validation_findings_and_an_unwritable_report_are_never_complete"]),
 ("M42 F4: an unwritable report keeps the batch's success status",
  edit(SIM, [('            out.update(status="invalid", exit_code=1, report_error=msg, original_status=status)', '            out.update(report_error=msg, original_status=status)')]),
  [T + "test_b4_sim.InvalidStops.test_self_validation_findings_and_an_unwritable_report_are_never_complete"]),
 ("M43 F8: no deadline check before finalisation",
  edit(SIM, [("        if status == \"complete\":\n            try:\n                self.dl.check()                                     # a finalisation unit never starts after the expiry", "        if False:\n            try:\n                self.dl.check()"),
             ("        batch.dl.check()                                            # after the last statistics unit (F8)\n", ""),
             ("        batch.dl.check()                                            # before the finalisation units (F8)\n", "")]),
  [T + "test_b4_sim.IncompleteStops.test_the_deadline_expiring_before_finalisation_is_incomplete"]),
 ("M44 F9: the external sources and the exclusion sources are not bound in the snapshot",
  edit(SIM, [('            external[str(p)] = got\n', '            pass\n'), ("    for src in exclusion.sources:                                   # read against their digests already; bound here for the checkpoints\n        inputs[src.path] = src.sha256\n", "")]),
  [T + "test_b4_sim.CompleteBatch.test_the_freezing_order_the_fixture_seeds_and_the_manifest", T + "test_b4_sim.InvalidStops.test_an_unexpected_exception_and_the_three_drifts"]),
 ("M45 F9: the registry snapshot is not held at the checkpoints",
  edit(SIM, [('        if now != c["registry"]:\n            raise Invalid("input_drift", f"the archived-set registry changed during the batch', '        if False:\n            raise Invalid("input_drift", f"the archived-set registry changed during the batch')]),
  [T + "test_b4_sim.InvalidStops.test_an_unexpected_exception_and_the_three_drifts"]),
 ("M46 F2: the verifier does not require the files of a pair's recorded state",
  edit(VER, [('        for rel in sorted(must - on_disk):\n            F.add(rel, f"required by pair', '        for rel in sorted(set()):\n            F.add(rel, f"required by pair')]),
  [T + "test_b4_sim.TheArchiveVerifier.test_the_untouched_archive_is_clean_and_every_tamper_is_named"]),
 ("M47 F2: the verifier does not recompute the pooled summary",
  edit(VER, [('                if _j(summary) != _j(report["summary"]):\n                    F.add("sim_report.json", "the pooled summary is not the one recomputed from the pairs\' files")', '                pass')]),
  [T + "test_b4_sim.TheArchiveVerifier.test_the_untouched_archive_is_clean_and_every_tamper_is_named"]),
 ("M48 F3: the fixed comparison sets are not enforced (K9 and K10 canonical checks removed)",
  multi(edit(K9, [("    f += canonical_findings(result, mapping)\n    if len(result[\"pairs\"]) > len(want_pairs):\n        return f\n", "")]),
        edit(K10, [("    f += canonical_findings(result)\n    if len(result[\"units\"]) > len(canonical_units()):\n        return f\n", "")]),
        edit(SCH, [("    f += k9.canonical_findings(doc, mapping)\n", ""), ("    f += k10.canonical_findings(doc)\n", "")])),
  [T + "test_b4_k9.TheComputation.test_a_refusal_inside_a_pair_carries_the_partial_and_a_truncated_complete_record_is_named",
   T + "test_b4_k10.TheComputation.test_duplicated_or_missing_units_in_a_complete_record_are_named", T + "test_b4_sim.TheArchiveVerifier.test_the_comparison_sets_and_the_cell_types_are_enforced_by_the_validators"]),
 ("M49 F3: a q cell of 2 passes the observation validator",
  edit(SCH, [("        if not (isinstance(row, list) and len(row) == ELEMENTS and all(c is None or (c in (0, 1) and _int(c)) for c in row)):", "        if not (isinstance(row, list) and len(row) == ELEMENTS):")]),
  [T + "test_b4_sim.TheArchiveVerifier.test_the_comparison_sets_and_the_cell_types_are_enforced_by_the_validators", T + "test_b4_sim.InvalidStops.test_a_bad_q_cell_from_the_source_is_never_archived_as_complete"]),
 ("M50 F3: a validator exception escapes instead of becoming a finding",
  edit(SCH, [("        except Exception as exc:  # noqa: BLE001\n            return [f\"{fn.__name__}: the validator raised {type(exc).__name__}: {exc} — the document is malformed\"]", "        except ZeroDivisionError as exc:  # noqa: BLE001\n            return [f\"{fn.__name__}: the validator raised {type(exc).__name__}: {exc} — the document is malformed\"]"),
             ('    if not (isinstance(doc["arm_order"], list) and tuple(doc["arm_order"]) == ROLES):', '    if tuple(doc["arm_order"]) != ROLES:')]),
  [T + "test_b4_sim.TheArchiveVerifier.test_the_comparison_sets_and_the_cell_types_are_enforced_by_the_validators"]),
]


def run(tree, tests):
    p = subprocess.run([sys.executable, "-m", "unittest", *tests], cwd=tree, capture_output=True, text=True)
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
        with tempfile.TemporaryDirectory(prefix="b4mut_") as tmp:
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
    # usage: b4_2b4a_mutants.py [<out.txt> [M1,M2,...]]  — the optional third argument runs a subset (names by their M-number)
    text = main(set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None)
    out = sys.argv[1] if len(sys.argv) > 1 else None
    if out:
        pathlib.Path(out).write_text(text)
