#!/usr/bin/env python3
"""Read-only: does the corrected v0.3 draft answer the owner's three P2 and the P3 of
docs/b2_prereg_v03_review_2026_09_16.md? The owner's own probe anchored on the old
ordering sentence and raises ValueError on the corrected text (recorded alongside), so the
same facts are recomputed here without literal anchors. Diagnostic only, never a proof."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "host"))
import b2_manifest as bman  # noqa: E402

text = (ROOT / "docs/b2_preregistration.md").read_text()
sec8a = text[text.index("## 8a."):]
ordering = sec8a[sec8a.index("**The ordering the pin table imposes"):]
steps = re.findall(r"^\s*(\d+)\.\s+(.*?)(?=^\s*\d+\.\s|\n\nBetween)", ordering, re.S | re.M)
step_text = {int(n): " ".join(t.split()) for n, t in steps}


def step_of(needle: str) -> int | None:
    for n, t in sorted(step_text.items()):
        if needle in t:
            return n
    return None


ids = {"s0_initial": "af271747", "s0_final": "86393ed7", "s1": "86997677", "s2": "e6b8db65", "s3": "5d2312c3", "prereg_v02": "68cde86d"}
non_input = sec8a[sec8a.index("**What is NOT an input"):sec8a.index("**The ordering the pin table imposes")]
image_row = next(l for l in text.splitlines() if l.startswith("| B2 image |"))
init_with = bman.init(ROOT / "evidence/b2/build_evidence.json")["image"]
init_without = bman.init(None)["image"]
old_prediction = subprocess.check_output(["git", "show", "87c321f:evidence/b2/prediction.json"], cwd=ROOT)

out = {
    "p2_1_image": {
        "row_says_not_built": "**not built**" in image_row,
        "row_names_digest_size_elf_evidence": all(k in image_row for k in ("d164cd1d", "114 708", "7de96ed2", "ce58eaf3")),
        "init_with_evidence_note": init_with["note"],
        "init_with_evidence_note_stale": "no B2 image exists yet" in init_with["note"],
        "init_without_evidence_note_stale": "no B2 image exists yet" in init_without["note"],
        "production_test_named": "test_0a_the_image_note_says_what_the_image_record_says" in image_row,
    },
    "p2_2_proofs": {
        "steps": step_text,
        "s0_proof_step": step_of("clean-tree proof at S0"),
        "s1_freeze_step": step_of("S1 freeze of *this* document"),
        "post_freeze_proof_step": step_of("post-freeze clean-tree proof"),
        "post_freeze_proof_bound_to_actual_s1_manifest": "actual frozen S1 manifest's sha256" in ordering,
        "b2q_ruling_step": step_of("the B2Q ruling pair (bound to that S1 manifest's sha256"),
        "s3_step": step_of("S3 plan"),
        "final_proof_step": step_of("final clean-tree proof"),
        "b2_rulings_step": step_of("B2 ruling pairs, each bound to the S3 manifest"),
    },
    "p2_3_identities": {
        "all_four_manifests_named_in_8a": {k: (v in sec8a) for k, v in ids.items()},
        "prereg_digest_labelled_as_document_not_manifest": "is the value written into `prereg.sha256` at S1; it is not a manifest identity" in sec8a,
        "s1_manifest_named_as_b2q_binding": "bound to the S1 manifest\n`86997677" in sec8a or "bound to the S1 manifest `86997677" in " ".join(sec8a.split()),
        "non_input_list_names_every_identity": {k: (v in non_input) for k, v in ids.items()},
    },
    # the owner's round 2 (docs/b2_prereg_v03_round2_review_2026_09_16.md)
    "round2_p2_step8_split": {
        "ruling_step": step_of("the B2Q ruling pair (bound to that S1 manifest's sha256"),
        "board_session_step": step_of("the B2Q board session under that ruling pair"),
        "s2_transition_step": step_of("S2 qualify"),
        "s2_proof_step": step_of("clean-tree proof at S2"),
        "s2_proof_required_before_s3": "required before S3" in (step_text.get(step_of("clean-tree proof at S2") or -1, "")),
    },
    "round2_p3_1_s0_rows": {
        "fa0271e_paired_with_af271747": "`fa0271e`) | `af2717476a518f3fcb31d5c76599a17585367fdc421f9607b06aaca424924540`" in sec8a,
        "01acb5f_paired_with_86393ed7": "`01acb5f`, pushed at `9429088`) | `86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`" in sec8a,
        "fa0271e_paired_with_86393ed7": "S0 init (`fa0271e`) | `86393ed7" in sec8a,
    },
    "round2_p3_2_change_count": {
        "still_says_exactly_three": "v0.3 changes exactly three things" in text,
        "says_four_with_item_iv": "v0.3 changes four things" in text and "(iv) the §2 image pin says the image **is built**" in text,
    },
    "p3_stagecoverage_claim": {
        "says_each_guard_removed": "against each guard removed" in text,
        "says_each_of_the_two_pin_summary_guards_removed": "each of the two pin-summary guards removed" in text,
    },
    "prediction_unchanged": (ROOT / "evidence/b2/prediction.json").read_bytes() == old_prediction,
    "draft_sha256": hashlib.sha256((ROOT / "docs/b2_preregistration.md").read_bytes()).hexdigest(),
    "diagnostic_only": True,
}
o = out["p2_2_proofs"]
o["order_ok"] = (o["s0_proof_step"] is not None and o["s1_freeze_step"] is not None and o["post_freeze_proof_step"] is not None
                 and o["b2q_ruling_step"] is not None and o["s3_step"] is not None and o["final_proof_step"] is not None
                 and o["b2_rulings_step"] is not None
                 and o["s0_proof_step"] < o["s1_freeze_step"] < o["post_freeze_proof_step"] < o["b2q_ruling_step"]
                 < o["s3_step"] < o["final_proof_step"] < o["b2_rulings_step"])
print(json.dumps(out, indent=2, sort_keys=True))
