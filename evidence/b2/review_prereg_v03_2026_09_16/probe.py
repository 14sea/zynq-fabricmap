#!/usr/bin/env python3
"""Read-only consistency probe for the lifecycle-2 preregistration draft v0.3."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
prereg_path = ROOT / "docs/b2_preregistration.md"
text = prereg_path.read_text()
manifest = json.loads((ROOT / "manifests/b2_manifest.json").read_text())
transition = json.loads((ROOT / "evidence/b2/s1_2026_09_13/transition.json").read_text())
s1_report = json.loads((ROOT / "evidence/b2/tests/test_report_2026-09-13T053400Z.json").read_text())
image_path = ROOT / manifest["image"]["path"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


old_prediction = subprocess.check_output(
    ["git", "show", "87c321f:evidence/b2/prediction.json"], cwd=ROOT
)

ordering = text[text.index("**The ordering the pin table imposes"):]

print(json.dumps({
    "draft": {
        "sha256": sha(prereg_path),
        "claims_image_not_built": "| B2 image | **not built**" in text,
        "claims_each_guard_removed": "against each guard removed" in text,
    },
    "image_observed": {
        "path": manifest["image"]["path"],
        "exists": image_path.is_file(),
        "bytes": image_path.stat().st_size,
        "sha256": sha(image_path),
        "manifest_sha256": manifest["image"]["sha256"],
        "manifest_note": manifest["image"]["note"],
        "build_evidence_exists": (ROOT / manifest["image"]["build_evidence"]["path"]).is_file(),
    },
    "lifecycle1_binding": {
        "prereg_sha256": transition["prereg_sha256"],
        "s0_manifest_sha256": transition["manifest_before_sha256"],
        "s1_manifest_sha256": transition["manifest_after_sha256"],
        "post_freeze_report_manifest_sha256": s1_report["artifacts_sha256"]["manifests/b2_manifest.json"],
        "distinct_prereg_and_s1_manifest": transition["prereg_sha256"] != transition["manifest_after_sha256"],
    },
    "ordering": {
        "s0_proof_before_s1_freeze": ordering.index("whole suite\ngreen and a clean-tree proof") < ordering.index("S1 freeze"),
        "mentions_post_freeze_proof": "post-freeze" in ordering,
        "runs_directly_from_s3_to_b2_rulings": "B2Q, S2, S3, and only then B2 ruling pairs" in ordering,
        "literal_tail": ordering.splitlines()[-5:],
    },
    "prediction": {
        "current_sha256": sha(ROOT / "evidence/b2/prediction.json"),
        "pre_v03_sha256": hashlib.sha256(old_prediction).hexdigest(),
        "unchanged": (ROOT / "evidence/b2/prediction.json").read_bytes() == old_prediction,
    },
}, indent=2, sort_keys=True))
