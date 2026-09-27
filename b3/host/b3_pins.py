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

Every file this module reads — the table, every pinned file, in generate and in verify alike — is read
through ONE reader (`read_regular`): opened with O_NOFOLLOW, fstat'd on the open descriptor as a regular
file, read from that descriptor, and — with the descriptor still open — re-fstat'd and the name re-lstat'd
to the same (device, inode, size, mtime_ns, ctime_ns) before the bytes are accepted; a name swapped for a
symbolic link or another file, or an inode rewritten in place, is refused by name. The pinned surface is
taken as a two-phase STABLE SNAPSHOT (`snapshot`): opening discovery, every file read and stamped, closing
discovery equal to the opening (a file that appeared or vanished meanwhile is named), and every read path
— the table too — re-stamped at the close (a file rewritten after its own read is named).
The command line reads the manifest through `b3_manifest.read_manifest` — the lifecycle's shared lock and
its unresolved-transaction refusal — never by name.
"""
from __future__ import annotations

import argparse
import errno
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


def read_fd(fd: int) -> bytes:
    """Every byte of an open descriptor (the read step of `read_regular`, on its own so a test can probe the
    window between the open and the acceptance)."""
    chunks = []
    while True:
        b = os.read(fd, 1 << 20)
        if not b:
            return b"".join(chunks)
        chunks.append(b)


def stamp_of(st: os.stat_result) -> tuple:
    """A regular file's identity AND content witness: (device, inode, size, mtime_ns, ctime_ns). The inode
    alone says which file the name is; size / mtime / ctime say whether that inode's bytes moved — an
    in-place rewrite keeps the inode (the owner's P2-1 on 02d179c)."""
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def what_changed(now: os.stat_result, was: tuple) -> str:
    if not stat.S_ISREG(now.st_mode):
        return f"the name is now {kind_of(now.st_mode)}"
    if (now.st_dev, now.st_ino) != was[:2]:
        return "the name is now another regular file"
    return "the inode's size / mtime / ctime moved"


def read_regular(path: Path, rel: str) -> tuple[bytes, tuple]:
    """The bytes of `path`, which must be ONE regular file, unchanged, from the open to the acceptance — the
    one reader generate and verify share (the owner's P2 on b6439ea and P2-1 on 02d179c). The name is opened
    with O_NOFOLLOW (a symbolic link is refused by the kernel, not by a prior look); the OPEN descriptor is
    fstat'd and must be a regular file; the bytes are read from that descriptor; then, WITH THE DESCRIPTOR
    STILL OPEN, the descriptor is fstat'd again and the name is lstat'd, and both must give the stamp the
    read began with — the same (device, inode) with the same size / mtime_ns / ctime_ns. A name swapped for
    a link or another file, and an inode rewritten in place, are each "changed while being read". Returns
    the bytes and that stamp, for the closing check of the snapshot."""
    try:
        # O_NONBLOCK: a fifo at the name must not hang the open — fstat then names it. No effect on a regular file.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    except FileNotFoundError:
        raise PinRefusal(f"{rel} is absent") from None
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise PinRefusal(f"{rel} is a symbolic link") from None
        raise PinRefusal(f"{rel}: cannot be read: {exc.strerror or exc}") from None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise PinRefusal(f"{rel} is {kind_of(st.st_mode)}, not a regular file")
        was = stamp_of(st)
        try:
            data = read_fd(fd)
        except OSError as exc:
            raise PinRefusal(f"{rel}: cannot be read: {exc.strerror or exc}") from None
        after = os.fstat(fd)                      # the inode that was read, seen through the still-open descriptor
        try:
            now = os.lstat(path)                  # the name, while the descriptor is still open
        except OSError:
            raise PinRefusal(f"{rel} changed while being read (the name is gone or unreadable now)") from None
        # Named most specifically first: a name that no longer refers to the opened inode (a swap — which also
        # moves the old inode's ctime, so this is decided before the stamp), then the inode itself moved.
        if (now.st_dev, now.st_ino) != was[:2] or not stat.S_ISREG(now.st_mode):
            raise PinRefusal(f"{rel} changed while being read ({what_changed(now, was)}, not the inode that was opened)")
        if stamp_of(after) != was or stamp_of(now) != was:
            raise PinRefusal(f"{rel} changed while being read (the inode's size / mtime / ctime moved under the open descriptor)")
    finally:
        os.close(fd)
    return data, was


def recheck(path: Path, rel: str, was: tuple) -> None:
    """The closing check of a file read earlier in the snapshot: the name must still be that regular inode
    with the size / mtime / ctime it had when read (the owner's P2-2 on 02d179c: a file rewritten AFTER its
    own read, while a later file was being hashed, must not stand)."""
    try:
        now = os.lstat(path)
    except OSError:
        raise PinRefusal(f"{rel} changed after it was read (the name is gone or unreadable now)") from None
    if stamp_of(now) != was:
        raise PinRefusal(f"{rel} changed after it was read ({what_changed(now, was)})")


def snapshot(root: Path) -> tuple[dict, dict]:
    """A STABLE snapshot of the pinned surface, in two phases (the owner's P2-2 on 02d179c): the opening
    discovery; every file read through `read_regular` with its stamp kept; then the CLOSING discovery,
    whose path set must equal the opening one (a file that appeared or vanished while the tree was being
    read is named), and every read path re-lstat'd against its stamp (a file rewritten after its own read
    is named). Returns ({rel: sha256}, {rel: stamp}) — generate writes the first, verify compares it."""
    root = Path(root)
    opening = discover(root)
    digests, stamps = {}, {}
    for rel in opening:
        data, stamps[rel] = read_regular(root / rel, rel)
        digests[rel] = hashlib.sha256(data).hexdigest()
    closing = discover(root)
    if closing != opening:
        appeared = sorted(set(closing) - set(opening))
        vanished = sorted(set(opening) - set(closing))
        raise PinRefusal("the rule's path set changed while the tree was being read: "
                         + "; ".join(f"{k} {v[:5]}" for k, v in (("appeared", appeared), ("vanished", vanished)) if v))
    for rel in opening:
        recheck(root / rel, rel, stamps[rel])
    return digests, stamps


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
    """The table for the tree NOW, from a stable snapshot (opening discovery, every file read once and
    stamped, closing discovery and re-stamp): a pure function of the pinned bytes (sorted entries; `render`
    gives the canonical bytes). Never written by this function."""
    root = Path(REPO_ROOT if root is None else root)
    files, _ = snapshot(root)
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
    data, table_stamp = read_regular(root / PIN_TABLE_REL, PIN_TABLE_REL)   # O_NOFOLLOW, fstat, read, re-fstat / re-lstat: never by name alone
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
    # 4. the tree, as ONE stable snapshot (opening discovery, every file read and stamped, closing discovery
    #    equal to the opening, every read path re-stamped) — and its path set EXACTLY the table's
    digests, _ = snapshot(root)
    now = sorted(digests)
    listed = set(files)
    missing = sorted(set(now) - listed)
    if missing:
        raise PinRefusal(f"not in the table: {missing[:5]} ({len(missing)} file(s) the rule reaches that the table lacks)")
    extra = sorted(listed - set(now))
    if extra:
        raise PinRefusal(f"in the table but not in the tree by the rule: {extra[:5]} ({len(extra)} entry(ies) — deleted, renamed, or never there)")
    # 5. every pinned file hashing to its entry
    drift = [f"{rel}: hash differs" for rel in now if digests[rel] != files[rel]]
    if drift:
        raise PinRefusal("pinned files changed: " + "; ".join(drift[:5]))
    # 6. the table itself, at the close: still the regular inode with the stamp it was read with
    recheck(root / PIN_TABLE_REL, PIN_TABLE_REL, table_stamp)
    return {"files_verified": len(now), "pins_sha256": pinned, "path": PIN_TABLE_REL}


# ------------------------------------------------------------------ the command line


def read_manifest_trusted(path: Path) -> bytes:
    """The manifest's bytes as EVERY trusted reader reads them — `b3_manifest.read_manifest`: under the
    lifecycle's shared lock and refusing by name while an unfinished transaction is beside the manifest, so
    a WITHDRAWN transition is never verified against as the authority (the owner's P1 on b6439ea, which read
    the path by name). Only the refusal b3_manifest declares becomes this tool's refusal; an import or
    implementation error inside it propagates (an INTERNAL ERROR). Malformed JSON is named here."""
    import importlib
    bman = importlib.import_module("b3_manifest")
    try:
        data = bman.read_manifest(path)
    except bman.Refusal as exc:
        raise PinRefusal(f"the manifest {path}: {exc}") from None
    try:
        json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise PinRefusal(f"the manifest {path} is not readable JSON: {exc}") from None
    return data


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
        manifest = json.loads(read_manifest_trusted(mpath).decode("utf-8"))
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
