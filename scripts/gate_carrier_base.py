#!/usr/bin/env python3
"""Refuse a phenotype_manifest whose base is not THE final routed carrier bitstream.

Architecture erratum 001 moved the safety authority from "no foreign net is routed through
a written frame" to "every non-evolutionary bit of every written frame equals the final
carrier base". That sentence is only worth anything if "the final carrier base" is pinned
by a machine rather than by convention, because the failure it guards against is quiet: a
manifest built from an earlier probe bitstream, or from a DCP-era build, would still gate
candidates happily and would compare them against frames the device is not running.

So this refuses unless all of the following hold:

* the build directory carries a `carrier_build` provenance record, written by
  `build_carrier.tcl` at the moment it wrote the bitstream — the only point in the flow that
  knows the file is the routed design whose cell isolation passed;
* that record says the design was routed and cell isolation passed;
* the bitstream file on disk still hashes to what the record says;
* the manifest's `base_bitstream.sha256` equals that same hash;
* the post-route DCP and the isolation evidence still hash to what the record says, so the
  artifacts the record vouches for have not been swapped underneath it.

**Two builds of identical RTL do NOT produce identical files.** `write_bitstream` stamps a
timestamp into the header, so the frames match while the file hash does not — measured, not
assumed: two consecutive builds of this carrier gave `dd8bf0b8…` and `e677d097…`. That is
precisely why the binding is to one file rather than to "a bitstream built from this RTL",
and why re-running the build invalidates an existing manifest.

Exit codes: 0 accepted, 2 refused, 3 usage/IO.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

TOOL_VERSION = "gate_carrier_base.py/1.0.0"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def findings(build_dir: Path, manifest_path: Path) -> list[dict]:
    """Every check, always all of them: a first-failure return hides the rest."""
    out: list[dict] = []

    def bad(kind: str, message: str, **detail):
        out.append({"kind": kind, "message": message, **detail})

    prov_path = build_dir / "carrier_build.json"
    if not prov_path.is_file():
        bad(
            "provenance",
            "no carrier_build.json in the build directory: the bitstream was not written "
            "by a run of build_carrier.tcl that recorded what it was",
            path=str(prov_path),
        )
        return out

    try:
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        bad("provenance", f"carrier_build.json is unreadable: {exc}", path=str(prov_path))
        return out

    if prov.get("schema") != "carrier_build":
        bad("provenance", f"not a carrier_build record: schema={prov.get('schema')!r}")
    if prov.get("routed") is not True:
        bad("provenance", f"the record does not claim a routed design: routed={prov.get('routed')!r}")
    if prov.get("cell_isolation") != "passed":
        bad(
            "isolation",
            "the record does not carry a passing cell-isolation verdict: "
            f"cell_isolation={prov.get('cell_isolation')!r}",
        )

    # the artifacts the record vouches for must still be the ones on disk
    for key, name in (
        ("bitstream_sha256", prov.get("bitstream", "carrier.bit")),
        ("post_route_dcp_sha256", "post_route.dcp"),
        ("isolation_evidence_sha256", "isolation.txt"),
    ):
        recorded = prov.get(key)
        path = build_dir / name
        if not recorded:
            bad("provenance", f"the record has no {key}")
            continue
        if not path.is_file():
            bad("artifact", f"{name} is missing but the record vouches for it", path=str(path))
            continue
        actual = sha256_of(path)
        if actual != recorded:
            bad(
                "artifact",
                f"{name} does not match the build record",
                path=str(path),
                recorded=recorded,
                actual=actual,
            )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        bad("manifest", f"the manifest is unreadable: {exc}", path=str(manifest_path))
        return out

    if manifest.get("schema") != "phenotype_manifest":
        bad("manifest", f"not a phenotype_manifest: schema={manifest.get('schema')!r}")

    base_sha = (manifest.get("base_bitstream") or {}).get("sha256")
    if base_sha != prov.get("bitstream_sha256"):
        bad(
            "binding",
            "the manifest's base bitstream is NOT the bitstream this build wrote",
            manifest_base_sha256=base_sha,
            build_bitstream_sha256=prov.get("bitstream_sha256"),
        )

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build-dir", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--json", type=Path, help="write the verdict here")
    args = ap.parse_args()

    if not args.build_dir.is_dir():
        print(f"no such build directory: {args.build_dir}", file=sys.stderr)
        return 3

    problems = findings(args.build_dir, args.manifest)
    verdict = {
        "tool": TOOL_VERSION,
        "build_dir": str(args.build_dir),
        "manifest": str(args.manifest),
        "accepted": not problems,
        "findings": problems,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    if problems:
        for p in problems:
            print(f"REFUSED [{p['kind']}] {p['message']}", file=sys.stderr)
            for k, v in p.items():
                if k not in ("kind", "message"):
                    print(f"           {k}: {v}", file=sys.stderr)
        return 2

    print(
        f"ACCEPTED: the manifest's base is the final routed carrier bitstream "
        f"({(json.loads((args.build_dir / 'carrier_build.json').read_text()))['bitstream_sha256'][:12]}…), "
        "routed, cell isolation passed, artifacts unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
