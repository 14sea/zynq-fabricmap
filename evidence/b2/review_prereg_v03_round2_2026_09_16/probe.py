#!/usr/bin/env python3
"""Read-only precision checks for preregistration v0.3 round 2."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
path = ROOT / "docs/b2_preregistration.md"
text = path.read_text()
sec8a = text[text.index("## 8a."):]
ordering = sec8a[sec8a.index("**The ordering the pin table imposes"):]
steps = {int(n): " ".join(body.split()) for n, body in re.findall(
    r"^\s*(\d+)\.\s+(.*?)(?=^\s*\d+\.\s|\n\nBetween)", ordering, re.S | re.M
)}


def git_blob_sha(commit: str, rel: str) -> str:
    raw = subprocess.check_output(["git", "show", f"{commit}:{rel}"], cwd=ROOT)
    return hashlib.sha256(raw).hexdigest()


step8 = steps[8]
print(json.dumps({
    "draft_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "original_findings_closed": {
        "image_row_built": "| B2 image | **built**" in text,
        "post_freeze_proof_precedes_b2q": steps[7].startswith("**the post-freeze clean-tree proof**")
            and "required before the B2Q" in steps[7],
        "final_proof_precedes_b2_rulings": steps[10].startswith("**the final clean-tree proof**")
            and "required before any B2 ruling" in steps[10],
        "all_four_manifest_prefixes_named": all(x in sec8a for x in
            ("86393ed7", "86997677", "e6b8db65", "5d2312c3")),
        "p3_phrase_narrowed": "each of the two pin-summary guards removed" in text,
    },
    "composite_step_8": {
        "text": step8,
        "contains_ruling": "B2Q ruling pair" in step8,
        "contains_board_session": "B2Q" in step8,
        "contains_s2_transition": "S2 qualify" in step8,
        "contains_s2_proof": "clean-tree proof at S2" in step8,
        "document_says_each_numbered_step_is_separately_authorised":
            "each step a separately authorised transition" in ordering,
    },
    "s0_provenance": {
        "table_pairs_fa0271e_with_86393": "S0 init (`fa0271e`) | `86393ed7" in sec8a,
        "manifest_at_fa0271e": git_blob_sha("fa0271e", "manifests/b2_manifest.json"),
        "manifest_at_01acb5f": git_blob_sha("01acb5f", "manifests/b2_manifest.json"),
        "table_manifest": "86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1",
    },
    "change_count_statement": {
        "still_says_exactly_three": "v0.3 changes exactly three things" in text,
        "now_has_image_init_contract": "The image record's `note` must say what the record says" in text,
    },
}, indent=2, sort_keys=True))
