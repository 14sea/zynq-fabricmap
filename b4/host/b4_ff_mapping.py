#!/usr/bin/env python3
"""B4-FF — the CERTIFICATE MAPPING of one site: which address carries which storage element and which
semantic, read from the clb_ff_config certificate and nothing else (docs/b4_architecture.md section 4.4).

    mapping = site_mapping()            # SLICE_X2Y25, the mine site (the owner's ruling 1 of 2026-10-17); the committed
                                        # certificate, held to CERTIFICATE_SHA256 — any other file needs its digest given
                                        # explicitly (`site_mapping(path, expected_sha256=...)`, the fixture boundary)
    mapping.addresses                   # the 21 addresses, sorted, "0x00400a00/52/16" (self_map v2's address form)
    mapping.entries[address]            # element, semantic, feature names, the reading of bit = 1, the specimen pair
    mapping.genome_bit(address)         # the address's position in the sorted list

Two things, kept apart (section 4.4): what the CERTIFICATE says — every feature name's address, its specimen
pair and the direction of its transition (`feature_results[].predicted_assignments`, `expected_transition`,
`feature_specimen_id` / `baseline_specimen_id`) — and the project's READING of each bit (`BIT_ONE_MEANS`,
docs/ff_preregistration_plan.md section 2's Z polarity convention), which this module checks against the
certificate's own specimen pairs: the feature endpoint of a ZINI feature must be a `zini_` specimen, of
ZRST / CEUSEDMUX / SRUSEDMUX / FFSYNC the `base`, of LATCH the `latch` variant, of CLKINV the `clkinv`
variant with NOCLKINV the negated reading of the SAME address. A certificate that disagrees is refused by
name; nothing is inferred from a name alone.

Counting (section 4.1): 22 feature names, 21 addresses — CLKINV and NOCLKINV are two readings of one bit.
The certificate is host evidence of a mapping, not of behaviour (section 4.2); this module makes no
behavioural statement. No board, no write.

Refusals (the owner's P2 on 2bad829 and on b91162c): an address out of range (far 32-bit, word 0..100 of a
7-series frame, bit 0..31); a feature or baseline endpoint that is not a specimen of the certificate, or not on
the site; a row whose `negated` flag is not the TOKEN's direction (every token is direct but NOCLKINV), or whose
expected_value / transition disagree with that direction; a shared address whose two readings are not one
direct and one negated (CLKINV / NOCLKINV); the certificate's digest not the authorised one.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CERTIFICATE_REL = "gate_runs/run_2026_08_05_ff/certificate.json"
CERTIFICATE = REPO_ROOT / CERTIFICATE_REL
CERTIFICATE_SCHEMA_VERSION = "1.6.0"
CERTIFICATE_SHA256 = "c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef"   # 90527e6, the authorised certificate
FRAME_WORDS = 101           # a 7-series configuration frame
BIT_CLASS = "clb_ff_config"
DEFAULT_SITE = "SLICE_X2Y25"

ELEMENTS = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")
SEMANTICS = ("ff_init", "ff_srval", "ce_mode", "sr_mode", "sr_kind", "storage_kind", "clock_mode")

# feature token -> (semantic, per-element?, the specimen suffix the FEATURE endpoint must carry, the DIRECTION of the
# token's reading: direct = the bit is 1 in the feature endpoint (expected_value 1, transition 0 -> 1); negated = the
# bit is 0 there (expected_value 0, transition 1 -> 0). The direction is the TOKEN's, fixed by the class's preregistration
# (docs/ff_preregistration_plan.md section 2) — a row that re-labels it, however self-consistent, is refused (the owner's
# P2 on b91162c). The one negated token is NOCLKINV, the complementary reading of CLKINV's bit.
TOKENS = {
    "ZINI": ("ff_init", True, "zini_", "direct"), "ZRST": ("ff_srval", True, "base", "direct"),
    "CEUSEDMUX": ("ce_mode", False, "base", "direct"), "SRUSEDMUX": ("sr_mode", False, "base", "direct"),
    "FFSYNC": ("sr_kind", False, "base", "direct"), "LATCH": ("storage_kind", False, "latch", "direct"),
    "CLKINV": ("clock_mode", False, "clkinv", "direct"), "NOCLKINV": ("clock_mode", False, "base", "negated"),
}
DIRECTION = {"direct": (False, 1, (0, 1)), "negated": (True, 0, (1, 0))}   # negated flag, expected_value, (before, after)
# the project's reading of bit = 1 per semantic (plan section 2; a decode assumption, section 4.4)
BIT_ONE_MEANS = {
    "ff_init": "INIT = 0", "ff_srval": "SRVAL = 0", "ce_mode": "CE driven", "sr_mode": "SR driven",
    "sr_kind": "synchronous", "storage_kind": "latch", "clock_mode": "clock inverted",
}


class MappingRefusal(ValueError):
    """The certificate is not the mapping this module reads — named, never guessed around."""


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def address_string(far: str, word: int, bit: int) -> str:
    """self_map v2's address form: lowercase 0x + 8 hex, /word/bit — range-checked."""
    try:
        f = int(far, 16)
    except (TypeError, ValueError):
        raise MappingRefusal(f"malformed frame address {far!r}") from None
    if not (0 <= f <= 0xFFFFFFFF):
        raise MappingRefusal(f"frame address {far!r} is not 32-bit")
    for name, v, hi in (("word", word, FRAME_WORDS - 1), ("bit", bit, 31)):
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= hi:
            raise MappingRefusal(f"address {far}/{word}/{bit}: {name} {v!r} is not in 0..{hi}")
    return f"0x{f:08x}/{word}/{bit}"


