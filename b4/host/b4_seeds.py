#!/usr/bin/env python3
"""B4 — the SEED ANCHOR, the EXCLUSION SET and the pair derivation (docs/b4_architecture.md section 9.2; the owner's
rulings of 2026-10-18 on unit 2b-3 section 5 and on unit 2b-4a section 3.1).

    master = master_seed("b4-sim-3", HYPOTHESIS_SHA256)       # int.from_bytes(sha256(label + "|" + anchor)[:4], "big")
    ex = load_exclusion_set(REPO_ROOT)                         # every historical source re-hashed, typed field by field,
                                                               # plus B4's exposed values, plus the exposure receipt, plus EVERY archived evidence/b4/sim/*/seeds.json
    pairs = pair_seeds(master, count, ex.values)               # B2's algorithm, copied: one pooled set, both positions screened

The anchor is the formal hypothesis's digest; the label is passed BESIDE it and a label carrying '|' is refused (a
pre-joined label would put two labels in one string). Nothing here reads a candidate result or generates a formal
set: the exploration set is derived once by the harness after the exclusion snapshot is archived (section 9.2's
freezing order); the gate set is unit 2b-4's.

THE EXCLUSION SET IS ONE POOLED SET OF INTEGERS. Every value in every seed-bearing field named below — a landscape,
operator, master or control seed, whatever its role there — is one integer in the set, and `pair_seeds` screens BOTH
positions of every drawn pair against it (B2's `pair_seeds` does the same with its `seen` set). Four kinds of source:

  1. the 38 historical files of section 9.2, each held to the digest recorded there and read through a TYPED FIELD
     PATH (`FIELDS`): a path that does not resolve, a leaf that is not an int in 0 .. 2^32 - 1, or a bool, is a
     refusal by name — counts, versions and timestamps are never mistaken for seeds because no path points at them;
  2. B4's own exposed literal values (`B4_EXPOSED_VALUES`: the seeds used as literal arguments in B4's tests, the
     control / fixture / derangement seeds, the single formal base observation of the 2b-3 scope draft) — a
     conservative measure, not an estimate of any distribution; a test that needs a new literal registers it here in
     the same commit;
  3. EVERY archived exploration set under `evidence/b4/sim/` (`sim_registry`): each run directory, in path order,
     must carry a readable, valid `seeds.json` (complete, invalid, incomplete, failed, aborted or void — all count),
     or an `INIT_FAILED.json` that states no seeds were derived; a directory with neither, or with a damaged or
     malformed seeds file, is a refusal, never skipped. The directory not existing at all is not a missing source;
  4. the EXPOSURE RECEIPT (`EXPOSURE_RECEIPT_REL`, pinned by digest): the owner's settlement of 2026-10-19 of the production
     sets derived before the repair under the labels `b4-sim-1` / `b4-sim-2` — every value observed in a preserved record,
     reconstructed from the committed recipes, or conservatively derivable from a drawn pair (the control seeds). Those two
     labels are RETIRED (`RETIRED_LABELS`): a new production derivation under them is refused before any master is formed;
     their archived records are still read by the registry. A missing, re-hashed or malformed receipt is a refusal.

A missing or re-hashed historical source is `ExclusionSourceRefusal`, never silently skipped. The loader never
imports a pinned module: `host/b2_search.py` is read as TEXT for its `EXCLUDED_SEEDS` line and the parsed list must
equal the copy `B2_EXCLUDED_SEEDS` kept here.
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from b4_rng import Rng  # noqa: E402

SEED_MAX = 0xFFFFFFFF
LABEL_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SIM_REL = "evidence/b4/sim"                                  # the exploration namespace; its seed registries are sources
SEEDS_FILE = "seeds.json"
INIT_FAILED_FILE = "INIT_FAILED.json"
SEEDS_SCHEMA = ("b4_sim_seeds", "1.2.0")                      # 1.1.0 (the repair of 2026-10-18): the `fixture` flag; 1.2.0 (the settlement of 2026-10-19): exclusion.exposure_receipt
SEEDS_SCHEMA_VERSIONS_READ = ("1.1.0", "1.2.0")                 # archived seed records of these versions are read by the registry (1.0.0 legacy records are not current-schema runs)
FIXTURE_LABEL_RE = re.compile(r"^b4-mech-[1-9][0-9]*$")       # a MECHANICS fixture set: explicit, already-exposed values, no master
RETIRED_LABELS = frozenset({"b4-sim-1", "b4-sim-2"})         # consumed by the pre-repair exposure (the owner's ruling of 2026-10-19, section 1): never derived again
EXPLORATION_LABEL = "b4-sim-3"                                 # the next exploration label, reserved by that ruling before any value of it exists (not derived in the settlement)
EXPOSURE_RECEIPT_REL = "evidence/b4/unit_2b4a_exposure_settlement_2026_10_19/exposure_receipt.json"
EXPOSURE_RECEIPT_SHA256 = "68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146"
RECEIPT_SCHEMA = ("b4_exposure_receipt", "1.0.0")
RECEIPT_KEYS = frozenset({"schema", "schema_version", "status", "ruling", "reconstruction_utc", "reconstruction_script", "historical_inputs", "envelope", "variants",
                          "preserved_records", "values", "pooled", "pooled_count", "pooled_sha256", "already_in_base_pool", "limits"})
RECEIPT_CLASSES = frozenset({"observed", "reconstructed_recipe", "conservative_superset"})
INIT_FAILED_SCHEMA = ("b4_sim_init_failed", "1.0.0")

# B2's frozen list (host/b2_search.py EXCLUDED_SEEDS), copied; the text of the pinned file must parse to exactly this.
B2_EXCLUDED_SEEDS = (1, 2, 3, 5, 11, 77, 99, 1234, 4321, 195948557, 324805736, 521288629, 1278624577,
                     1278628687, 1281816666, 2119807262, 3735928559, 4294967295, 1123460948, 176359248)

# B4's exposed literal values (section 9.2): landscape seeds 3 / 5 / 7 / 8 and operator seeds 11 / 12 / 13 used as
# literal arguments in the B4 tests and the v0.3 mechanism fixing; the X control values 5 / 6 / 7 / 8; the fabric
# fixture seeds 1 / 2 / 3 / 5; the derangement seeds 5 / 6 / 9 and the scanned value 1; the single formal base
# observation of the 2b-3 scope draft under landscape seed 7. One pooled set; the roles are history, not structure.
B4_EXPOSED_VALUES = frozenset((3, 5, 7, 8, 11, 12, 13, 5, 6, 7, 8, 1, 2, 3, 5, 5, 6, 9, 1, 7))

# The values a mechanics FIXTURE schedule may use: already exposed under section 9.2 (B2's copy and B4's exposed values).
# A fixture set derives nothing: no anchor, no master, no draw; it can never reach a production set.
FIXTURE_VALUES = frozenset(B2_EXCLUDED_SEEDS) | B4_EXPOSED_VALUES

# ------------------------------------------------------------------ the typed field paths
# A path is dot-separated; a step `name` indexes a dict key, `name[]` iterates a list under that key, `[]` alone
# iterates the current list, `*` iterates every value of a dict. A leaf must be an int (not a bool) in 0 .. SEED_MAX.
PY_EXCLUDED = "python:EXCLUDED_SEEDS"
ROWS = ("rows[].landscape_seed", "rows[].operator_seed")
PAIRS = ("pairs[].landscape_seed", "pairs[].operator_seed")
GATE_SEEDS_B2 = ("seeds.master_seed", "seeds.excluded[]")
SOURCE_SEEDS_B2 = ("source.seeds.master_seed", "source.seeds.excluded[]")
GATE_SEEDS_B3 = ("seeds.master_seed", "seeds.excluded_fixed[]", "seeds.excluded_sources.*.master_seed", "control_x.seed_x")
SIM_SEEDS = ("seeds.master_seed",)

FIELDS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("host/b2_search.py", (PY_EXCLUDED,), "3acb04714a6c677708892d171f6a418e6de7627210e2ec6ad65158db51eab1cf"),
    ("manifests/b2_manifest.json", ("seeds.master_seed", "seeds.pairs[][]", "seeds.excluded_frozen_sets.*.master_seed", "qualification_plan.master_seed"),
     "aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0"),
    ("manifests/b3_manifest.json", ("seeds.master_seed", "seeds.pairs[][]", "qualification_plan.master_seed"),
     "258bb14c4b3ba1a3d33741f23b1663f563de64da800843d30c8a615e2f128628"),
    ("evidence/b2/gate/gate_report.json", GATE_SEEDS_B2, "571196bd509e5eb09897d206a634b508655bb42f293be7eeaf7fba8d4c514c43"),
    ("evidence/b2/gate/raw_F1.json", ROWS, "b821c24998dece562026d41c094509da98cfd5430b099ea52ec35dc44050e0bf"),
    ("evidence/b2/gate/raw_F2.json", ROWS, "6194ed690afd5107a76cd081f158a174d2147c3f364e331e0c58ebba74dcab5f"),
    ("evidence/b2/gate/raw_F3.json", ROWS, "8a751a23c7e3088f85f39f2da32a175648623861d525099dcfb05c93eb8111a9"),
    ("evidence/b2/gate/v0.1_2026-09-10/gate_report.json", GATE_SEEDS_B2, "d547144fce433078531b125937b946c2df94ad69d5c44f7ba37c45976984e4ce"),
    ("evidence/b2/gate/v0.1_2026-09-10/raw_F1.json", ROWS, "ffb0bf396f975585cc9bd88f7500ea188612ab2e8a5e9f59076dbd675dcab532"),
    ("evidence/b2/gate/v0.1_2026-09-10/raw_F2.json", ROWS, "859b96a03cdccd23b116a0b64e41f5f3c091ba85da4c13c404027c8b77ca7522"),
    ("evidence/b2/gate/v0.1_2026-09-10/raw_F3.json", ROWS, "f37ae4e4b38b4b9508c424bf0cedc85f1b5f88b1c3b01f75cdc2c90047fce21d"),
    ("evidence/b2/gate/recomputed_2026_09_10/gate_report.json", SOURCE_SEEDS_B2, "997317fb8763925ffcaa1ae63700471165e2f804c527648205a31622d02f625c"),
    ("evidence/b2/gate/recomputed_2026_09_10/controls_report.json", SOURCE_SEEDS_B2, "4a5042e283069f7112cf45c2dbbbb913ef81ea7d5fede97450c2d6b4084c2f89"),
    ("evidence/b2/gate/recomputed_2026_09_10/raw_controls_F1.json", ROWS, "bddc7ad93003e787cebe5fb569131d161b05d76f931212fe4e52f658bc2e4aa6"),
    ("evidence/b2/gate/recomputed_2026_09_10/raw_controls_F2.json", ROWS, "7948e974be96fd983e5155bdbb72f0d97bc646dc5a0bfdb1cda22c3188f33ed8"),
    ("evidence/b2/gate/recomputed_2026_09_10/raw_controls_F3.json", ROWS, "a5ed062f6591acc4fe782a35e8cca1910269145ce8682465f8022c181890d394"),
    ("evidence/b2/plan.json", ("seed_derivation.master_seed", "seed_derivation.excluded_fixed[]", "seed_derivation.excluded_frozen_sets.*.master_seed"),
     "62dc85934eec02e2fe31a90b336d0fd320d03a4f54bf90537e944ece72458b9c"),
    ("evidence/b2/b2q_plan.json", ("seed_derivation.master_seed", "seed_derivation.excluded_b2_pairs[][]", "seed_derivation.excluded_frozen_sets.*.master_seed", "seed_derivation.pairs[][]"),
     "3d194d76e083fd4ba3ce3cf0458af65637120fcda6761be36598833dbc659216"),
    ("evidence/b2/prediction.json", PAIRS, "a611b8e03c88fa797e2b9d9c5d10bb97e42c590bc8754f1defccc6c11c9e3731"),
    ("evidence/b2/b2q_prediction.json", PAIRS, "2ada4d5dab7ed08f081aa55bb4b6f138688a326bb859ab5d63f58c16e67b58aa"),
    ("evidence/b3/sim/sim_report.json", SIM_SEEDS, "d9c432f8b797933e26e24a77d33e5884f29c03c2be88e6c59c61bc0af250adf9"),
    ("evidence/b3/sim/raw_F1.json", ROWS, "ccf4d24622c7cfb3ee698623047ea461303c603449d47ffb0452f83656b74c53"),
    ("evidence/b3/sim/raw_F2.json", ROWS, "953511d7540bbf0a0af7932f5c8c486a03f64d3d68cda576b2ed07f6e4ed4e1c"),
    ("evidence/b3/sim_v0.1.1/sim_report.json", SIM_SEEDS, "dcbaa2a3cf2fe817c77ce24ab4a4250ec4c8a2c171117f55da9d80740e29401c"),
    ("evidence/b3/sim_v0.1.1/raw_F1.json", ROWS, "ccf4d24622c7cfb3ee698623047ea461303c603449d47ffb0452f83656b74c53"),
    ("evidence/b3/sim_v0.1.1/raw_F2.json", ROWS, "953511d7540bbf0a0af7932f5c8c486a03f64d3d68cda576b2ed07f6e4ed4e1c"),
    ("evidence/b3/gate/gate_report.json", GATE_SEEDS_B3, "477225f54bb40866abb08df69e6e34341c7516cd7e398e8bb6d0c06c8ae2aa68"),
    ("evidence/b3/gate/raw_F1.json", ROWS, "54f9c4fbc0bac8c0bfe1c6ce203f8848367d201b85b610e40c031f96c1746ed6"),
    ("evidence/b3/gate/raw_F2.json", ROWS, "279b08ede52cf73d948f69e1390e2c02c09e417ca8406bb52da78439ff1b3e2d"),
    ("evidence/b3/gate_2/gate_report.json", GATE_SEEDS_B3, "8f717b12bdc7258d49145bd47bbcfb8291d2b2a79cad42cb75491a19398fda90"),
    ("evidence/b3/gate_2/raw_F1.json", ROWS, "631aac7119dc054b9db835a756e2fbc1f56b4071f027506b13d5a3630c08b0fc"),
    ("evidence/b3/gate_2/raw_F2.json", ROWS, "cba55465bde4a35c39cc33ce0a853db4a3db5f9ac85e0ded6d671a87732cbfe5"),
    ("evidence/b3/plan.json", ("seed_derivation.master_seed", "seed_derivation.excluded_fixed[]", "seed_derivation.excluded_sources.*.master_seed"),
     "b202a2800d5934978394ffca7ee8f24d9b2897c953d4f41b1050fed840c81dd1"),
    ("evidence/b3/b3q_plan.json", ("seed_derivation.master_seed", "seed_derivation.excluded_b3_pairs[][]", "seed_derivation.excluded_sources.*.master_seed", "seed_derivation.pairs[][]"),
     "490347f4b3542147581940035a12eb9bb7db7cbd0ad550dd8bfd3e2b68261026"),
    ("evidence/b3/prediction.json", PAIRS, "92b774ea62d290d380e72a4c990b384060db9006cf9160940fb4848ae4a14cf5"),
    ("evidence/b3/b3q_prediction.json", PAIRS, "7eae26509b9488a111257c112c5cf90e9cc8f6e34311af837c79ccc40245ec27"),
    ("evidence/b3/plan_trial_2026_09_17/plan.json", ("seed_derivation.master_seed", "seed_derivation.excluded_fixed[]", "seed_derivation.excluded_sources.*.master_seed"),
     "8b6142b06b883baee2e9e8b298635429384279d2be78efab18cd73bdcc3761d2"),
    ("evidence/b3/plan_trial_2026_09_17/prediction.json", PAIRS, "6e45a752bd3db536db0cbea7dcb0e531bb40889fff91f7dc6c28250f44f729b2"),
)


class RetiredLabelRefusal(ValueError):
    """A production derivation was asked under a retired label (`RETIRED_LABELS`): refused before any master is formed."""


def check_label_not_retired(label) -> None:
    """The guard of the NEW-production-derivation path only (the harness's pre-flight and its init); never applied to the
    registry's reading of archived records, which keeps every retired label's set in the pooled exclusion."""
    if label in RETIRED_LABELS:
        raise RetiredLabelRefusal(f"the label {label!r} is retired by the owner's ruling of 2026-10-19 (its prior derivations are the exposure receipt's); "
                                  f"the next exploration label is {EXPLORATION_LABEL!r}")


class ExclusionSourceRefusal(ValueError):
    """A historical or archived seed source that cannot be read AS SPECIFIED: missing, re-hashed, malformed, mistyped."""


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def is_seed_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= SEED_MAX


def master_seed(label: str, anchor_sha256: str) -> int:
    """int.from_bytes(sha256(utf8(label + '|' + anchor))[:4], 'big'). The label is passed beside the anchor, never
    pre-joined (a '|' inside the label is refused); the anchor is a 64-hex digest."""
    if not isinstance(label, str) or not LABEL_RE.match(label):
        raise ValueError(f"the label {label!r} is not lowercase [a-z0-9-] without '|' or a leading / trailing dash")
    if not isinstance(anchor_sha256, str) or not HEX64_RE.match(anchor_sha256):
        raise ValueError("the anchor must be a lowercase 64-hex sha256 digest")
    d = hashlib.sha256(f"{label}|{anchor_sha256}".encode("utf-8")).digest()
    return int.from_bytes(d[:4], "big")


def pair_seeds(master: int, count: int, exclude) -> list[tuple[int, int]]:
    """B2's `pair_seeds`, copied (host/b2_search.py; recorded in b4/IMPORT.json): (landscape_seed, operator_seed) per pair
    from one stream off the master; every seed 32-bit; a draw is skipped when either value is in the pooled set — B2's
    frozen list plus `exclude` — or repeats a value drawn earlier, or the two values coincide; all values distinct."""
    if not is_seed_int(master):
        raise ValueError("the master seed must be a 32-bit int")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("count must be a non-negative int")
    rng = Rng(master)
    out: list[tuple[int, int]] = []
    seen: set[int] = set(B2_EXCLUDED_SEEDS) | set(exclude)
    while len(out) < count:
        l_seed = rng.next32()
        o_seed = rng.next32()
        if l_seed in seen or o_seed in seen or l_seed == o_seed:
            continue
        seen.add(l_seed)
        seen.add(o_seed)
        out.append((l_seed, o_seed))
    return out


# ------------------------------------------------------------------ the typed extraction
def _steps(path: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for tok in path.split("."):
        if tok == "*":
            out.append(("values", ""))
        elif tok == "[]":
            out.append(("list", ""))
        else:
            m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_\-]*)((?:\[\])*)", tok)
            if not m:
                raise ValueError(f"malformed field path {path!r}")
            out.append(("key", m.group(1)))
            for _ in range(len(m.group(2)) // 2):
                out.append(("list", ""))
    return out


def extract_ints(doc, path: str, where: str) -> list[int]:
    """Every leaf under `path`, each an int (not bool) in 0 .. SEED_MAX; a path that does not resolve is a refusal."""
    def walk(node, steps, trail):
        if not steps:
            if not is_seed_int(node):
                raise ExclusionSourceRefusal(f"{where}: {trail} is {node!r}, not a 32-bit seed integer")
            return [node]
        kind, name = steps[0]
        if kind == "key":
            if not isinstance(node, dict) or name not in node:
                raise ExclusionSourceRefusal(f"{where}: {trail}.{name} is missing")
            return walk(node[name], steps[1:], f"{trail}.{name}")
        if kind == "list":
            if not isinstance(node, list):
                raise ExclusionSourceRefusal(f"{where}: {trail} is not a list")
            if not node:
                raise ExclusionSourceRefusal(f"{where}: {trail} is an empty list")
            out = []
            for i, x in enumerate(node):
                out += walk(x, steps[1:], f"{trail}[{i}]")
            return out
        if not isinstance(node, dict):
            raise ExclusionSourceRefusal(f"{where}: {trail} is not an object")
        if not node:
            raise ExclusionSourceRefusal(f"{where}: {trail} is an empty object")
        out = []
        for k in sorted(node):
            out += walk(node[k], steps[1:], f"{trail}.{k}")
        return out
    return walk(doc, _steps(path), "$")


def parse_python_excluded(text: str, where: str) -> list[int]:
    m = re.search(r"EXCLUDED_SEEDS\s*=\s*frozenset\(\[(.*?)\]\)", text, re.S)
    if not m:
        raise ExclusionSourceRefusal(f"{where}: no EXCLUDED_SEEDS = frozenset([...]) line")
    try:
        vals = [int(x) for x in re.split(r"[\s,]+", m.group(1).strip()) if x]
    except ValueError as exc:
        raise ExclusionSourceRefusal(f"{where}: EXCLUDED_SEEDS is not a list of integers: {exc}") from None
    if tuple(vals) != B2_EXCLUDED_SEEDS:
        raise ExclusionSourceRefusal(f"{where}: EXCLUDED_SEEDS parses to {len(vals)} values that are not the copy kept here")
    return vals


@dataclass(frozen=True)
class SourceRecord:
    path: str                    # repository-relative
    sha256: str                  # of the bytes as read
    paths: tuple                 # the typed field paths read
    values: tuple                # every seed value found, in path order (duplicates kept here, pooled later)

    def as_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "fields": list(self.paths), "count": len(self.values), "values": list(self.values)}


def read_source(repo_root: Path, rel: str, paths: tuple, expected_sha256: str) -> SourceRecord:
    p = Path(repo_root) / rel
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise ExclusionSourceRefusal(f"{rel}: cannot be read ({exc.__class__.__name__}); a historical seed source that ought to exist is missing") from None
    got = sha256_bytes(raw)
    if got != expected_sha256:
        raise ExclusionSourceRefusal(f"{rel}: hashes to {got[:16]}…, not the recorded {expected_sha256[:16]}…")
    values: list[int] = []
    if paths == (PY_EXCLUDED,):
        values = parse_python_excluded(raw.decode("utf-8"), rel)
    else:
        try:
            doc = json.loads(raw)
        except ValueError as exc:
            raise ExclusionSourceRefusal(f"{rel}: not JSON: {exc}") from None
        for path in paths:
            values += extract_ints(doc, path, rel)
    return SourceRecord(rel, got, tuple(paths), tuple(values))


# ------------------------------------------------------------------ the archived exploration registries
def seeds_doc_findings(doc) -> list[str]:
    """The shape of an archived `seeds.json` (schema b4_sim_seeds 1.1.0), total and type-exact. `fixture` False: a
    production set — a label that is not a fixture label, an anchor, an int master. `fixture` True: a MECHANICS fixture
    set — a `b4-mech-<n>` label, `master_seed` null, `anchor.hypothesis_sha256` null, every pair value in FIXTURE_VALUES."""
    f: list[str] = []
    if not isinstance(doc, dict):
        return ["not an object"]
    want = {"schema", "schema_version", "label", "fixture", "anchor", "master_seed", "count", "pairs", "exclusion", "generated_utc"}
    if set(doc) != want:
        return [f"keys {sorted(set(doc) ^ want)} differ from the schema's"]
    if doc["schema"] != SEEDS_SCHEMA[0] or doc["schema_version"] not in SEEDS_SCHEMA_VERSIONS_READ:
        f.append("schema / schema_version")
    with_receipt = doc["schema_version"] == "1.2.0"           # 1.1.0 records (archived before the settlement of 2026-10-19) carry no receipt entry
    if not isinstance(doc["fixture"], bool):
        return f + ["fixture is not a bool"]
    fixture = doc["fixture"]
    if not (isinstance(doc["label"], str) and LABEL_RE.match(doc["label"])):
        f.append("label")
    elif fixture is not bool(FIXTURE_LABEL_RE.match(doc["label"])):
        f.append("label: a fixture set has a b4-mech-<n> label and a production set has not")
    a = doc["anchor"]
    if not (isinstance(a, dict) and set(a) == {"rule", "hypothesis_sha256", "label"} and isinstance(a["rule"], str) and a["label"] == doc["label"]):
        f.append("anchor")
    elif fixture:
        if a["hypothesis_sha256"] is not None or "fixture" not in a["rule"]:
            f.append("anchor: a fixture set has no anchor (hypothesis_sha256 null, the rule naming the fixture)")
    elif not (isinstance(a["hypothesis_sha256"], str) and HEX64_RE.match(a["hypothesis_sha256"])):
        f.append("anchor.hypothesis_sha256")
    if fixture:
        if doc["master_seed"] is not None:
            f.append("master_seed: a fixture set derives no master (null)")
    elif not is_seed_int(doc["master_seed"]):
        f.append("master_seed")
    if not (isinstance(doc["count"], int) and not isinstance(doc["count"], bool) and doc["count"] >= 0):
        f.append("count")
    pairs = doc["pairs"]
    if not (isinstance(pairs, list) and all(isinstance(p, list) and len(p) == 2 and is_seed_int(p[0]) and is_seed_int(p[1]) and p[0] != p[1] for p in pairs)):
        f.append("pairs")
    elif isinstance(doc["count"], int) and len(pairs) != doc["count"]:
        f.append(f"count {doc['count']} != {len(pairs)} pairs")
    elif fixture and any(v not in FIXTURE_VALUES for p in pairs for v in p):
        f.append("pairs: a fixture set uses already-exposed values only (FIXTURE_VALUES)")
    e = doc["exclusion"]
    want_e = {"sources", "b4_exposed_values", "sim_registry", "pooled_total"} | ({"exposure_receipt"} if with_receipt else set())
    if not (isinstance(e, dict) and set(e) == want_e):
        f.append("exclusion")
    else:
        if with_receipt:
            f.extend(receipt_reference_findings(e["exposure_receipt"], "exclusion.exposure_receipt"))
        if not (isinstance(e["sources"], list) and all(isinstance(s, dict) and set(s) == {"path", "sha256", "fields", "count", "values"} for s in e["sources"])):
            f.append("exclusion.sources")
        if not (isinstance(e["b4_exposed_values"], list) and all(is_seed_int(v) for v in e["b4_exposed_values"])):
            f.append("exclusion.b4_exposed_values")
        if not (isinstance(e["sim_registry"], list) and all(isinstance(s, dict) and set(s) == {"dir", "status", "seeds_sha256", "master_seed", "count"} for s in e["sim_registry"])):
            f.append("exclusion.sim_registry")
        if not (isinstance(e["pooled_total"], int) and not isinstance(e["pooled_total"], bool) and e["pooled_total"] >= 0):
            f.append("exclusion.pooled_total")
    if not isinstance(doc["generated_utc"], str):
        f.append("generated_utc")
    return f


@functools.lru_cache(maxsize=4)
def _pinned_receipt_count(pinned_sha256: str) -> int:
    return len(read_exposure_receipt(REPO_ROOT).values)


def pinned_receipt_count() -> int:
    """The AUTHORITATIVE count a record's receipt reference must carry: the pooled length of the pinned receipt in the code
    tree, read and hash-verified (`read_exposure_receipt`); never a literal kept apart from the file. Raises
    `ExclusionSourceRefusal` when the pinned receipt cannot be read (the owner's review of 2026-10-19 on 1d9525c)."""
    return _pinned_receipt_count(EXPOSURE_RECEIPT_SHA256)


def receipt_reference_findings(ref, where: str) -> list[str]:
    """A record's reference to the exposure receipt: exactly the pinned path and digest, and a count equal to the pooled
    length of the hash-verified pinned receipt (two records agreeing with each other is not enough)."""
    if not (isinstance(ref, dict) and set(ref) == {"path", "sha256", "count"}):
        return [f"{where}: keys"]
    f: list[str] = []
    if ref["path"] != EXPOSURE_RECEIPT_REL:
        f.append(f"{where}.path is not the pinned receipt's")
    if ref["sha256"] != EXPOSURE_RECEIPT_SHA256:
        f.append(f"{where}.sha256 is not the pinned receipt's digest")
    if not (isinstance(ref["count"], int) and not isinstance(ref["count"], bool) and ref["count"] >= 0):
        return f + [f"{where}.count"]
    try:
        n = pinned_receipt_count()
    except ExclusionSourceRefusal as exc:
        return f + [f"{where}.count cannot be bound: the pinned receipt does not read ({exc})"]
    if ref["count"] != n:
        f.append(f"{where}.count {ref['count']} is not the pinned receipt's pooled length {n}")
    return f


def canonical_ints(values) -> str:
    return json.dumps(list(values), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def receipt_findings(doc) -> list[str]:
    """The exposure receipt (schema b4_exposure_receipt 1.0.0), total and type-exact: the pooled list is sorted, distinct
    32-bit seed ints with its count and the digest of its canonical JSON text; every variant carries a RETIRED label and its
    master, pair and control values are in the pooled list; every value entry is in the pooled list with known classes, and
    the value entries are exactly the pooled list. Never raises."""
    try:
        if not isinstance(doc, dict):
            return ["not an object"]
        if set(doc) != RECEIPT_KEYS:
            return [f"keys {sorted(set(doc) ^ RECEIPT_KEYS)} differ from the schema's"]
        f: list[str] = []
        if (doc["schema"], doc["schema_version"]) != RECEIPT_SCHEMA:
            f.append("schema / schema_version")
        pooled = doc["pooled"]
        if not (isinstance(pooled, list) and all(is_seed_int(v) for v in pooled) and pooled == sorted(set(pooled))):
            return f + ["pooled: not a sorted list of distinct 32-bit seed ints"]
        if not (isinstance(doc["pooled_count"], int) and not isinstance(doc["pooled_count"], bool) and doc["pooled_count"] == len(pooled)):
            f.append("pooled_count is not the pooled list's length")
        if doc["pooled_sha256"] != sha256_bytes(canonical_ints(pooled).encode()):
            f.append("pooled_sha256 is not the digest of the pooled list's canonical text")
        pool = set(pooled)
        if not (isinstance(doc["variants"], list) and doc["variants"]):
            f.append("variants")
        else:
            for v in doc["variants"]:
                ok = (isinstance(v, dict) and {"id", "label", "master_seed", "pairs", "control_seeds"} <= set(v) and v["label"] in RETIRED_LABELS
                      and is_seed_int(v["master_seed"]) and v["master_seed"] in pool
                      and isinstance(v["pairs"], list) and all(isinstance(p, list) and len(p) == 2 and all(is_seed_int(x) and x in pool for x in p) for p in v["pairs"])
                      and isinstance(v["control_seeds"], list) and all(isinstance(c, dict) and is_seed_int(c.get("x_control_seed")) and c["x_control_seed"] in pool
                                                                       and is_seed_int(c.get("d_shuffle_seed")) and c["d_shuffle_seed"] in pool for c in v["control_seeds"]))
                if not ok:
                    f.append(f"variants[{v.get('id') if isinstance(v, dict) else '?'}]: a retired label, a 32-bit master and pairs and control seeds all in the pooled list")
        vals = doc["values"]
        if not (isinstance(vals, list) and all(isinstance(e, dict) and is_seed_int(e.get("value")) and isinstance(e.get("classes"), list) and e["classes"]
                                               and set(e["classes"]) <= RECEIPT_CLASSES for e in vals) and sorted(e["value"] for e in vals) == pooled):
            f.append("values: every entry a pooled value with known classes, the entries exactly the pooled list")
        for k in ("status", "ruling", "reconstruction_utc", "reconstruction_script"):
            if not isinstance(doc[k], str):
                f.append(k)
        if not (isinstance(doc["historical_inputs"], dict) and isinstance(doc["envelope"], dict) and isinstance(doc["preserved_records"], list) and isinstance(doc["limits"], list)
                and isinstance(doc["already_in_base_pool"], list)):
            f.append("historical_inputs / envelope / preserved_records / limits / already_in_base_pool")
        return f
    except Exception as exc:  # noqa: BLE001 — a validator never raises
        return [f"receipt_findings: the validator raised {type(exc).__name__}: {exc} — the document is malformed"]


@dataclass(frozen=True)
class ReceiptRecord:
    path: str                    # EXPOSURE_RECEIPT_REL
    sha256: str                  # the file's digest (== EXPOSURE_RECEIPT_SHA256, or the loader refused)
    values: tuple                # the pooled list, sorted

    def as_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "count": len(self.values)}


def read_exposure_receipt(repo_root: Path) -> ReceiptRecord:
    """The exposure receipt under the root, held to its pinned digest and its schema; missing, unreadable, re-hashed or
    malformed is `ExclusionSourceRefusal` by name, never skipped."""
    p = Path(repo_root) / EXPOSURE_RECEIPT_REL
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise ExclusionSourceRefusal(f"{EXPOSURE_RECEIPT_REL}: the exposure receipt is missing or unreadable ({type(exc).__name__}); the exclusion set cannot be formed without it") from None
    got = sha256_bytes(raw)
    if got != EXPOSURE_RECEIPT_SHA256:
        raise ExclusionSourceRefusal(f"{EXPOSURE_RECEIPT_REL}: the exposure receipt hashes to {got[:16]}…, not its pinned {EXPOSURE_RECEIPT_SHA256[:16]}… (re-hashed or replaced; never skipped)")
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise ExclusionSourceRefusal(f"{EXPOSURE_RECEIPT_REL}: not JSON ({exc})") from None
    f = receipt_findings(doc)
    if f:
        raise ExclusionSourceRefusal(f"{EXPOSURE_RECEIPT_REL}: malformed: " + "; ".join(f))
    return ReceiptRecord(EXPOSURE_RECEIPT_REL, got, tuple(doc["pooled"]))


def init_failed_findings(doc) -> list[str]:
    if not isinstance(doc, dict):
        return ["not an object"]
    want = {"schema", "schema_version", "label", "seeds_derived", "reason", "generated_utc"}
    if set(doc) != want:
        return [f"keys {sorted(set(doc) ^ want)} differ from the schema's"]
    f: list[str] = []
    if (doc["schema"], doc["schema_version"]) != INIT_FAILED_SCHEMA:
        f.append("schema / schema_version")
    if not isinstance(doc["seeds_derived"], bool):
        f.append("seeds_derived")
    if not isinstance(doc["reason"], str):
        f.append("reason")
    return f


@dataclass(frozen=True)
class RegistryRecord:
    dir: str                     # repository-relative run directory
    status: str                  # "seeds" (a production seeds.json), "seeds_fixture" (a mechanics fixture set) or "init_failed_no_seeds"
    seeds_sha256: str | None
    master_seed: int | None      # None for a fixture set (no master is derived)
    values: tuple                # the master and every planned pair value (a fixture set: its pair values; init_failed_no_seeds: empty)

    def as_dict(self) -> dict:
        return {"dir": self.dir, "status": self.status, "seeds_sha256": self.seeds_sha256, "master_seed": self.master_seed, "count": len(self.values)}


def sim_registry(repo_root: Path, sim_rel: str = SIM_REL) -> tuple[list[RegistryRecord], str]:
    """Every run directory under evidence/b4/sim/, in path order. Returns (records, note); the note says whether the
    directory existed. A directory without a valid seeds.json or a no-seeds INIT_FAILED.json is a refusal."""
    root = Path(repo_root) / sim_rel
    if not root.exists():
        return [], f"{sim_rel}/ does not exist yet (not a missing source)"
    if not root.is_dir():
        raise ExclusionSourceRefusal(f"{sim_rel} exists and is not a directory")
    out: list[RegistryRecord] = []
    for d in sorted(p for p in root.iterdir()):
        rel = f"{sim_rel}/{d.name}"
        if not d.is_dir():
            raise ExclusionSourceRefusal(f"{rel}: a non-directory entry inside the exploration namespace")
        seeds_p, init_p = d / SEEDS_FILE, d / INIT_FAILED_FILE
        if seeds_p.exists():
            try:
                raw = seeds_p.read_bytes()
                doc = json.loads(raw)
            except (OSError, ValueError) as exc:
                raise ExclusionSourceRefusal(f"{rel}/{SEEDS_FILE}: unreadable ({exc.__class__.__name__}); an archived set is never skipped") from None
            f = seeds_doc_findings(doc)
            if f:
                raise ExclusionSourceRefusal(f"{rel}/{SEEDS_FILE}: malformed: " + "; ".join(f))
            vals = ([] if doc["fixture"] else [doc["master_seed"]]) + [v for p in doc["pairs"] for v in p]
            out.append(RegistryRecord(rel, "seeds_fixture" if doc["fixture"] else "seeds", sha256_bytes(raw), doc["master_seed"], tuple(vals)))
        elif init_p.exists():
            try:
                doc = json.loads(init_p.read_bytes())
            except (OSError, ValueError) as exc:
                raise ExclusionSourceRefusal(f"{rel}/{INIT_FAILED_FILE}: unreadable ({exc.__class__.__name__})") from None
            f = init_failed_findings(doc)
            if f:
                raise ExclusionSourceRefusal(f"{rel}/{INIT_FAILED_FILE}: malformed: " + "; ".join(f))
            if doc["seeds_derived"]:
                raise ExclusionSourceRefusal(f"{rel}: INIT_FAILED.json says seeds were derived but no {SEEDS_FILE} is present")
            out.append(RegistryRecord(rel, "init_failed_no_seeds", None, None, ()))
        else:
            raise ExclusionSourceRefusal(f"{rel}: neither {SEEDS_FILE} nor {INIT_FAILED_FILE}; a run directory with no seed record is refused, never skipped")
    return out, f"{sim_rel}/ holds {len(out)} run directories"


# ------------------------------------------------------------------ the pooled set
@dataclass(frozen=True)
class ExclusionSet:
    sources: tuple               # SourceRecord per historical file, in FIELDS order
    b4_exposed: tuple            # sorted B4_EXPOSED_VALUES
    registry: tuple              # RegistryRecord per archived run directory
    registry_note: str
    receipt: ReceiptRecord       # the exposure receipt (the settlement of 2026-10-19), held to its pinned digest
    values: frozenset = field(default_factory=frozenset)

    def as_dict(self) -> dict:
        return {"sources": [s.as_dict() for s in self.sources], "b4_exposed_values": list(self.b4_exposed),
                "sim_registry": [r.as_dict() for r in self.registry], "sim_registry_note": self.registry_note,
                "exposure_receipt": self.receipt.as_dict(),
                "b2_excluded_seeds_copy": list(B2_EXCLUDED_SEEDS), "pooled_total": len(self.values)}


def load_exclusion_set(repo_root: Path = REPO_ROOT, sim_rel: str = SIM_REL) -> ExclusionSet:
    """The 38 historical sources under `repo_root`, B4's exposed values, the exposure receipt under the root and every
    archived set under `sim_rel` (relative to the root, or an absolute path for a hermetic test tree) — one pooled set."""
    sources = tuple(read_source(repo_root, rel, paths, sha) for rel, paths, sha in FIELDS)
    receipt = read_exposure_receipt(repo_root)
    registry, note = sim_registry(repo_root, sim_rel)
    pooled: set[int] = set(B2_EXCLUDED_SEEDS) | set(B4_EXPOSED_VALUES)
    for s in sources:
        pooled.update(s.values)
    pooled.update(receipt.values)
    for r in registry:
        pooled.update(r.values)
    return ExclusionSet(sources, tuple(sorted(B4_EXPOSED_VALUES)), tuple(registry), note, receipt, frozenset(pooled))


if __name__ == "__main__":
    ex = load_exclusion_set()
    print(json.dumps({k: v for k, v in ex.as_dict().items() if k != "sources"} | {"sources": len(ex.sources)}, indent=1))
