#!/usr/bin/env python3
"""B3 — the instrument pin table of everything under `b3/` plus the architecture (host-only;
architecture v0.3 §6; preregistration v0.3.1 §8).

    b3_pins.py --generate --out PATH [--root R]     write the table PATH (never over an existing file)
    b3_pins.py [--manifest M] [--root R]            verify the tree's table against the manifest's pin

THE RULE, fixed here and nowhere else: every REGULAR FILE that `b3/**/*` reaches, plus
`docs/b3_architecture.md`; `.pyc` files and anything inside a `__pycache__` directory are excluded;
directories are not entries. A symbolic link or any other non-regular file the rule reaches is a
NAMED refusal, never silently skipped — a link is a way to pin a name while the bytes live elsewhere.
The table `manifests/b3_instrument_pins.json` is not in the table (it cannot pin its own hash); the B3
manifest is not (it pins the table); the preregistration is not (the manifest pins it by its frozen
hash, and pinning it twice would let the two disagree). This module and its test ARE in the table:
they live under `b3/` like every other decision this package makes.

`verify(manifest, root)` holds the manifest's `instrument_pins` block to its type and to exactly
{path, sha256}, the path to exactly `manifests/b3_instrument_pins.json`, the digest to 64 lower-case
hex, the table's bytes to that digest, the table to this schema and version with exactly this rule's
globs, the file count to the entries, every entry to a normalized repo-relative path (no absolute
path, no `.` or `..` component, no empty component) and a 64 lower-case hex digest, the table's path
set to EXACTLY what the rule discovers in the tree now (a file the rule reaches that the table lacks,
and an entry the rule does not reach — deleted, renamed, or never there — are both named), and every
pinned file to a regular file hashing to its entry. What it does NOT do: verify the B2 lineage (the
B2 table, the B2 manifest, the seven indirect frozen inputs) — that is the B3 manifest's fixed prefix
(`b3_manifest.verify`), and it is not repeated here.

Refusals: `PinRefusal` (a `Refusal`) is raised for a malformed input or a drifted pin, and ONLY for
those; an implementation defect, a dependency missing inside this module or any unexpected exception
propagates unchanged — on the command line it is an INTERNAL ERROR (exit 3, with its traceback), a
refusal is `REFUSED: …` (exit 2). The manifest and the runner convert exactly these two classes.
This module imports the standard library only, so no dependency of its own can go missing.

Type before use, then domain, then lookup: a malformed value is a named refusal and never reaches a
formula or a filesystem call that would raise something else.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import traceback
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_TABLE_REL = "manifests/b3_instrument_pins.json"
MANIFEST_REL = "manifests/b3_manifest.json"
SCHEMA = "b3_instrument_pins"
SCHEMA_VERSION = "1.0.0"

# The rule. `b3/**/*` reaches every entry at every depth below b3/ (measured: `b3/**` alone lists
# directories only); the architecture is the one normative document the runtime is bound to.
# Every rule must reach at least one regular file (discover): a rule whose file is absent would pin nothing, silently.
PINNED_GLOBS = ("b3/**/*", "docs/b3_architecture.md")
EXCLUDE_SUFFIXES = (".pyc",)
EXCLUDE_DIRS = ("__pycache__",)
TABLE_KEYS = frozenset({"schema", "schema_version", "globs", "file_count", "files"})
BLOCK_KEYS = frozenset({"path", "sha256"})
HEX = frozenset("0123456789abcdef")


class Refusal(Exception):
    """A named refusal: a malformed input or a drifted pin. Never an implementation defect."""


class PinRefusal(Refusal):
    pass


# ------------------------------------------------------------------ small things


def is_sha256_hex(s) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in HEX for c in s)


def sha256_of(path: Path, rel: str) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise PinRefusal(f"{rel}: cannot be read: {exc.strerror or exc}") from None


def kind_of(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "a symbolic link"
    if stat.S_ISDIR(mode):
        return "a directory"
    if stat.S_ISFIFO(mode):
        return "a fifo"
    if stat.S_ISSOCK(mode):
        return "a socket"
    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
        return "a device"
    return "not a regular file"


def check_rel(rel) -> None:
    """A table path is a normalized repo-relative POSIX path: a non-empty string, not absolute, no
    empty, `.` or `..` component, no trailing slash — so `root / rel` cannot leave the root by name."""
    if not isinstance(rel, str) or not rel:
        raise PinRefusal(f"table path {rel!r} is not a non-empty string")
    if "\x00" in rel:
        raise PinRefusal(f"table path {rel!r} carries a NUL byte")
    if PurePosixPath(rel).is_absolute():
        raise PinRefusal(f"table path {rel!r} is absolute, not repo-relative")
    parts = rel.split("/")
    if any(p == "" for p in parts):
        raise PinRefusal(f"table path {rel!r} is not normalized (an empty component or a trailing slash)")
    if any(p in (".", "..") for p in parts):
        raise PinRefusal(f"table path {rel!r} is not normalized (a '.' or '..' component)")


def excluded(rel: str) -> bool:
    parts = rel.split("/")
    return parts[-1].endswith(EXCLUDE_SUFFIXES) or any(p in EXCLUDE_DIRS for p in parts[:-1])


# ------------------------------------------------------------------ discovery and the table


def discover(root: Path | None = None) -> list[str]:
    """The sorted normalized repo-relative paths the rule reaches in `root` NOW. Directories are not
    entries; `.pyc` and `__pycache__` contents are excluded; a symbolic link or any other non-regular
    file the rule reaches is a named refusal; a rule that reaches no regular file (the architecture
    absent, no b3/ tree) is a named refusal — a rule that pins nothing is not a table."""
    root = Path(REPO_ROOT if root is None else root)
    found: set[str] = set()
    bad: list[str] = []
    empty: list[str] = []
    for g in PINNED_GLOBS:
        n = 0
        for p in sorted(root.glob(g)):
            rel = p.relative_to(root).as_posix()
            if excluded(rel):
                continue
            mode = os.lstat(p).st_mode          # lstat: a link is seen as a link, not as its target
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                bad.append(f"{rel} is {kind_of(mode)}")
                continue
            found.add(rel)
            n += 1
        if n == 0:
            empty.append(g)
    if bad:
        raise PinRefusal("the rule reaches what it cannot pin: " + "; ".join(bad[:5]))
    if empty:
        raise PinRefusal(f"the rule reaches no regular file for {empty} under {root} (absent — a table without it pins nothing there)")
    return sorted(found)


def generate(root: Path | None = None) -> dict:
    """The table for the tree NOW: a pure function of the pinned bytes (sorted entries; `render` gives
    the canonical bytes). Never written by this function."""
    root = Path(REPO_ROOT if root is None else root)
    files = {rel: sha256_of(root / rel, rel) for rel in discover(root)}
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "globs": list(PINNED_GLOBS),
            "file_count": len(files), "files": files}


def render(table: dict) -> str:
    return json.dumps(table, indent=1, sort_keys=True) + "\n"


def write_table_once(table: dict, out: Path) -> str:
    """Publish `out` atomically and without clobbering: the bytes go to a temporary file beside it,
    fsync'd, then `os.link` — which fails if `out` exists, and never exposes a partial file. Returns
    the table's sha256."""
    out = Path(out)
    if not out.parent.is_dir():
        raise PinRefusal(f"{out.parent} is not an existing directory")
    data = render(table).encode()
    tmp = out.parent / f".{out.name}.part-{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, out)
        except FileExistsError:
            raise PinRefusal(f"{out} already exists (the table is generated once; it is never patched or overwritten)") from None
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    dfd = os.open(out.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ verify


def verify(manifest, root: Path | None = None) -> dict:
    """Every failure is a named PinRefusal (see the module docstring for the order). Returns
    {"files_verified", "pins_sha256", "path"}. The B2 lineage is NOT verified here."""
    root = Path(REPO_ROOT if root is None else root)
    # 1. the manifest's block: type before use
    if not isinstance(manifest, dict):
        raise PinRefusal(f"the manifest is {type(manifest).__name__}, not a JSON object")
    block = manifest.get("instrument_pins")
    if block is None:
        raise PinRefusal(f"the manifest pins no {SCHEMA} table (no instrument_pins block)")
    if not isinstance(block, dict):
        raise PinRefusal(f"the manifest's instrument_pins is {type(block).__name__}, not a JSON object")
    if set(block) != BLOCK_KEYS:
        raise PinRefusal(f"the manifest's instrument_pins keys are {sorted(map(str, block))}, not {sorted(BLOCK_KEYS)}")
    path = block["path"]
    if path != PIN_TABLE_REL:
        raise PinRefusal(f"the manifest's instrument_pins path is {path!r}, not {PIN_TABLE_REL!r}")
    pinned = block["sha256"]
    if not is_sha256_hex(pinned):
        raise PinRefusal(f"the manifest's instrument_pins sha256 {pinned!r} is not 64 lower-case hex")
    # 2. the table's bytes
    pins_path = root / PIN_TABLE_REL
    try:
        mode = os.lstat(pins_path).st_mode
    except FileNotFoundError:
        raise PinRefusal(f"{PIN_TABLE_REL} is absent") from None
    if not stat.S_ISREG(mode):
        raise PinRefusal(f"{PIN_TABLE_REL} is {kind_of(mode)}, not a regular file")
    try:
        data = pins_path.read_bytes()
    except OSError as exc:
        raise PinRefusal(f"{PIN_TABLE_REL} cannot be read: {exc.strerror or exc}") from None
    if hashlib.sha256(data).hexdigest() != pinned:
        raise PinRefusal(f"{PIN_TABLE_REL} does not hash to the manifest's pin")
    # 3. the table's shape
    try:
        table = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise PinRefusal(f"{PIN_TABLE_REL} is not readable JSON: {exc}") from None
    if not isinstance(table, dict):
        raise PinRefusal(f"{PIN_TABLE_REL} is {type(table).__name__}, not a JSON object")
    if table.get("schema") != SCHEMA or table.get("schema_version") != SCHEMA_VERSION:
        raise PinRefusal(f"{PIN_TABLE_REL} is not a {SCHEMA} {SCHEMA_VERSION} document "
                         f"(schema {table.get('schema')!r}, schema_version {table.get('schema_version')!r})")
    if set(table) != TABLE_KEYS:
        raise PinRefusal(f"{PIN_TABLE_REL} keys are {sorted(map(str, table))}, not {sorted(TABLE_KEYS)}")
    if table["globs"] != list(PINNED_GLOBS):
        raise PinRefusal(f"{PIN_TABLE_REL} globs {table['globs']!r} are not this rule's {list(PINNED_GLOBS)!r}")
    files = table["files"]
    if not isinstance(files, dict) or not files:
        raise PinRefusal(f"{PIN_TABLE_REL} carries no file table (files is {type(files).__name__}"
                         f"{' and empty' if isinstance(files, dict) else ''})")
    count = table["file_count"]
    # No separate bool guard: files is non-empty and the rule reaches >= 2 files, so True (1) and False (0)
    # can never equal len(files) — the inequality refuses them by name (an explicit bool check would be dead code).
    if not isinstance(count, int) or count != len(files):
        raise PinRefusal(f"{PIN_TABLE_REL}: file_count {count!r} is not the {len(files)} listed")
    for rel in files:
        check_rel(rel)
    bad = [f"{rel}: digest {sha!r} is not 64 lower-case hex" for rel, sha in sorted(files.items()) if not is_sha256_hex(sha)]
    if bad:
        raise PinRefusal(f"{PIN_TABLE_REL}: " + "; ".join(bad[:5]))
    # 4. the path set: EXACTLY what the rule reaches now
    now = discover(root)
    listed = set(files)
    missing = sorted(set(now) - listed)
    if missing:
        raise PinRefusal(f"not in the table: {missing[:5]} ({len(missing)} file(s) the rule reaches that the table lacks)")
    extra = sorted(listed - set(now))
    if extra:
        raise PinRefusal(f"in the table but not in the tree by the rule: {extra[:5]} ({len(extra)} entry(ies) — deleted, renamed, or never there)")
    # 5. every pinned file: regular (discover saw to it) and hashing to its entry
    drift = []
    for rel in now:
        if sha256_of(root / rel, rel) != files[rel]:
            drift.append(f"{rel}: hash differs")
            if len(drift) >= 5:
                break
    if drift:
        raise PinRefusal("pinned files changed: " + "; ".join(drift))
    return {"files_verified": len(now), "pins_sha256": pinned, "path": PIN_TABLE_REL}


# ------------------------------------------------------------------ the command line


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--generate", action="store_true", help="write the table for --root to --out (never over an existing file)")
    ap.add_argument("--out", type=Path, default=None, help="with --generate: the file to create (required)")
    ap.add_argument("--root", type=Path, default=None, help="the tree (default: this repository)")
    ap.add_argument("--manifest", type=Path, default=None, help=f"the manifest to verify against (default: <root>/{MANIFEST_REL})")
    a = ap.parse_args(argv)
    root = Path(REPO_ROOT if a.root is None else a.root)
    try:
        if a.generate:
            if a.out is None:
                raise PinRefusal("--generate requires --out: the table is written to an explicit path, once")
            table = generate(root)
            digest = write_table_once(table, a.out)
            print(f"pinned {table['file_count']} files -> {a.out} sha256 {digest}")
            return 0
        mpath = root / MANIFEST_REL if a.manifest is None else a.manifest
        if not mpath.is_file():
            raise PinRefusal(f"the manifest {mpath} is absent")
        try:
            manifest = json.loads(mpath.read_text())
        except (OSError, ValueError) as exc:
            raise PinRefusal(f"the manifest {mpath} is not readable JSON: {exc}") from None
        print(json.dumps(verify(manifest, root=root), sort_keys=True))
        return 0
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:                     # noqa: BLE001 — an implementation defect stays visible
        traceback.print_exc()
        print(f"INTERNAL ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