def address_key(address: str) -> tuple[int, int, int]:
    """Numeric order (far, word, bit) — the genome bit order; a string sort would put /19 before /7."""
    far, word, bit = address.split("/")
    return int(far, 16), int(word), int(bit)


@dataclass(frozen=True)
class Entry:
    address: str
    element: str | None           # one of ELEMENTS for per-element semantics; None for the slice-wide ones
    semantic: str
    features: tuple[str, ...]     # the feature name(s) the certificate carries for this address (two for clock_mode)
    bit_one_means: str
    feature_specimen: str         # the certificate's feature endpoint specimen of the primary feature
    baseline_specimen: str
    split: str


@dataclass(frozen=True)
class Mapping:
    site: str
    tile: str
    certificate_rel: str
    certificate_sha256: str
    addresses: tuple[str, ...]
    entries: dict[str, Entry] = field(default_factory=dict)

    def genome_bit(self, address: str) -> int:
        return self.addresses.index(address)

    def address_of(self, element: str | None, semantic: str) -> str:
        for a, e in self.entries.items():
            if e.element == element and e.semantic == semantic:
                return a
        raise KeyError((element, semantic))

    def summary(self) -> dict:
        return {"site": self.site, "tile": self.tile, "certificate": self.certificate_rel, "certificate_sha256": self.certificate_sha256,
                "addresses": list(self.addresses),
                "entries": {a: {"element": e.element, "semantic": e.semantic, "features": list(e.features), "bit_one_means": e.bit_one_means}
                            for a, e in self.entries.items()}}


def load_certificate(path: Path = CERTIFICATE, expected_sha256: str | None = CERTIFICATE_SHA256) -> dict:
    """The committed certificate must hash to CERTIFICATE_SHA256. Another file is read only with its digest given
    explicitly (the fixture boundary); `expected_sha256=None` is refused."""
    if not (isinstance(expected_sha256, str) and len(expected_sha256) == 64):
        raise MappingRefusal("a certificate is read only against an explicit 64-hex expected digest")
    try:
        raw = Path(path).read_bytes()
        doc = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise MappingRefusal(f"the certificate {path} cannot be read: {exc}") from exc
    got = hashlib.sha256(raw).hexdigest()
    if got != expected_sha256:
        raise MappingRefusal(f"the certificate {path} hashes to {got[:16]}…, not the expected {expected_sha256[:16]}…")
    if not isinstance(doc, dict) or doc.get("schema_version") != CERTIFICATE_SCHEMA_VERSION:
        raise MappingRefusal(f"the certificate's schema_version is not {CERTIFICATE_SCHEMA_VERSION}")
    if doc.get("status") != "passed":
        raise MappingRefusal(f"the certificate's status is {doc.get('status')!r}, not 'passed'")
    bc = doc.get("bit_class") or {}
    if bc.get("id") != BIT_CLASS:
        raise MappingRefusal(f"the certificate's bit class is {bc.get('id')!r}, not {BIT_CLASS!r}")
    if not isinstance(doc.get("feature_results"), list) or not isinstance(doc.get("specimens"), list):
        raise MappingRefusal("the certificate carries no feature_results / specimens lists")
    return doc


