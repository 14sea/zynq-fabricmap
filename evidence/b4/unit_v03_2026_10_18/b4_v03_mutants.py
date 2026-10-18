#!/usr/bin/env python3
"""Mutants for the v0.3 model revision unit (hermetic whole-tree copies; a kill only with Ran N > 0 and FAILED).
The copy carries the certificate and the D1' probe report (both re-hashed by the loader) but no other evidence."""
import json, re, shutil, subprocess, sys, tempfile, pathlib
R = pathlib.Path(__file__).resolve().parents[3]
H = "b4/hypothesis/ff_behaviour_v0.3.json"; HY = "b4/host/b4_ff_hypothesis.py"; M = "b4/host/b4_ff_model.py"; FX = "b4/tests/b4_test_fixtures.py"
V02 = "b4/hypothesis/ff_behaviour_v0.2.json"
TH = "b4.tests.test_b4_ff_hypothesis"; TM = "b4.tests.test_b4_ff_model"; TE = "b4.tests.test_b4_engine"; TX = "b4.tests.test_b4_execution"
PR = "evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json"

def json_edit(fn):
    """An edit of the committed v0.3 document, re-serialised in its own format (the pin then differs: the mutant also re-pins)."""
    def apply(tree):
        p = tree / H; doc = json.loads(p.read_bytes()); fn(doc)
        p.write_bytes((json.dumps(doc, indent=1, sort_keys=True) + "\n").encode())
        import hashlib
        d = hashlib.sha256(p.read_bytes()).hexdigest()
        hp = tree / HY; s = hp.read_text(); s = re.sub(r'HYPOTHESIS_SHA256 = "[0-9a-f]{64}"', f'HYPOTHESIS_SHA256 = "{d}"', s); hp.write_text(s)
    return apply

def text_edit(rel, edits):
    def apply(tree):
        f = tree / rel; s = f.read_text()
        for old, new in edits:
            assert s.count(old) == 1, (rel, old[:60], s.count(old))
            s = s.replace(old, new)
        f.write_text(s)
    return apply

def bit0_unknown(d): d["decode"]["clock_mode"]["by_storage_context"]["latch"]["bit_zero"] = "unknown"
def bit0_not_inverted(d): d["decode"]["clock_mode"]["by_storage_context"]["latch"]["bit_zero"] = "not_inverted"
def drop_probe_source(d): d["sources"] = [s for s in d["sources"] if s.get("path") != PR]
def drop_g_items(d):
    s = next(x for x in d["sources"] if x["kind"] == "project_decode_assumption"); s["items"] = [t for t in s["items"] if not re.match(r"G\d ", t)]
def status_verified(d): d["status"] = "verified"
def version_back(d): d["schema_version"] = "0.2.1"

