#!/usr/bin/env python3
"""B1Q — the CARRIER QUALIFICATION runner. Ruling text `whole-of-run B1 carrier qualification`.
HOST-ONLY UNTIL RULED. docs/b1_carrier_qualification.md §3.

    b1q_runner.py --ruling <B1Q whole-of-run json> --provision-ruling <P3-K json bound to session B1Q>
                  --boundary <principal_boundary json> --out <evidence dir> --image <b1_app.bin> [...]

The mapping runner's preflight and session function under the QUALIFICATION profile
(host/b1_runner.py): session "B1Q", the manifest's pinned qualification plan (budget 9,
eleven records, every one audited), the B1 image and the B1 carrier, no qualification
required of the carrier (this session is what produces it). After the session the B1Q
adjudicator (host/b1q_adjudicate.py) runs over the evidence as written and the
qualification RECORD (host/b1_qualification.py) is left beside it as `qualification.json`.
The owner pins a PASS record into the manifest with `b1_manifest.py --qualification <dir>`;
`carrier.qualified` is derived from it and re-verified by every later runner.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_runner as rn  # noqa: E402

if __name__ == "__main__":
    sys.exit(rn.main(profile=rn.QUALIFICATION))
