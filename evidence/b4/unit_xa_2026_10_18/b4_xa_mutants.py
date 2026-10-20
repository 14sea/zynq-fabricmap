#!/usr/bin/env python3
"""Mutants for the X-A unit (hermetic whole-tree copies; a kill only with Ran N > 0 and FAILED)."""
import re, shutil, subprocess, sys, tempfile, pathlib
R = pathlib.Path(__file__).resolve().parents[3]
E = "b4/host/b4_engine.py"; C = "b4/host/b4_carto.py"; RP = "b4/host/b4_replay.py"
TE = "b4.tests.test_b4_engine"; TC = "b4.tests.test_b4_carto"; TR = "b4.tests.test_b4_replay"
MUTANTS = [
 ("X1 the relabelling removed (X's cartographer learns the true addresses)", E,
  [("            carto.ingest(seq_, bc.relabel_genome(genome, x_perm), stim_sha, grid)     # the addresses relabelled, the grid untouched\n",
    "            carto.ingest(seq_, genome, stim_sha, grid)\n")],
  [f"{TE}.CompleteRuns.test_o_learns_online_and_x_stays_isomorphic"]),
 ("X2 the shadow contract not checked after each ingest", E,
  [("            findings = bc.isomorphic_addresses(carto, shadow, x_perm)                  # after EVERY ingest\n", "            findings = []\n")],
  [f"{TE}.ControlXA.test_a_control_failure_is_its_own_event_at_its_commit_point"]),
 ("X3a pi drawn from the operator seed", E,
  [("        attempts = bc.derangement_attempts(control_seed, n)\n", "        attempts = bc.derangement_attempts(operator_seed, n)\n")],
  [f"{TE}.CompleteRuns.test_o_learns_online_and_x_stays_isomorphic", f"{TE}.ControlXA.test_pi_is_drawn_before_the_base_from_the_control_generator_not_the_operator_s"]),
 ("X3b pi's draw consumes the operator's generator", E,
  [("        attempts = bc.derangement_attempts(control_seed, n)\n", "        rng.next32()\n        attempts = bc.derangement_attempts(control_seed, n)\n")],
  [f"{TE}.ControlXA.test_pi_is_drawn_before_the_base_from_the_control_generator_not_the_operator_s"]),
 ("X4 pi redrawn after the base observation (after something was seen)", E,
  [("        pop = [Individual(task.base_genome, base_fit, i) for i in range(MU)]\n",
    "        pop = [Individual(task.base_genome, base_fit, i) for i in range(MU)]\n        if arm == \"X\":\n            x_perm = bc.derangement(control_seed + 1, n); res.x_perm = list(x_perm)\n")],
  [f"{TE}.CompleteRuns.test_o_learns_online_and_x_stays_isomorphic", f"{TE}.ControlXA.test_domain_mid_generation_under_x_keeps_pi_and_reports_the_residual_post_hoc", f"{TR}.ControlXARecords"]),
 ("X5 the operator handed the TRUE partition (the shadow's view) under X", E,
  [("                    live = frozen if arm == \"F\" else (carto.view() if carto else None)\n",
    "                    live = frozen if arm == \"F\" else ((shadow.view() if arm == \"X\" else carto.view()) if carto else None)\n")],
  [f"{TE}.ControlXA.test_the_operator_s_group_moves_use_x_s_relabelled_groups"]),
 ("X6 the ledger stores the relabelled genome", E,
  [("        e = {\"seq\": seq, \"phase\": phase, \"genome\": genome, \"genome_hex\": ex.genome_hex(genome, n),",
    "        genome = bc.relabel_genome(genome, x_perm) if arm == \"X\" else genome\n        e = {\"seq\": seq, \"phase\": phase, \"genome\": genome, \"genome_hex\": ex.genome_hex(genome, n),")],
  [f"{TE}.CompleteRuns.test_o_learns_online_and_x_stays_isomorphic"]),
 ("X7 a control failure recorded as DOMAIN", E,
  [("    except ControlFailure as c:                                   # the shadow contract broken: its own event, never DOMAIN or a refusal\n        res.control_failure = {",
    "    except ControlFailure as c:\n        res.terminal = {'code': 'DOMAIN', 'phase': c.phase, 'attempt': c.attempt + 1, 'genome': 0, 'config_sha256': '0' * 64, 'stimulus_sha256': '0' * 64, 'landscape_seed': task.seed, 'operator_seed': operator_seed, 'budget': budget, 'successful_observations': res.observations, 'rng_state': rng.state(), 'population_commitment': population_commitment(pop), 'map_commitment': carto.commitment(), 'map_version': carto.version}\n        res.completed = False\n    except ControlFailure as c:\n        res.control_failure = {")],
  [f"{TE}.ControlXA.test_a_control_failure_is_its_own_event_at_its_commit_point"]),
 ("X8 the exposing observation dropped on a control failure", E,
  [("        res.completed = False\n    except (ValueError, ex.fm.ModelRefusal) as e:",
    "        res.completed = False\n        res.ledger.pop(); children.pop(); res.evals -= 1; res.cost['search'] -= 1; res.best_trace.pop()\n    except (ValueError, ex.fm.ModelRefusal) as e:")],
  [f"{TE}.ControlXA.test_a_control_failure_is_its_own_event_at_its_commit_point"]),
 ("X9 the generation closed (selection) after a control failure", E,
  [("        res.completed = False\n    except (ValueError, ex.fm.ModelRefusal) as e:",
    "        res.completed = False\n        if children:\n            pool = pop + children; pool.sort(key=lambda ind: (-ind.fit, ind.born)); pop = pool[:MU]; children = []\n    except (ValueError, ex.fm.ModelRefusal) as e:")],
  [f"{TE}.ControlXA.test_a_control_failure_is_its_own_event_at_its_commit_point"]),
 ("X10 the generator advanced after a control failure", E,
  [("        res.completed = False\n    except (ValueError, ex.fm.ModelRefusal) as e:",
    "        res.completed = False\n        rng.next32()\n    except (ValueError, ex.fm.ModelRefusal) as e:")],
  [f"{TE}.ControlXA.test_a_control_failure_is_its_own_event_at_its_commit_point"]),
 ("X11 the replay accepts the recorded pi without re-deriving it", RP,
  [("            if r[\"x_perm_attempts\"] != attempts or r[\"x_perm\"] != attempts[-1]:\n", "            if False:\n")],
  [f"{TR}.ControlXARecords.test_pi_not_derived_from_the_control_seed_is_named"]),
 ("X12 a non-reproduced control failure not named by the replay", RP,
  [("    if result[\"control_failure\"] is not None and again.control_failure is None:\n        out.append(\"the recorded control failure did not reproduce: on re-execution the relabelled cartographer and the shadow agree\")\n", "")],
  [f"{TE}.ControlXA.test_a_control_failure_is_its_own_event_at_its_commit_point"]),
 ("X13 groups_moved always zero / preserved always true", C,
  [("    moved = sum(1 for g in true_groups if g not in x_groups)\n    return {\"partition_preserved\": set(true_groups) == x_groups,", "    moved = 0\n    return {\"partition_preserved\": True,")],
  [f"{TC}.ControlX.test_the_two_hand_fixtures_of_the_ruling"]),
 ("X14 the address isomorphism ignores the permutation", C,
  [("        s, xr = shadow.rel[a], x.rel[perm[a]]\n", "        s, xr = shadow.rel[a], x.rel[a]\n")],
  [f"{TC}.ControlX.test_x_a_relabels_the_addresses_and_stays_isomorphic_in_full"]),
 ("X15 the address isomorphism skips the evidence references", C,
  [("        if (xr.cells, xr.presence, xr.pairs_with_effect, xr.pairs_without_effect, xr.contexts, xr.evidence) != \\\n           (s.cells, s.presence, s.pairs_with_effect, s.pairs_without_effect, s.contexts, s.evidence):\n            f.append(f\"address {a} -> {perm[a]}",
    "        if (xr.cells, xr.presence, xr.pairs_with_effect, xr.pairs_without_effect, xr.contexts) != \\\n           (s.cells, s.presence, s.pairs_with_effect, s.pairs_without_effect, s.contexts):\n            f.append(f\"address {a} -> {perm[a]}")],
  [f"{TC}.ControlX.test_x_a_relabels_the_addresses_and_stays_isomorphic_in_full"]),
 ("X16 the rejected attempts not recorded", C,
  [("        attempts.append(p)\n        if all(p[i] != i for i in range(n)):\n            return attempts\n", "        if all(p[i] != i for i in range(n)):\n            attempts.append(p)\n            return attempts\n")],
  [f"{TC}.ControlX.test_the_attempts_are_recorded_and_the_last_is_the_derangement"]),
 ("X17 a control seed accepted on any arm", E,
  [("    if arm != \"X\" and control_seed is not None:\n        raise ValueError(\"a control seed is for control X only\")\n", "")],
  [f"{TE}.CompleteRuns.test_given_views_carry_their_provenance"]),
 ("X18 the residual computed from X's view against itself", E,
  [("            res.x_residual = bc.residual_structure(live_carto.view(), shadow.view())     # post hoc only\n", "            res.x_residual = bc.residual_structure(live_carto.view(), live_carto.view())\n")],
  [f"{TE}.CompleteRuns.test_o_learns_online_and_x_stays_isomorphic"]),
]
only = sys.argv[1:]
for name, rel, edits, targets in MUTANTS:
    if only and not any(name.startswith(o) for o in only):
        continue
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="b4_mut_"))
    shutil.copytree(R, tmp / "tree", ignore=shutil.ignore_patterns(".git", "build", "staging", "__pycache__", "*.pyc", "vivado", "builds", "evidence"), symlinks=True)
    (tmp / "tree/gate_runs/run_2026_08_05_ff").mkdir(parents=True, exist_ok=True)
    shutil.copy2(R / "gate_runs/run_2026_08_05_ff/certificate.json", tmp / "tree/gate_runs/run_2026_08_05_ff/certificate.json")
    f = tmp / "tree" / rel; s = f.read_text()
    for old, new in edits:
        assert s.count(old) == 1, (name, old[:60], s.count(old))
        s = s.replace(old, new)
    f.write_text(s)
    p = subprocess.run([sys.executable, "-B", "-m", "unittest", *targets], cwd=tmp / "tree", capture_output=True, text=True)
    out = p.stdout + p.stderr
    ran = re.search(r"^Ran (\d+) tests?", out, re.M); n = int(ran.group(1)) if ran else 0
    status = "FAILED" if re.search(r"^FAILED", out, re.M) else ("OK" if re.search(r"^OK", out, re.M) else "NO-RESULT")
    first = re.findall(r"^(?:FAIL|ERROR): (\S+)", out, re.M)
    print(f"{'KILLED' if n > 0 and status == 'FAILED' else 'SURVIVED'}  {name}  [Ran {n}, {status}]  {first[:3]}")
    shutil.rmtree(tmp, True)