def site_mapping(site: str = DEFAULT_SITE, path: Path = CERTIFICATE, expected_sha256: str | None = CERTIFICATE_SHA256) -> Mapping:
    doc = load_certificate(path, expected_sha256)
    specimens = {s["specimen_id"]: s for s in doc["specimens"] if isinstance(s, dict) and "specimen_id" in s}
    tiles = {s["tile"] for s in specimens.values() if s.get("loc_site") == site}
    if len(tiles) != 1:
        raise MappingRefusal(f"the certificate names {len(tiles)} tiles for site {site}, not one")
    (tile,) = tiles
    by_address: dict[str, list[dict]] = {}
    for r in doc["feature_results"]:
        fs = r.get("feature_specimen_id"); bs = r.get("baseline_specimen_id")
        if not (isinstance(fs, str) and isinstance(bs, str)) or specimens.get(fs, {}).get("loc_site") != site:
            continue
        assigns = r.get("predicted_assignments")
        if not isinstance(assigns, list) or len(assigns) != 1:
            raise MappingRefusal(f"{r.get('feature')}: {0 if not isinstance(assigns, list) else len(assigns)} predicted assignments, not one (the class is single-bit)")
        a = assigns[0]
        if not isinstance(a, dict) or not isinstance(a.get("address"), dict) or not isinstance(a.get("segbit"), dict):
            raise MappingRefusal(f"{r.get('feature')}: the assignment lacks an address or a segbit")
        addr = address_string(a["address"].get("far"), a["address"].get("word"), a["address"].get("bit"))
        for role, sid in (("feature endpoint", fs), ("baseline endpoint", bs)):
            if sid not in specimens:
                raise MappingRefusal(f"{r['feature']}: the {role} {sid!r} is not a specimen of the certificate")
            if specimens[sid].get("loc_site") != site:
                raise MappingRefusal(f"{r['feature']}: the {role} {sid!r} is not on site {site}")
        token = r["feature"].split(".")[-1]
        if token not in TOKENS:
            raise MappingRefusal(f"{r['feature']}: the token {token!r} is not a clb_ff_config token this module reads")
        direction = TOKENS[token][3]
        want_neg, want_value, want_tr = DIRECTION[direction]
        if (a["segbit"].get("negated") is True) != want_neg:
            raise MappingRefusal(f"{r['feature']}: the token's reading is {direction} but the row says negated = {a['segbit'].get('negated')!r}")
        tr = r.get("expected_transition") or {}
        if a.get("expected_value") != want_value or (tr.get("before"), tr.get("after")) != want_tr:
            raise MappingRefusal(f"{r['feature']}: expected_value {a.get('expected_value')!r} and transition {tr} do not agree with the token's {direction} reading ({want_value}, {want_tr[0]} -> {want_tr[1]})")
        by_address.setdefault(addr, []).append(r)
    entries: dict[str, Entry] = {}
    for addr, rows in sorted(by_address.items()):
        tokens = {r["feature"].split(".")[-1]: r for r in rows}
        if set(tokens) == {"CLKINV", "NOCLKINV"}:
            primary = tokens["CLKINV"]
            dirs = {t: TOKENS[t][3] for t in tokens}
            negs = {t: tokens[t]["predicted_assignments"][0]["segbit"].get("negated") is True for t in tokens}
            if not (dirs["CLKINV"] == "direct" and dirs["NOCLKINV"] == "negated" and negs == {"CLKINV": False, "NOCLKINV": True}):
                raise MappingRefusal(f"{addr}: the two readings of the shared bit are not complementary (CLKINV direct, NOCLKINV negated)")
        elif len(tokens) == 1:
            (primary,) = tokens.values()
        else:
            raise MappingRefusal(f"{addr}: {sorted(tokens)} share one address; only CLKINV / NOCLKINV may")
        token = primary["feature"].split(".")[-1]
        semantic, per_element, suffix, _direction = TOKENS[token]
        element = primary["feature"].split(".")[-2] if per_element else None
        if per_element and element not in ELEMENTS:
            raise MappingRefusal(f"{primary['feature']}: {element!r} is not a storage element")
        fs, bs = primary["feature_specimen_id"], primary["baseline_specimen_id"]
        want = f"{site}_{suffix}{element}" if suffix == "zini_" else f"{site}_{suffix}"
        if fs != want:
            raise MappingRefusal(f"{primary['feature']}: the feature endpoint is {fs!r}, not {want!r} — the bit reading cannot be taken from this pair")
        entries[addr] = Entry(addr, element, semantic, tuple(sorted(r["feature"] for r in rows)), BIT_ONE_MEANS[semantic], fs, bs, str(primary.get("split")))
    if len(entries) != 21 or sum(len(e.features) for e in entries.values()) != 22:
        raise MappingRefusal(f"site {site}: {len(entries)} addresses / {sum(len(e.features) for e in entries.values())} features, not 21 / 22")
    want_pairs = {(e, "ff_init") for e in ELEMENTS} | {(e, "ff_srval") for e in ELEMENTS} | {(None, s) for s in ("ce_mode", "sr_mode", "sr_kind", "storage_kind", "clock_mode")}
    got_pairs = {(e.element, e.semantic) for e in entries.values()}
    if got_pairs != want_pairs:
        raise MappingRefusal(f"site {site}: the (element, semantic) set differs from the class's: missing {sorted(map(str, want_pairs - got_pairs))}, extra {sorted(map(str, got_pairs - want_pairs))}")
    return Mapping(site, tile, str(Path(path).resolve().relative_to(REPO_ROOT)) if Path(path).resolve().is_relative_to(REPO_ROOT) else str(path),
                   sha256_file(path), tuple(sorted(entries, key=address_key)), entries)


if __name__ == "__main__":
    print(json.dumps(site_mapping().summary(), indent=1))