MUTANTS = [
 ("V1 the v0.3 file's latch bit 0 back to unknown (re-pinned)", json_edit(bit0_unknown),
  [f"{TH}.TheFile.test_it_loads_and_every_source_hashes", f"{TH}.TheFile.test_the_decode_of_the_base_configuration", f"{TM}.Latches.test_the_inverted_gate_latch_is_transparent_while_the_slice_clock_is_low", f"{TE}.Termination.test_under_the_formal_v03_hypothesis_f_s_probe_pass_completes"]),
 ("V2 the v0.3 file's latch bit 0 read as not_inverted (the mechanics reading as formal; re-pinned)", json_edit(bit0_not_inverted),
  [f"{TH}.TheFile.test_the_decode_of_the_base_configuration", f"{TM}.Latches.test_the_inverted_gate_latch_is_transparent_while_the_slice_clock_is_low"]),
 ("V3 the D1' probe report dropped from the sources (re-pinned)", json_edit(drop_probe_source), [f"{TH}.TheFile.test_it_loads_and_every_source_hashes"]),
 ("V4 the generalisation assumptions G1-G6 dropped (re-pinned)", json_edit(drop_g_items), [f"{TH}.TheFile.test_it_loads_and_every_source_hashes"]),
 ("V5 the file's status set to verified (re-pinned)", json_edit(status_verified), [f"{TH}.TheFile.test_it_loads_and_every_source_hashes"]),
 ("V6 the formal pointer left on the v0.2 file", text_edit(HY, [('HYPOTHESIS_REL = "b4/hypothesis/ff_behaviour_v0.3.json"', 'HYPOTHESIS_REL = "b4/hypothesis/ff_behaviour_v0.2.json"')]),
  [f"{TH}.TheFile.test_it_loads_and_every_source_hashes", f"{TE}.Termination.test_under_the_formal_v03_hypothesis_f_s_probe_pass_completes"]),
 ("V7 the digest not rotated (the v0.2 pin kept with the v0.3 pointer)", text_edit(HY, [(None, None)]), [f"{TH}.TheFile.test_it_loads_and_every_source_hashes", f"{TM}.Latches.test_the_inverted_gate_latch_is_transparent_while_the_slice_clock_is_low"]),
 ("V8 the kept v0.2 file altered by one byte (a trailing newline added)", None, [f"{TH}.TheFile.test_every_assignment_is_in_the_v03_domain_and_the_v02_file_is_kept_as_a_marked_fixture", f"{TE}.Termination.test_under_the_kept_v021_reading_f_s_probe_pass_terminates_at_the_latch_flip"]),
 ("V9 the hole fixture built without the digest check (any content accepted)", text_edit(FX, [("    if got != V021_SHA256:\n        raise AssertionError", "    if False:\n        raise AssertionError")]),
  [f"{TH}.TheFile.test_every_assignment_is_in_the_v03_domain_and_the_v02_file_is_kept_as_a_marked_fixture"]),
 ("V10 the hole fixture built from the FORMAL file (no hole)", text_edit(FX, [("    return hy.fixture(json.loads(raw), \"v021_hole\")", "    return hy.fixture(json.loads(hy.HYPOTHESIS.read_bytes()), \"v021_hole\")")]),
  [f"{TH}.TheFile.test_the_decode_of_the_base_configuration", f"{TM}.Latches.test_a_latch_with_the_clkinv_bit_clear_is_outside_the_v021_domain_and_the_refusal_says_only_that", f"{TE}.Termination.test_under_the_kept_v021_reading_f_s_probe_pass_terminates_at_the_latch_flip", f"{TX}.Boundary.test_domain_becomes_a_terminal_event_with_the_state_before_the_call"]),
 ("V11 the model ignores the inversion under a latch (the gate always the slice clock)", text_edit(M, [("                gate = self._phys(cfg, clock) if h.flag(\"latch_gate_is_physical_clock\") else clock\n", "                gate = clock\n")]),
  [f"{TM}.Latches.test_the_inverted_gate_latch_is_transparent_while_the_slice_clock_is_low"]),
 ("V12 the model settles the new inputs only after the clock change (the wrong order)", text_edit(M, [(None, None)]),
  [f"{TM}.Latches.test_the_inverted_gate_latch_is_transparent_while_the_slice_clock_is_low"]),
 ("V13 the init step settles level effects (INIT not atomic under an open gate)", text_edit(M, [(None, None)]),
  [f"{TM}.Latches.test_the_inverted_gate_latch_is_transparent_while_the_slice_clock_is_low"]),
 ("V14 the formal-completion fact weakened: calls not held to B + 23", text_edit("b4/tests/test_b4_engine.py", [('            self.assertEqual((r.cost, port.calls, r.observations), ({"base": 1, "probes": 21, "search": budget, "holdout": 1}, budget + 23, budget + 23), seed)\n', '')]),
  None),   # a test mutant: shown to matter by the engine mutant V17 surviving it (see below)
 ("V15 the engine skips the last probe (20 probes, the run still completes)", text_edit("b4/host/b4_engine.py", [(None, None)]),
  [f"{TE}.Termination.test_under_the_formal_v03_hypothesis_f_s_probe_pass_completes"]),
 ("V16 the latch_gate_inverted swap made equal to the formal v0.3 reading", text_edit(M, [('    "latch_gate_inverted": ("reading", "clock_mode", "inverted", "not_inverted", "latch"),', '    "latch_gate_inverted": ("reading", "clock_mode", "not_inverted", "inverted", "latch"),')]),
  [f"{TM}.Fixtures.test_every_hypothesis_swap_changes_a_trace_the_truth_would_not"]),
 ("V17 the engine double-counts the base observation (observations B + 24, the port called B + 23; invisible to the ledger and to the replay)",
  text_edit("b4/host/b4_engine.py", [("        res.observations += 1\n", "        res.observations += 1 + (1 if phase == \"base\" else 0)\n")]),
  [f"{TE}.Termination.test_under_the_formal_v03_hypothesis_f_s_probe_pass_completes"]),
]
only = sys.argv[1:]
def make_tree():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="b4_mut_"))
    shutil.copytree(R, tmp / "tree", ignore=shutil.ignore_patterns(".git", "build", "staging", "__pycache__", "*.pyc", "vivado", "builds", "evidence"), symlinks=True)
    for rel in ("gate_runs/run_2026_08_05_ff/certificate.json", PR):
        (tmp / "tree" / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(R / rel, tmp / "tree" / rel)
    return tmp
for name, apply, targets in MUTANTS:
    if only and not any(name.startswith(o) for o in only):
        continue
    tmp = make_tree(); tree = tmp / "tree"
    if name.startswith("V7"):
        s = (tree / HY).read_text(); s = re.sub(r'HYPOTHESIS_SHA256 = "[0-9a-f]{64}"', 'HYPOTHESIS_SHA256 = "1118bedf4831bac3806be4aa3d9b56630912a946156869807f2c26f6374e6ed2"', s); (tree / HY).write_text(s)
    elif name.startswith("V8"):
        (tree / V02).write_bytes((tree / V02).read_bytes() + b"\n")
    elif name.startswith("V12"):
        f = tree / M; s = f.read_text()
        # the set step: settle at the old clock AFTER the clock change instead of before — found by its comment line
        old = "                self._settle(q, decoded, clock, ce, sr, d)\n                clock_before, clock = clock, st[\"clock\"]\n"
        assert s.count(old) == 1, "V12 anchor"; s = s.replace(old, "                clock_before, clock = clock, st[\"clock\"]\n"); f.write_text(s)
    elif name.startswith("V13"):
        f = tree / M; s = f.read_text()
        old = "                        q[i] = decoded[e].init if decoded[e].applicable else None\n"
        assert s.count(old) == 1, "V13 anchor"
        s = s.replace(old, old + "                self._settle(q, decoded, clock, ce, sr, d)\n"); f.write_text(s)
    elif name.startswith("V15"):
        f = tree / "b4/host/b4_engine.py"; s = f.read_text()
        old = "            for a in order:\n"
        assert s.count(old) == 1, "V15 anchor"; s = s.replace(old, "            for a in order[:-1]:\n"); f.write_text(s)
    elif name.startswith("V14"):
        apply(tree)
        # the test mutant: apply the engine mutant V17 on top and show the weakened test lets it live
        f = tree / "b4/host/b4_engine.py"; s = f.read_text(); assert s.count("        res.observations += 1\n") == 1; s = s.replace("        res.observations += 1\n", "        res.observations += 1 + (1 if phase == \"base\" else 0)\n"); f.write_text(s)
        targets = [f"{TE}.Termination.test_under_the_formal_v03_hypothesis_f_s_probe_pass_completes"]
    else:
        apply(tree)
    p = subprocess.run([sys.executable, "-B", "-m", "unittest", *targets], cwd=tree, capture_output=True, text=True)
    out = p.stdout + p.stderr
    ran = re.search(r"^Ran (\d+) tests?", out, re.M); n = int(ran.group(1)) if ran else 0
    status = "FAILED" if re.search(r"^FAILED", out, re.M) else ("OK" if re.search(r"^OK", out, re.M) else "NO-RESULT")
    first = re.findall(r"^(?:FAIL|ERROR): (\S+)", out, re.M)
    verdict = "KILLED" if n > 0 and status == "FAILED" else "SURVIVED"
    if name.startswith("V14"):
        verdict = "TEST-MUTANT: " + ("engine mutant V17 would SURVIVE the weakened test (the assertion matters)" if status == "OK" else "engine mutant V17 still caught (the assertion is redundant)")
    print(f"{verdict}  {name}  [Ran {n}, {status}]  {first[:3]}")
    if status == "NO-RESULT":
        print(out[-1500:])
    shutil.rmtree(tmp, True)
