#!/usr/bin/env python3
"""Assemble a `carrier_run` bundle: the one place a carrier's authority is pinned.

Erratum 001 made bit invariance against **one exact bitstream** the safety authority. The
first version of that left the judgement scattered across command-line arguments — a gate
was handed `--map`, `--map-lut-key` and `--build-dir` and judged whatever it was pointed
at, so the operator chose the authority. That is the same defect as a gate that asks the
builder what to expect.

This bundle is the fix. It names every input, pins each by sha256, and records the ECO's
`by_lut` key **derived** from the tilegrid rather than typed in. `gate_carrier_base.py`
and `gate_init_eco.py` take a run directory and nothing else: every path and every
expected digest comes from here.

The bundle does not pin itself. That is the publication gate's job
(`gate_publish_carrier_run.py`), which reads the git index.

**Derivation, not assertion, for the LUT key.** The ECO record carries a device site
(`SLICE_X2Y25`) and a BEL (`SLICEL.A6LUT`); the map is indexed by prjxray's in-tile naming
(`CLBLL_L.SLICEL_X0.ALUT`). The bridge is the tilegrid: which tile holds that site, of what
type, and which position the site occupies among the tile's sites ordered by X. Typing the
key in by hand would let a wrong one through and make the differential judge the wrong LUT.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402

TOOL_VERSION = "build_carrier_run.py/1.0.0"
SCHEMA_VERSION = "1.0.0"

# The artifacts a carrier run is, and which of them are LFS-backed binaries.
LFS_ARTIFACTS = ("carrier.bit", "carrier_eco.bit", "post_route.dcp")
TEXT_ARTIFACTS = (
    "local_map.json",
    "phenotype_manifest.json",
    "carrier_build.json",
    "carrier_eco.json",
    "isolation.txt",
)


class RunError(Exception):
    """A refusal."""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_lut_key(loc: str, bel: str, tilegrid: dict) -> str:
    """`SLICE_X2Y25` + `SLICEL.A6LUT` -> `CLBLL_L.SLICEL_X0.ALUT`, from the tilegrid."""
    holders = [name for name, t in tilegrid.items() if loc in (t.get("sites") or {})]
    if len(holders) != 1:
        raise RunError(f"{loc} is held by {len(holders)} tiles, expected exactly 1")
    tile = tilegrid[holders[0]]
    sites = tile["sites"]

    def site_x(name: str) -> int:
        m = re.match(r"SLICE_X(\d+)Y\d+$", name)
        if not m:
            raise RunError(f"unparsable site name {name!r}")
        return int(m.group(1))

    ordered = sorted(sites, key=site_x)
    index = ordered.index(loc)
    site_type = sites[loc]                       # SLICEL / SLICEM

    m = re.match(r"(?:SLICE[LM]\.)?([A-D])6LUT$", bel)
    if not m:
        raise RunError(f"BEL {bel!r} is not a 6LUT this map can be indexed by")
    return f"{tile['type']}.{site_type}_X{index}.{m.group(1)}LUT"


def build(run_dir: Path, run_id: str) -> dict:
    artifacts: dict[str, dict] = {}
    for name in LFS_ARTIFACTS + TEXT_ARTIFACTS:
        path = run_dir / name
        if not path.is_file():
            raise RunError(f"the run directory has no {name}")
        artifacts[name] = {
            "sha256": sha256_of(path),
            "bytes": path.stat().st_size,
            "lfs": name in LFS_ARTIFACTS,
        }

    build_rec = json.loads((run_dir / "carrier_build.json").read_text(encoding="utf-8"))
    eco_rec = json.loads((run_dir / "carrier_eco.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "phenotype_manifest.json").read_text(encoding="utf-8"))

    # The bundle must not disagree with the records it bundles.
    if build_rec.get("bitstream_sha256") != artifacts["carrier.bit"]["sha256"]:
        raise RunError("carrier_build.json's bitstream sha256 is not the carrier.bit here")
    if build_rec.get("post_route_dcp_sha256") != artifacts["post_route.dcp"]["sha256"]:
        raise RunError("carrier_build.json's DCP sha256 is not the post_route.dcp here")
    if build_rec.get("isolation_evidence_sha256") != artifacts["isolation.txt"]["sha256"]:
        raise RunError("carrier_build.json's evidence sha256 is not the isolation.txt here")
    if eco_rec.get("bitstream_sha256") != artifacts["carrier_eco.bit"]["sha256"]:
        raise RunError("carrier_eco.json's bitstream sha256 is not the carrier_eco.bit here")
    base = (manifest.get("base_bitstream") or {})
    if base.get("sha256") != artifacts["carrier.bit"]["sha256"]:
        raise RunError("the manifest's base is not the carrier.bit in this run")

    # the manifest must point at the artifacts published HERE, not at a build directory
    for key, want in (("base_bitstream", "carrier.bit"), ("local_map", "local_map.json")):
        declared = (manifest.get(key) or {}).get("path", "")
        if Path(declared).name != want or "build/" in declared:
            raise RunError(
                f"the manifest's {key}.path is {declared!r}: it must point at the published "
                f"{want}, not at a build directory nobody else has"
            )
    if (manifest.get("local_map") or {}).get("sha256") != artifacts["local_map.json"]["sha256"]:
        raise RunError("the manifest's local_map sha256 is not the local_map.json here")

    tilegrid = json.loads(Path(bf.TILEGRID).read_text(encoding="utf-8"))
    lut_key = derive_lut_key(eco_rec["loc"], eco_rec["bel"], tilegrid)

    local_map = json.loads((run_dir / "local_map.json").read_text(encoding="utf-8"))
    if lut_key not in local_map["index"]["by_lut"]:
        raise RunError(
            f"the derived LUT key {lut_key!r} is not in the map's by_lut index; "
            f"have {sorted(local_map['index']['by_lut'])}"
        )

    return {
        "schema": "carrier_run",
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "part": build_rec.get("part"),
        "artifacts": artifacts,
        "eco": {
            "cell": eco_rec.get("cell"),
            "loc": eco_rec.get("loc"),
            "bel": eco_rec.get("bel"),
            "map_lut_key": lut_key,
            "map_lut_key_derivation": "tilegrid: site -> tile, tile type, site index by X",
            "init_before": eco_rec.get("init_before"),
            "init_after": eco_rec.get("init_after"),
        },
        "tool_versions": {"builder": TOOL_VERSION},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    run_id = args.run_id or args.run_dir.resolve().name
    try:
        doc = build(args.run_dir, run_id)
    except (RunError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    out = args.run_dir / "carrier_run.json"
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"{out}: {len(doc['artifacts'])} artifacts, ECO LUT key {doc['eco']['map_lut_key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
