"""b3/host/b3_pins.py — the B3 instrument pin table: the rule, the table, the verifier, the command line
and the two consumers (the B3 manifest's `_production_pins`, the runner's `ProductionAuthority.verify_pins`).

The fixture is a temporary tree shaped like the repository's pinned surface — files under b3/ at depth 1,
2 and 3, a `.pyc`, a `__pycache__`, the architecture, and files the rule must NOT reach (host/, the
preregistration, the manifests/ directory) — pinned by the tool's own `generate` + `write_table_once`,
with a manifest whose `instrument_pins` block is what `b3_manifest.instrument_pins_block` builds. Every
case is checked to VERIFY first (the positive control), then one thing is changed and the refusal must
be NAMED. Where two guards would catch the same tamper (the table's bytes and the table's content), the
test asserts WHICH one fired — an unpinned edit is caught by the hash, the same edit re-pinned is caught
by the content check — so neither layer is a passenger.

Nothing here writes `manifests/b3_instrument_pins.json` in the repository or touches a manifest, a B2
pin, a frozen input, a device or a board. `--generate` is exercised on temporary trees only.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host", R / "b3/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b3_manifest as bman  # noqa: E402
import b3_pins as bp  # noqa: E402
import b3_runner as rn  # noqa: E402

# The fixture tree. PINNED is what the rule must reach; UNPINNED is what it must not.
PINNED = {
    "b3/x": "a depth-1 file\n",
    "b3/host/a.py": "print('a')\n",
    "b3/host/.hidden": "a dotfile is a regular file\n",
    "b3/schemas/s.schema.json": "{}\n",
    "b3/tests/test_a.py": "import unittest\n",
    "b3/tests/deep/deeper/x": "a depth-4 file\n",
    "docs/b3_architecture.md": "# architecture\n",
}
UNPINNED = {
    "b3/host/__pycache__/a.cpython-312.pyc": "bytecode",
    "b3/host/__pycache__/notes.txt": "anything inside __pycache__",
    "b3/host/stray.pyc": "bytecode outside __pycache__",
    "host/other.py": "a B2 module\n",
    "docs/b3_preregistration.md": "# prereg\n",
    "manifests/b3_manifest.json": "{}\n",
    "manifests/b2_instrument_pins.json": "{}\n",
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def make_tree(d: Path, pinned=PINNED, unpinned=UNPINNED) -> None:
    for rel, body in {**pinned, **unpinned}.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(body)
    (d / "b3/empty_dir").mkdir()
    (d / "manifests").mkdir(exist_ok=True)


def manifest_for(d: Path) -> dict:
    """The block exactly as the B3 manifest builds it, so `check_instrument_pins`'s `_same` holds too."""
    return {"schema": bman.SCHEMA, "instrument_pins": bman.instrument_pins_block(d)}


def pin(d: Path) -> dict:
    bp.write_table_once(bp.generate(d), d / bp.PIN_TABLE_REL)
    return manifest_for(d)


def rewrite_table(d: Path, table_or_bytes) -> dict:
    """Overwrite the table (the tool itself never does) and return a manifest RE-PINNED to the new bytes —
    so the content check, not the hash, is what a test then exercises."""
    data = table_or_bytes if isinstance(table_or_bytes, bytes) else bp.render(table_or_bytes).encode()
    (d / bp.PIN_TABLE_REL).write_bytes(data)
    return manifest_for(d)


class Tree(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="b3_pins_"))
        make_tree(self.d)
        self.m = pin(self.d)
        self.table = json.loads((self.d / bp.PIN_TABLE_REL).read_text())
        self.assertEqual(bp.verify(self.m, root=self.d)["files_verified"], len(PINNED))    # the positive control

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def refused(self, needle: str, fn, *a, **kw) -> str:
        with self.assertRaises(bp.PinRefusal) as cm:
            fn(*a, **kw)
        self.assertIn(needle, str(cm.exception))
        return str(cm.exception)

    _DEFAULT = object()

    def verify(self, m=_DEFAULT):
        return bp.verify(self.m if m is Tree._DEFAULT else m, root=self.d)


# ------------------------------------------------------------------ the rule


class TheRule(Tree):
    def test_discovery_is_exactly_the_rule(self):
        self.assertEqual(bp.discover(self.d), sorted(PINNED))
        for rel in UNPINNED:
            self.assertNotIn(rel, self.table["files"])
        self.assertNotIn("b3/empty_dir", self.table["files"])
        self.assertNotIn("b3/host", self.table["files"])
        self.assertNotIn("b3", self.table["files"])
        self.assertEqual(list(self.table["files"]), sorted(self.table["files"]))     # deterministic order
        self.assertEqual(self.table["globs"], ["b3/**/*", "docs/b3_architecture.md"])

    def test_pyc_and_pycache_are_excluded_and_a_new_one_changes_nothing(self):
        (self.d / "b3/tests/__pycache__").mkdir()
        (self.d / "b3/tests/__pycache__/test_a.cpython-312.pyc").write_bytes(b"\x00new")
        (self.d / "b3/new.pyc").write_bytes(b"\x00new")
        self.assertEqual(bp.discover(self.d), sorted(PINNED))
        self.verify()

    def test_a_directory_alone_is_not_an_entry(self):
        for rel in ("b3/newdir", "b3/host/newdir", "b3/tests/deep/deeper/newdir/evendeeper"):
            (self.d / rel).mkdir(parents=True)
        self.assertEqual(bp.discover(self.d), sorted(PINNED))
        self.assertEqual(bp.generate(self.d), self.table)
        self.verify()

    def test_a_symbolic_link_is_a_named_refusal_not_a_skip(self):
        """A link at depth 1, a link to a directory (outside the tree), a link where the architecture
        should be — each named as a link, by both discover and verify; a dangling link too."""
        outside = Path(tempfile.mkdtemp(prefix="b3_pins_outside_"))
        self.addCleanup(shutil.rmtree, outside, True)
        (outside / "f.py").write_text("elsewhere\n")
        cases = {
            "b3/link.py": self.d / "b3/host/a.py",
            "b3/host/linkdir": outside,
            "b3/tests/deep/dangling": self.d / "nowhere",
        }
        for rel, target in cases.items():
            os.symlink(target, self.d / rel)
            self.refused(f"{rel} is a symbolic link", bp.discover, self.d)
            self.refused(f"{rel} is a symbolic link", self.verify)
            self.refused(f"{rel} is a symbolic link", bp.generate, self.d)
            os.unlink(self.d / rel)
        self.verify()
        arch = self.d / "docs/b3_architecture.md"
        body = arch.read_text()
        arch.unlink()
        os.symlink(outside / "f.py", arch)
        self.refused("docs/b3_architecture.md is a symbolic link", self.verify)
        arch.unlink()
        arch.write_text(body)
        self.verify()

    def test_a_fifo_is_a_named_refusal(self):
        os.mkfifo(self.d / "b3/host/pipe")
        self.refused("b3/host/pipe is a fifo", bp.discover, self.d)
        self.refused("b3/host/pipe is a fifo", self.verify)

    def test_a_rule_that_reaches_nothing_is_refused(self):
        (self.d / "docs/b3_architecture.md").unlink()
        self.refused("reaches no regular file for ['docs/b3_architecture.md']", bp.discover, self.d)
        self.refused("reaches no regular file for ['docs/b3_architecture.md']", bp.generate, self.d)
        self.refused("reaches no regular file for ['docs/b3_architecture.md']", self.verify)
        e = Path(tempfile.mkdtemp(prefix="b3_pins_empty_"))
        self.addCleanup(shutil.rmtree, e, True)
        (e / "docs").mkdir()
        (e / "docs/b3_architecture.md").write_text("arch\n")
        self.refused("reaches no regular file for ['b3/**/*']", bp.generate, e)
        (e / "b3/host/__pycache__").mkdir(parents=True)
        (e / "b3/host/__pycache__/x.pyc").write_bytes(b"\x00")
        self.refused("reaches no regular file for ['b3/**/*']", bp.generate, e)      # excluded files do not count

    def test_the_repository_table_pins_this_unit_and_nothing_it_must_not(self):
        """Against the real tree: this module and this test are in; the table, the B3 manifest, the
        preregistration and every B2 file are out; no `.pyc` or `__pycache__` entry; the count is the
        entries and equals an independent walk — never a number written down here."""
        t = bp.generate(R)
        files = t["files"]
        for rel in ("b3/host/b3_pins.py", "b3/tests/test_b3_pins.py", "docs/b3_architecture.md",
                    "b3/host/b3_manifest.py", "b3/host/b3_runner.py", "b3/tests/test_b3_sentinel.py"):
            self.assertIn(rel, files)
            self.assertEqual(files[rel], sha((R / rel).read_bytes()))
        for rel in (bp.PIN_TABLE_REL, bp.MANIFEST_REL, "docs/b3_preregistration.md", "manifests/b2_instrument_pins.json",
                    "manifests/b2_manifest.json", "host/b2_pins.py", "host/b2_manifest.py", "host/b3_online.py"):
            self.assertNotIn(rel, files)
        self.assertFalse([r for r in files if "__pycache__" in r.split("/") or r.endswith(".pyc")])
        self.assertTrue(all(r.startswith("b3/") or r == "docs/b3_architecture.md" for r in files))
        walked = {os.path.relpath(os.path.join(dp, f), R) for dp, _, fs in os.walk(R / "b3") for f in fs
                  if "__pycache__" not in dp.split(os.sep) and not f.endswith(".pyc")
                  and stat.S_ISREG(os.lstat(os.path.join(dp, f)).st_mode)} | {"docs/b3_architecture.md"}
        self.assertEqual(set(files), walked)
        self.assertEqual(t["file_count"], len(files))
        self.assertEqual(t["file_count"], len(walked))
        self.assertGreater(t["file_count"], 2)


# ------------------------------------------------------------------ generate / render / write once


class Generate(Tree):
    def test_reproducible_and_a_pure_function_of_the_bytes(self):
        a = bp.generate(self.d)
        b = bp.generate(self.d)
        self.assertEqual(a, b)
        self.assertEqual(bp.render(a), bp.render(b))
        self.assertEqual(bp.render(a).encode(), (self.d / bp.PIN_TABLE_REL).read_bytes())
        copy_ = Path(tempfile.mkdtemp(prefix="b3_pins_copy_"))
        self.addCleanup(shutil.rmtree, copy_, True)
        shutil.rmtree(copy_)
        shutil.copytree(self.d, copy_, symlinks=True)
        self.assertEqual(bp.render(bp.generate(copy_)), bp.render(a))         # the location is not in the table
        self.assertEqual(set(a), {"schema", "schema_version", "globs", "file_count", "files"})
        self.assertEqual((a["schema"], a["schema_version"]), ("b3_instrument_pins", "1.0.0"))
        for rel, digest in a["files"].items():
            self.assertEqual(digest, sha((self.d / rel).read_bytes()))

    def test_the_count_is_the_entries_never_a_constant(self):
        base = bp.generate(self.d)
        self.assertEqual(base["file_count"], len(base["files"]))
        self.assertEqual(base["file_count"], len(PINNED))
        (self.d / "b3/added.py").write_text("more\n")
        (self.d / "b3/tests/deep/added2").write_text("more\n")
        t = bp.generate(self.d)
        self.assertEqual(t["file_count"], len(PINNED) + 2)
        self.assertEqual(t["file_count"], len(t["files"]))
        (self.d / "b3/host/a.py").unlink()
        (self.d / "b3/added.py").unlink()
        t = bp.generate(self.d)
        self.assertEqual(t["file_count"], len(PINNED))
        self.assertNotIn("b3/host/a.py", t["files"])
        self.assertIn("b3/tests/deep/added2", t["files"])
        small = Path(tempfile.mkdtemp(prefix="b3_pins_small_"))
        self.addCleanup(shutil.rmtree, small, True)
        make_tree(small, pinned={"b3/one": "1\n", "docs/b3_architecture.md": "arch\n"}, unpinned={})
        self.assertEqual(bp.generate(small)["file_count"], 2)

    def test_write_once_is_atomic_and_never_clobbers(self):
        out = self.d / "elsewhere" / "table.json"
        self.refused("is not an existing directory", bp.write_table_once, self.table, out)
        out.parent.mkdir()
        digest = bp.write_table_once(self.table, out)
        self.assertEqual(digest, sha(out.read_bytes()))
        self.assertEqual(out.read_bytes(), bp.render(self.table).encode())
        self.assertTrue(stat.S_ISREG(os.lstat(out).st_mode))
        self.assertEqual(sorted(os.listdir(out.parent)), ["table.json"])                  # no .part left behind
        before = out.read_bytes()
        other = dict(self.table, file_count=self.table["file_count"] + 1)
        self.refused("already exists (the table is generated once", bp.write_table_once, other, out)
        self.assertEqual(out.read_bytes(), before)
        self.assertEqual(sorted(os.listdir(out.parent)), ["table.json"])
        # a symbolic link where the table would go is "exists" too: nothing is written through it
        target = self.d / "elsewhere" / "target.json"
        target.write_text("keep\n")
        link = self.d / "elsewhere" / "link.json"
        os.symlink(target, link)
        self.refused("already exists", bp.write_table_once, self.table, link)
        self.assertEqual(target.read_text(), "keep\n")


# ------------------------------------------------------------------ verify: the manifest's block


class TheManifestBlock(Tree):
    def test_the_manifest_type(self):
        for bad in (None, [], "manifest", 7, True):
            self.refused(f"the manifest is {type(bad).__name__}, not a JSON object", self.verify, bad)

    def test_the_block(self):
        self.refused("pins no b3_instrument_pins table (no instrument_pins block)", self.verify, {"schema": bman.SCHEMA})
        for bad in ([], "x", 0, True):
            self.refused(f"instrument_pins is {type(bad).__name__}, not a JSON object", self.verify, {"instrument_pins": bad})
        good = self.m["instrument_pins"]
        self.refused("keys are ['sha256'], not ['path', 'sha256']", self.verify, {"instrument_pins": {"sha256": good["sha256"]}})
        self.refused("keys are ['path'], not ['path', 'sha256']", self.verify, {"instrument_pins": {"path": good["path"]}})
        self.refused("keys are ['extra', 'path', 'sha256']", self.verify, {"instrument_pins": dict(good, extra=1)})
        self.refused("keys are [], not", self.verify, {"instrument_pins": {}})

    def test_the_path_is_exactly_the_tables(self):
        good = self.m["instrument_pins"]
        for bad in ("manifests/b2_instrument_pins.json", "/" + bp.PIN_TABLE_REL, str(self.d / bp.PIN_TABLE_REL),
                    "b3/" + bp.PIN_TABLE_REL, bp.PIN_TABLE_REL.upper(), "", None, 3, ["manifests/b3_instrument_pins.json"]):
            self.refused(f"instrument_pins path is {bad!r}, not 'manifests/b3_instrument_pins.json'", self.verify,
                         {"instrument_pins": dict(good, path=bad)})

    def test_the_digest_is_64_lower_case_hex(self):
        good = self.m["instrument_pins"]
        ok = good["sha256"]
        for bad in (ok.upper(), ok[:63], ok + "0", ok[:-1] + "g", int(ok, 16), None, True, "", b"x".hex() * 32 + "zz"):
            self.refused(f"instrument_pins sha256 {bad!r} is not 64 lower-case hex", self.verify, {"instrument_pins": dict(good, sha256=bad)})
        wrong = ("0" if ok[0] != "0" else "1") + ok[1:]
        self.refused("does not hash to the manifest's pin", self.verify, {"instrument_pins": dict(good, sha256=wrong)})


# ------------------------------------------------------------------ verify: the table


class TheTable(Tree):
    def test_the_tables_bytes(self):
        p = self.d / bp.PIN_TABLE_REL
        p.unlink()
        self.refused("manifests/b3_instrument_pins.json is absent", self.verify)
        (self.d / "real.json").write_text(bp.render(self.table))
        os.symlink(self.d / "real.json", p)
        self.refused("manifests/b3_instrument_pins.json is a symbolic link", self.verify)
        p.unlink()
        p.mkdir()
        self.refused("manifests/b3_instrument_pins.json is a directory, not a regular file", self.verify)
        p.rmdir()
        os.mkfifo(p)                                                                   # must not hang the open
        self.refused("manifests/b3_instrument_pins.json is a fifo, not a regular file", self.verify)
        p.unlink()
        p.write_text(bp.render(self.table) + " ")
        self.refused("does not hash to the manifest's pin", self.verify)              # the hash layer, unpinned
        self.verify(manifest_for(self.d))                                              # re-pinned: a trailing space is still the same table
        repinned = manifest_for(self.d)
        os.chmod(p, 0)
        try:
            if os.geteuid() != 0:
                self.refused("manifests/b3_instrument_pins.json: cannot be read", self.verify, repinned)
        finally:
            os.chmod(p, 0o644)

    def test_the_tables_shape_each_named_by_the_content_check_not_the_hash(self):
        cases = [
            (b"not json", "is not readable JSON"),
            (b"\xff\xfe", "is not readable JSON"),
            (b"[]\n", "is list, not a JSON object"),
            (b"null\n", "is NoneType, not a JSON object"),
            (dict(self.table, schema="b2_instrument_pins"), "is not a b3_instrument_pins 1.0.0 document (schema 'b2_instrument_pins'"),
            (dict(self.table, schema_version="1.0.1"), "is not a b3_instrument_pins 1.0.0 document (schema 'b3_instrument_pins', schema_version '1.0.1')"),
            ({k: v for k, v in self.table.items() if k != "globs"}, "keys are ['file_count', 'files', 'schema', 'schema_version'], not"),
            (dict(self.table, extra=1), "keys are ['extra', 'file_count', 'files', 'globs', 'schema', 'schema_version'], not"),
            (dict(self.table, globs=["b3/**/*"]), "globs ['b3/**/*'] are not this rule's"),
            (dict(self.table, globs=["docs/b3_architecture.md", "b3/**/*"]), "globs ['docs/b3_architecture.md', 'b3/**/*'] are not this rule's"),
            (dict(self.table, globs=["b3/**/*", "docs/b3_architecture.md", "docs/b3_preregistration.md"]), "are not this rule's"),
            (dict(self.table, globs="b3/**/*"), "globs 'b3/**/*' are not this rule's"),
            (dict(self.table, files={}, file_count=0), "carries no file table (files is dict and empty)"),
            (dict(self.table, files=[]), "carries no file table (files is list)"),
            (dict(self.table, files=None), "carries no file table (files is NoneType)"),
            (dict(self.table, file_count=len(PINNED) + 1), f"file_count {len(PINNED) + 1} is not the {len(PINNED)} listed"),
            (dict(self.table, file_count=len(PINNED) - 1), f"file_count {len(PINNED) - 1} is not the {len(PINNED)} listed"),
            (dict(self.table, file_count=str(len(PINNED))), f"file_count '{len(PINNED)}' is not the {len(PINNED)} listed"),
            (dict(self.table, file_count=float(len(PINNED))), f"file_count {float(len(PINNED))!r} is not the {len(PINNED)} listed"),
            (dict(self.table, file_count=True), f"file_count True is not the {len(PINNED)} listed"),
            (dict(self.table, file_count=None), f"file_count None is not the {len(PINNED)} listed"),
        ]
        for table, needle in cases:
            with self.subTest(needle=needle):
                m_unpinned = copy.deepcopy(self.m)
                rewrite_table(self.d, table)
                self.refused("does not hash to the manifest's pin", self.verify, m_unpinned)     # layer 1: the bytes
                self.refused(needle, self.verify, manifest_for(self.d))                            # layer 2: the content
        rewrite_table(self.d, self.table)
        self.verify(manifest_for(self.d))

    def test_every_entry_digest_is_64_lower_case_hex(self):
        rel = "b3/host/a.py"
        ok = self.table["files"][rel]
        for bad in (ok.upper(), ok[:63], ok + "0", None, 1, True, "", ok[:-1] + "G"):
            t = copy.deepcopy(self.table)
            t["files"][rel] = bad
            self.refused(f"{rel}: digest {bad!r} is not 64 lower-case hex", self.verify, rewrite_table(self.d, t))

    def test_every_entry_path_is_a_normalized_repo_relative_path(self):
        digest = self.table["files"]["b3/host/a.py"]
        cases = {
            "/etc/passwd": "is absolute, not repo-relative",
            "/" + "b3/host/a.py": "is absolute, not repo-relative",
            "b3/../host/other.py": "is not normalized (a '.' or '..' component)",
            "../b3/host/a.py": "is not normalized (a '.' or '..' component)",
            "b3/./host/a.py": "is not normalized (a '.' or '..' component)",
            "./b3/host/a.py": "is not normalized (a '.' or '..' component)",
            "..": "is not normalized (a '.' or '..' component)",
            "b3//host/a.py": "is not normalized (an empty component or a trailing slash)",
            "b3/host/a.py/": "is not normalized (an empty component or a trailing slash)",
            "": "is not a non-empty string",
            "b3/host/a\x00.py": "carries a NUL byte",
        }
        for rel, needle in cases.items():
            with self.subTest(rel=rel):
                t = copy.deepcopy(self.table)
                t["files"][rel] = digest
                t["file_count"] += 1
                self.refused(f"table path {rel!r} {needle}", self.verify, rewrite_table(self.d, t))
        # ".." pointing at a REAL file with its REAL digest, escaping b3/: still refused by name, before any set or hash check
        t = copy.deepcopy(self.table)
        t["files"]["b3/../host/other.py"] = sha((self.d / "host/other.py").read_bytes())
        t["file_count"] += 1
        msg = self.refused("table path 'b3/../host/other.py' is not normalized", self.verify, rewrite_table(self.d, t))
        self.assertNotIn("not in the tree", msg)


# ------------------------------------------------------------------ verify: the tree against the table


class TheTreeAgainstTheTable(Tree):
    def test_a_new_file_at_every_depth_is_not_in_the_table(self):
        for rel in ("b3/x2", "b3/host/x", "b3/tests/deep/deeper/x2", "b3/tests/deep/deeper/evendeeper/x", "b3/.newdot"):
            with self.subTest(rel=rel):
                (self.d / rel).parent.mkdir(parents=True, exist_ok=True)
                (self.d / rel).write_text("new\n")
                msg = self.refused(f"not in the table: ['{rel}'] (1 file(s) the rule reaches that the table lacks)", self.verify)
                self.assertNotIn("hash differs", msg)
                (self.d / rel).unlink()
                self.verify()
        for rel in ("b3/x2", "b3/host/x", "b3/tests/deep/deeper/x2"):
            (self.d / rel).write_text("new\n")
        self.refused("not in the table: ['b3/host/x', 'b3/tests/deep/deeper/x2', 'b3/x2'] (3 file(s)", self.verify)

    def test_a_modified_pinned_file(self):
        for rel in ("b3/x", "b3/host/a.py", "b3/tests/deep/deeper/x", "docs/b3_architecture.md"):
            with self.subTest(rel=rel):
                body = (self.d / rel).read_text()
                (self.d / rel).write_text(body + "#\n")
                msg = self.refused(f"pinned files changed: {rel}: hash differs", self.verify)
                self.assertNotIn("not in the table", msg)
                (self.d / rel).write_text(body)
                self.verify()
        (self.d / "b3/host/a.py").write_text("")                              # emptied, same name: a change
        self.refused("b3/host/a.py: hash differs", self.verify)

    def test_a_deleted_or_renamed_pinned_file(self):
        (self.d / "b3/host/a.py").rename(self.d / "b3/host/b.py")
        msg = self.refused("not in the table: ['b3/host/b.py']", self.verify)         # the new name is reported first…
        (self.d / "b3/host/b.py").unlink()
        msg = self.refused("in the table but not in the tree by the rule: ['b3/host/a.py'] (1 entry(ies)", self.verify)   # …then the lost one
        self.assertNotIn("hash differs", msg)
        (self.d / "b3/tests/deep/deeper/x").unlink()
        self.refused("['b3/host/a.py', 'b3/tests/deep/deeper/x'] (2 entry(ies)", self.verify)

    def test_an_extra_table_entry(self):
        """A ghost with a well-formed digest; a REAL file the rule does not reach with its REAL digest; the
        table itself; the manifest — each an entry the rule does not reach."""
        for rel, digest in (("b3/host/ghost.py", "0" * 64),
                            ("host/other.py", sha((self.d / "host/other.py").read_bytes())),
                            ("docs/b3_preregistration.md", sha((self.d / "docs/b3_preregistration.md").read_bytes())),
                            ("b3/host/stray.pyc", sha((self.d / "b3/host/stray.pyc").read_bytes())),
                            ("b3/host/__pycache__/notes.txt", sha((self.d / "b3/host/__pycache__/notes.txt").read_bytes())),
                            (bp.PIN_TABLE_REL, "1" * 64),
                            (bp.MANIFEST_REL, sha((self.d / bp.MANIFEST_REL).read_bytes()))):
            with self.subTest(rel=rel):
                t = copy.deepcopy(self.table)
                t["files"][rel] = digest
                t["file_count"] += 1
                self.refused(f"in the table but not in the tree by the rule: ['{rel}']", self.verify, rewrite_table(self.d, t))
        # an entry for a file the rule reaches, whose digest is another file's: not an "extra", a drift
        t = copy.deepcopy(self.table)
        t["files"]["b3/x"] = t["files"]["b3/host/a.py"]
        self.refused("pinned files changed: b3/x: hash differs", self.verify, rewrite_table(self.d, t))

    def test_the_summary(self):
        s = self.verify()
        self.assertEqual(s, {"files_verified": len(PINNED), "pins_sha256": self.m["instrument_pins"]["sha256"], "path": bp.PIN_TABLE_REL})
        self.assertEqual(s["pins_sha256"], sha((self.d / bp.PIN_TABLE_REL).read_bytes()))
        (self.d / "b3/added").write_text("x\n")
        m2 = rewrite_table(self.d, bp.generate(self.d))
        self.assertEqual(self.verify(m2)["files_verified"], len(PINNED) + 1)
        self.assertNotEqual(self.verify(m2)["pins_sha256"], s["pins_sha256"])

    def assert_binding_of(self, root: Path, foreign: dict, *, default_root: bool = False) -> str:
        """The three states a committed tree can be in, EACH asserted (the audit's F3 on 918d309: an `if not
        table.exists()` guard asserted nothing once the table existed). Returns the state it found.
        `foreign` is a manifest that pins ANOTHER tree's table (the fixture's); `default_root` calls the API
        with root=None, i.e. against bp.REPO_ROOT — only meaningful when root IS the repository."""
        call = (lambda m: bp.verify(manifest=m)) if default_root else (lambda m: bp.verify(m, root=root))
        table, manifest = os.path.lexists(root / bp.PIN_TABLE_REL), os.path.lexists(root / bman.MANIFEST_REL)
        if not table:
            # absent: every manifest is refused by the table's absence, by name
            self.refused("manifests/b3_instrument_pins.json is absent", call, foreign)
            if default_root:
                self.refused("manifests/b3_instrument_pins.json is absent", bp.verify, foreign, root=None)
            return "absent"
        data, _ = bp.read_regular(root / bp.PIN_TABLE_REL, bp.PIN_TABLE_REL)
        own = {"instrument_pins": {"path": bp.PIN_TABLE_REL, "sha256": sha(data)}}
        if not manifest:
            # table only (generated, S0 not yet): the table's own bytes verify THIS tree; a foreign pin does not
            res = call(own)
            self.assertEqual(res, {"files_verified": bp.generate(root)["file_count"], "pins_sha256": sha(data), "path": bp.PIN_TABLE_REL})
            self.assertEqual(set(json.loads(data)["files"]), set(bp.generate(root)["files"]))
            self.refused("manifests/b3_instrument_pins.json does not hash to the manifest's pin", call, foreign)
            return "table_only"
        # table and manifest (S0 or later): the committed manifest, read as a trusted reader, verifies THIS tree
        m = json.loads(bman.read_manifest(root / bman.MANIFEST_REL).decode("utf-8"))
        self.assertEqual(m.get("instrument_pins"), {"path": bp.PIN_TABLE_REL, "sha256": sha(data)}, "the manifest pins this table's bytes")
        try:
            res = call(m)
        except bp.PinRefusal as exc:                                        # a drifted tree is this helper's FAILURE, never a pass
            self.fail(f"the production verifier refuses this tree under its own manifest: {exc}")
        self.assertEqual(res, {"files_verified": bp.generate(root)["file_count"], "pins_sha256": sha(data), "path": bp.PIN_TABLE_REL})
        self.assertEqual(call(own), res)
        self.refused("manifests/b3_instrument_pins.json does not hash to the manifest's pin", call, foreign)
        return "table_and_manifest"

    def test_the_three_committed_states_each_assert_on_a_temporary_tree(self):
        """The helper's every branch, before any of the states exists on the repository: a second tree walked
        through absent → table only → table and manifest, the fixture's manifest as the foreign pin."""
        o = Path(tempfile.mkdtemp(prefix="b3_pins_states_"))
        self.addCleanup(shutil.rmtree, o, True)
        make_tree(o, pinned={"b3/only.py": "other\n", "docs/b3_architecture.md": "other arch\n"}, unpinned={})
        self.assertEqual(self.assert_binding_of(o, self.m), "absent")
        bp.write_table_once(bp.generate(o), o / bp.PIN_TABLE_REL)
        self.assertEqual(self.assert_binding_of(o, self.m), "table_only")
        (o / bman.MANIFEST_REL).write_text(json.dumps({"schema": bman.SCHEMA, "instrument_pins": bman.instrument_pins_block(o)}))
        self.assertEqual(self.assert_binding_of(o, self.m), "table_and_manifest")
        # and this class's fixture tree, once its placeholder manifest carries the real block, is in the third state
        (self.d / bman.MANIFEST_REL).write_text(json.dumps({"schema": bman.SCHEMA, "instrument_pins": bman.instrument_pins_block(self.d)}))
        self.assertEqual(self.assert_binding_of(self.d, {"instrument_pins": {"path": bp.PIN_TABLE_REL, "sha256": "0" * 64}}), "table_and_manifest")
        # a drifted tree in the third state is a failure of the helper, never a pass
        (o / "b3/only.py").write_text("drifted\n")
        with self.assertRaises(AssertionError):
            self.assert_binding_of(o, self.m)
        (o / "b3/only.py").write_text("other\n")
        # NEGATIVE probes, one per branch: a verifier that lies must make the helper FAIL in every state
        good = bp.verify(json.loads((o / bman.MANIFEST_REL).read_text()), root=o)
        foreign_sha = self.m["instrument_pins"]["sha256"]

        def liar(summary):
            """A verifier that still refuses the FOREIGN pin (so that guard cannot be what fails) but answers
            `summary` to every other manifest, whatever the tree says."""
            def verify(manifest=None, root=None):
                if (manifest.get("instrument_pins") or {}).get("sha256") == foreign_sha:
                    raise bp.PinRefusal("manifests/b3_instrument_pins.json does not hash to the manifest's pin")
                return dict(summary)
            return mock.patch.object(bp, "verify", verify)
        accept_anything = mock.patch.object(bp, "verify", lambda manifest=None, root=None: dict(good))
        wrong_count = liar(dict(good, files_verified=good["files_verified"] + 1))
        with accept_anything:                                                   # table and manifest: the foreign pin accepted
            with self.assertRaises(AssertionError):
                self.assert_binding_of(o, self.m)
        with wrong_count:                                                       # table and manifest: the wrong summary (the foreign pin still refused)
            with self.assertRaises(AssertionError):
                self.assert_binding_of(o, self.m)
        (o / bman.MANIFEST_REL).write_text(json.dumps({"schema": bman.SCHEMA, "instrument_pins": {"path": bp.PIN_TABLE_REL, "sha256": "0" * 64}}))
        with liar(good):                                                        # the manifest's block is not this table's — the helper's own check, the verifier lying
            with self.assertRaises(AssertionError):
                self.assert_binding_of(o, self.m)
        (o / bman.MANIFEST_REL).unlink()
        self.assertEqual(self.assert_binding_of(o, self.m), "table_only")
        with accept_anything:                                                   # table only: the foreign pin accepted
            with self.assertRaises(AssertionError):
                self.assert_binding_of(o, self.m)
        with wrong_count:                                                       # table only: the wrong summary (the foreign pin still refused)
            with self.assertRaises(AssertionError):
                self.assert_binding_of(o, self.m)
        (o / bp.PIN_TABLE_REL).unlink()
        self.assertEqual(self.assert_binding_of(o, self.m), "absent")
        with accept_anything:                                                   # absent: a verifier that does not refuse
            with self.assertRaises(AssertionError):
                self.assert_binding_of(o, self.m)

    def test_the_default_root_is_the_repository(self):
        """root=None is THIS repository — shown against it, not by patching REPO_ROOT: discovery and the table
        equal the explicit-R call, and the repository's committed state — the table absent (generated once, after
        every pinned edit), the table alone, or the table and the manifest — is asserted for what it is, in
        every state (no guard that asserts nothing once the table exists)."""
        self.assertEqual(bp.REPO_ROOT, R)
        self.assertEqual(bp.discover(), bp.discover(R))
        self.assertEqual(bp.generate(), bp.generate(R))
        self.assertEqual(self.verify()["files_verified"], len(PINNED))
        state = self.assert_binding_of(R, self.m, default_root=True)
        self.assertIn(state, ("absent", "table_only", "table_and_manifest"))
        self.assertEqual(state == "absent", not os.path.lexists(R / bp.PIN_TABLE_REL))


# ------------------------------------------------------------------ the reader: a name swapped between the check and the read


class RaceProbes(Tree):
    """The owner's P2 on b6439ea: a regular-file check by lstat and a later read by name accepted a table or a
    pinned source swapped, in between, for a symbolic link to the same bytes. The shared reader opens with
    O_NOFOLLOW, fstat's the descriptor, reads from it and re-lstat's the name; each probe performs the swap at
    the exact step and the bytes are identical, so only the identity check can refuse."""

    def setUp(self):
        super().setUp()
        self.outside = Path(tempfile.mkdtemp(prefix="b3_pins_race_"))
        self.addCleanup(shutil.rmtree, self.outside, True)

    def swap_for_symlink(self, rel: str):
        """Replace the regular file at rel by a symbolic link to a copy of its exact bytes."""
        copy_ = self.outside / Path(rel).name
        copy_.write_bytes((self.d / rel).read_bytes())
        (self.d / rel).unlink()
        os.symlink(copy_, self.d / rel)

    def rewrite_in_place(self, rel: str, same_length: bool):
        """Rewrite the bytes at rel through the SAME inode (open for writing, truncate, write)."""
        old = (self.d / rel).read_bytes()
        new = bytes(b ^ 0x01 for b in old) if same_length else old + b"#\n"
        assert new != old
        ino = os.lstat(self.d / rel).st_ino
        with open(self.d / rel, "r+b") as f:
            f.truncate(0)
            f.write(new)
        assert os.lstat(self.d / rel).st_ino == ino, "the probe must keep the inode"
        return new

    def during_read_of(self, rel: str, action):
        """A read_fd that performs `action()` right after the bytes of THAT file have been read (its open
        descriptor still held by the reader)."""
        target = os.lstat(self.d / rel)
        real = bp.read_fd

        def read_fd(fd):
            st = os.fstat(fd)
            data = real(fd)
            if (st.st_dev, st.st_ino) == (target.st_dev, target.st_ino):
                action()
            return data
        return mock.patch.object(bp, "read_fd", read_fd)

    def swap_for_other_regular(self, rel: str):
        """Replace the regular file at rel by ANOTHER regular file (a new inode) holding its exact bytes."""
        data = (self.d / rel).read_bytes()
        tmp = self.d / (rel + ".swap")
        tmp.write_bytes(data)
        os.replace(tmp, self.d / rel)

    def probe_read_step(self, rel: str, swap):
        """Run verify with `swap(rel)` performed inside the read of THAT file — after its open and fstat, before
        the acceptance — and return the refusal."""
        target = os.lstat(self.d / rel)
        real = bp.read_fd

        def read_fd(fd):
            st = os.fstat(fd)
            data = real(fd)
            if (st.st_dev, st.st_ino) == (target.st_dev, target.st_ino):
                swap(rel)
            return data
        with mock.patch.object(bp, "read_fd", read_fd):
            with self.assertRaises(bp.PinRefusal) as cm:
                self.verify()
        return str(cm.exception)

    def test_the_table_swapped_for_a_symlink_between_the_open_and_the_acceptance(self):
        msg = self.probe_read_step(bp.PIN_TABLE_REL, self.swap_for_symlink)
        self.assertEqual(msg, "manifests/b3_instrument_pins.json changed while being read (the name is now a symbolic link, not the inode that was opened)")
        self.assertTrue(os.path.islink(self.d / bp.PIN_TABLE_REL))                 # the swap did happen — and the bytes match
        self.assertEqual((self.d / bp.PIN_TABLE_REL).read_bytes(), bp.render(self.table).encode())
        # once the swap has happened, a plain verify names the link at the open
        self.refused("manifests/b3_instrument_pins.json is a symbolic link", self.verify)

    def test_a_pinned_source_swapped_for_a_symlink_between_discovery_and_the_read(self):
        real = bp.discover

        def discover(root=None):
            out = real(root)
            self.swap_for_symlink("b3/host/a.py")
            return out
        with mock.patch.object(bp, "discover", discover):
            self.refused("b3/host/a.py is a symbolic link", self.verify)
        self.assertTrue(os.path.islink(self.d / "b3/host/a.py"))
        self.assertEqual((self.d / "b3/host/a.py").read_bytes(), PINNED["b3/host/a.py"].encode())
        # generate shares the reader: the same swap at the same step is the same refusal
        os.unlink(self.d / "b3/host/a.py")
        (self.d / "b3/host/a.py").write_text(PINNED["b3/host/a.py"])
        with mock.patch.object(bp, "discover", discover):
            self.refused("b3/host/a.py is a symbolic link", bp.generate, self.d)

    def test_a_pinned_source_swapped_for_another_regular_file_between_the_open_and_the_acceptance(self):
        msg = self.probe_read_step("b3/host/a.py", self.swap_for_other_regular)
        self.assertEqual(msg, "b3/host/a.py changed while being read (the name is now another regular file, not the inode that was opened)")
        self.assertEqual((self.d / "b3/host/a.py").read_bytes(), PINNED["b3/host/a.py"].encode())
        self.verify()                                                                 # settled, the same bytes verify
        msg = self.probe_read_step("b3/host/a.py", self.swap_for_symlink)
        self.assertEqual(msg, "b3/host/a.py changed while being read (the name is now a symbolic link, not the inode that was opened)")

    def test_a_pinned_source_removed_between_the_open_and_the_acceptance(self):
        msg = self.probe_read_step("b3/tests/deep/deeper/x", lambda rel: (self.d / rel).unlink())
        self.assertEqual(msg, "b3/tests/deep/deeper/x changed while being read (the name is gone or unreadable now)")

    def test_a_pinned_source_rewritten_in_place_after_the_read_same_inode(self):
        """The owner's P2-1 on 02d179c: the bytes were read, then the SAME inode was rewritten in place; the
        inode compare alone accepted it. Now the descriptor is still open: its re-fstat sees the size / mtime /
        ctime move. Both a length-changing and a same-length rewrite."""
        for same_length in (False, True):
            with self.subTest(same_length=same_length):
                rel = "b3/host/a.py"
                ino = os.lstat(self.d / rel).st_ino
                with self.during_read_of(rel, lambda: self.rewrite_in_place(rel, same_length)):
                    msg = self.refused(f"{rel} changed while being read (the inode's size / mtime / ctime moved under the open descriptor)", self.verify)
                self.assertNotIn("hash differs", msg)
                self.assertEqual(os.lstat(self.d / rel).st_ino, ino)                 # same inode, different bytes now
                self.refused(f"pinned files changed: {rel}: hash differs", self.verify)   # settled: an ordinary drift
                (self.d / rel).write_text(PINNED[rel])
                self.m = rewrite_table(self.d, bp.generate(self.d))                    # mtime moved: re-pin the table
                self.verify()

    def test_the_table_rewritten_in_place_after_the_read_same_inode(self):
        rel = bp.PIN_TABLE_REL
        ino = os.lstat(self.d / rel).st_ino
        for same_length in (False, True):
            with self.subTest(same_length=same_length):
                with self.during_read_of(rel, lambda: self.rewrite_in_place(rel, same_length)):
                    self.refused(f"{rel} changed while being read (the inode's size / mtime / ctime moved under the open descriptor)", self.verify)
                self.assertEqual(os.lstat(self.d / rel).st_ino, ino)
                self.refused("does not hash to the manifest's pin", self.verify)          # settled: the bytes are not the pinned ones
                rewrite_table(self.d, self.table)
                self.verify()

    def test_a_file_appearing_while_the_sources_are_hashed(self):
        """The owner's P2-2 on 02d179c: discovery ran once, so a file matching the rule that appeared while the
        sources were being hashed was never seen. The closing discovery must equal the opening one — in verify
        AND in generate."""
        first = sorted(PINNED)[0]
        for new in ("b3/new.py", "b3/host/new.py", "b3/tests/deep/deeper/new"):
            with self.subTest(new=new):
                def appear():
                    (self.d / new).write_text("late\n")
                with self.during_read_of(first, appear):
                    self.refused(f"the rule's path set changed while the tree was being read: appeared ['{new}']", self.verify)
                self.assertTrue((self.d / new).exists())
                self.refused(f"not in the table: ['{new}']", self.verify)              # settled: an ordinary new file
                (self.d / new).unlink()
                with self.during_read_of(first, appear):
                    self.refused(f"the rule's path set changed while the tree was being read: appeared ['{new}']", bp.generate, self.d)
                (self.d / new).unlink()
                self.verify()
        # a directory appearing is not an entry and changes nothing
        with self.during_read_of(first, lambda: (self.d / "b3/latedir").mkdir()):
            self.verify()

    def test_an_already_read_source_vanishing_or_rewritten_while_another_is_hashed(self):
        """The owner's P2-2 on 02d179c: a source read earlier in the snapshot, changed while a LATER one was
        being hashed — its own read saw nothing. The closing check names it: vanished from the path set, or
        the same inode re-stamped with another size / mtime / ctime, or the name now another file."""
        early, late = "b3/host/.hidden", "b3/tests/test_a.py"
        self.assertLess(early, late)
        with self.during_read_of(late, lambda: (self.d / early).unlink()):
            self.refused(f"the rule's path set changed while the tree was being read: vanished ['{early}']", self.verify)
        (self.d / early).write_text(PINNED[early])
        self.m = rewrite_table(self.d, bp.generate(self.d))
        self.verify()
        for same_length in (False, True):
            with self.subTest(same_length=same_length):
                with self.during_read_of(late, lambda: self.rewrite_in_place(early, same_length)):
                    msg = self.refused(f"{early} changed after it was read (the inode's size / mtime / ctime moved)", self.verify)
                self.assertNotIn("hash differs", msg)
                (self.d / early).write_text(PINNED[early])
                self.m = rewrite_table(self.d, bp.generate(self.d))
                self.verify()
        with self.during_read_of(late, lambda: self.swap_for_other_regular(early)):
            self.refused(f"{early} changed after it was read (the name is now another regular file)", self.verify)
        self.m = rewrite_table(self.d, bp.generate(self.d))
        self.verify()
        with self.during_read_of(late, lambda: self.swap_for_symlink(early)):
            self.refused(f"the rule reaches what it cannot pin: {early} is a symbolic link", self.verify)   # the closing discovery, first
        os.unlink(self.d / early)
        (self.d / early).write_text(PINNED[early])
        # generate shares the closing check
        self.m = rewrite_table(self.d, bp.generate(self.d))
        with self.during_read_of(late, lambda: self.rewrite_in_place(early, False)):
            self.refused(f"{early} changed after it was read", bp.generate, self.d)

    def test_the_table_rewritten_after_its_read_while_the_sources_are_hashed(self):
        """The table's own closing check: read first, re-stamped last."""
        first = sorted(PINNED)[0]
        with self.during_read_of(first, lambda: self.rewrite_in_place(bp.PIN_TABLE_REL, True)):
            self.refused("manifests/b3_instrument_pins.json changed after it was read (the inode's size / mtime / ctime moved)", self.verify)
        rewrite_table(self.d, self.table)
        with self.during_read_of(first, lambda: self.swap_for_symlink(bp.PIN_TABLE_REL)):
            self.refused("manifests/b3_instrument_pins.json changed after it was read (the name is now a symbolic link)", self.verify)
        os.unlink(self.d / bp.PIN_TABLE_REL)
        rewrite_table(self.d, self.table)
        with self.during_read_of(first, lambda: self.swap_for_other_regular(bp.PIN_TABLE_REL)):
            self.refused("manifests/b3_instrument_pins.json changed after it was read (the name is now another regular file)", self.verify)

    def test_the_table_removed_after_its_read_while_the_sources_are_hashed(self):
        """The table is not in the rule's path set, so only its own closing check can see it go."""
        first = sorted(PINNED)[0]
        with self.during_read_of(first, lambda: (self.d / bp.PIN_TABLE_REL).unlink()):
            self.refused("manifests/b3_instrument_pins.json changed after it was read (the name is gone or unreadable now)", self.verify)
        self.assertFalse((self.d / bp.PIN_TABLE_REL).exists())
        self.refused("manifests/b3_instrument_pins.json is absent", self.verify)

    def before_examining(self, rel: str, action, occurrence: int = 1):
        """An lstat_name that performs `action()` right before the `occurrence`-th examination of rel — i.e. after
        the rule listed it and before it is examined (the owner's P2 on ef0ce46)."""
        real = bp.lstat_name
        seen = {"n": 0}

        def lstat_name(p):
            if Path(p) == self.d / rel:
                seen["n"] += 1
                if seen["n"] == occurrence:
                    action()
            return real(p)
        return mock.patch.object(bp, "lstat_name", lstat_name)

    def test_a_source_vanishing_between_the_listing_and_its_examination(self):
        """Listed by the rule, gone before lstat: a NAMED refusal, in the opening discovery, in the closing
        discovery (the second examination of the same name), and in generate — never a FileNotFoundError."""
        rel = "b3/host/a.py"
        with self.before_examining(rel, lambda: (self.d / rel).unlink()):
            msg = self.refused(f"{rel} vanished during discovery (listed by the rule, gone before it could be examined)", self.verify)
        self.assertFalse((self.d / rel).exists())
        self.refused(f"in the table but not in the tree by the rule: ['{rel}']", self.verify)      # settled: an ordinary loss
        (self.d / rel).write_text(PINNED[rel])
        self.m = rewrite_table(self.d, bp.generate(self.d))
        self.verify()
        # the CLOSING discovery: the file survives the opening one and its read, and vanishes before its second examination
        with self.before_examining(rel, lambda: (self.d / rel).unlink(), occurrence=2):
            self.refused(f"{rel} vanished during discovery", self.verify)
        (self.d / rel).write_text(PINNED[rel])
        self.m = rewrite_table(self.d, bp.generate(self.d))
        with self.before_examining(rel, lambda: (self.d / rel).unlink()):
            self.refused(f"{rel} vanished during discovery", bp.generate, self.d)
        (self.d / rel).write_text(PINNED[rel])
        with self.before_examining(rel, lambda: (self.d / rel).unlink(), occurrence=2):
            self.refused(f"{rel} vanished during discovery", bp.generate, self.d)
        (self.d / rel).write_text(PINNED[rel])
        with self.before_examining("docs/b3_architecture.md", lambda: (self.d / "docs/b3_architecture.md").unlink()):
            self.refused("docs/b3_architecture.md vanished during discovery", bp.discover, self.d)

    def test_a_source_unreadable_at_its_examination_is_named_not_an_internal_error(self):
        """Listed, then unexaminable (its directory closed) before lstat: named. The permission itself is
        exercised for real when this user can be refused by it; the conversion is exercised for every user
        through the seam (no skip: the suite must run with zero skips)."""
        if os.geteuid() != 0:
            locked = self.d / "b3/locked"
            locked.mkdir()
            (locked / "x").write_text("x\n")
            try:
                with self.before_examining("b3/locked/x", lambda: os.chmod(locked, 0)):
                    self.refused("b3/locked/x: cannot be examined: Permission denied", bp.discover, self.d)
            finally:
                os.chmod(locked, 0o755)
            shutil.rmtree(locked)
            self.verify()
        real = bp.lstat_name

        def lstat_name(p):
            if Path(p) == self.d / "b3/host/a.py":
                raise PermissionError(13, "Permission denied", str(p))
            return real(p)
        with mock.patch.object(bp, "lstat_name", lstat_name):
            self.refused("b3/host/a.py: cannot be examined: Permission denied", self.verify)
            self.refused("b3/host/a.py: cannot be examined: Permission denied", bp.generate, self.d)

    def test_an_implementation_defect_in_the_examination_stays_an_internal_error(self):
        for exc in (TypeError("a defect"), KeyError("a defect"), ValueError("a defect")):
            with self.subTest(exc=type(exc).__name__):
                with mock.patch.object(bp, "lstat_name", side_effect=exc):
                    with self.assertRaises(type(exc)):
                        self.verify()
                    with self.assertRaises(type(exc)):
                        bp.generate(self.d)

    def test_the_reader_itself(self):
        rel = "b3/host/a.py"
        data, stamp = bp.read_regular(self.d / rel, rel)
        self.assertEqual(data, PINNED[rel].encode())
        st = os.lstat(self.d / rel)
        self.assertEqual(stamp, (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns))
        self.refused("b3/none is absent", bp.read_regular, self.d / "b3/none", "b3/none")
        os.symlink(self.d / rel, self.d / "b3/link")
        self.refused("b3/link is a symbolic link", bp.read_regular, self.d / "b3/link", "b3/link")
        self.refused("b3/host is a directory, not a regular file", bp.read_regular, self.d / "b3/host", "b3/host")
        os.mkfifo(self.d / "b3/pipe")
        self.refused("b3/pipe is a fifo, not a regular file", bp.read_regular, self.d / "b3/pipe", "b3/pipe")
        text = (R / "b3/host/b3_pins.py").read_text()
        self.assertNotIn("read_bytes(", text.split("def read_regular")[1].split("def sha256_of")[0])
        # no other read of a pinned name exists: every read_bytes / read_text in the module is in a test-only helper or absent
        body = text.split('"""', 2)[2]                                             # after the module docstring
        self.assertEqual(body.count("read_bytes("), 0)
        self.assertEqual(body.count("read_text("), 0)


# ------------------------------------------------------------------ the consumers


class TheConsumers(Tree):
    """The B3 manifest's production pin verifier and the runner's production authority, over THIS module —
    a legal summary passes through, a PinRefusal is renamed `instrument pins: …`, and an implementation
    defect inside this module (a TypeError, a KeyError, a dependency missing) propagates unwrapped."""

    def other_tree(self) -> Path:
        """A second, independent tree — pinned on its own — so a consumer that verified the wrong root is caught."""
        o = Path(tempfile.mkdtemp(prefix="b3_pins_other_"))
        self.addCleanup(shutil.rmtree, o, True)
        make_tree(o, pinned={"b3/only.py": "other\n", "docs/b3_architecture.md": "other arch\n"}, unpinned={})
        return o

    def test_the_manifest_receives_the_summary_or_a_named_refusal_for_the_root_it_was_given(self):
        """The production b3_manifest path over THIS module, on an independent temporary tree, with REPO_ROOT
        untouched (the owner's P2 on b6439ea: the consumer used to drop root and read the repository)."""
        self.assertEqual(bp.REPO_ROOT, R)
        self.assertEqual(bman._production_pins(self.m, self.d)["files_verified"], len(PINNED))
        self.assertEqual(bman.check_instrument_pins(self.m, self.d, bman.Seams())["pins_sha256"], self.m["instrument_pins"]["sha256"])
        # the SAME manifest against another root: that root's table (absent) is what is named — never this tree's
        o = self.other_tree()
        with self.assertRaises(bman.Refusal) as cm:
            bman._production_pins(self.m, o)
        self.assertEqual(str(cm.exception), "instrument pins: manifests/b3_instrument_pins.json is absent")
        mo = pin(o)
        self.assertEqual(bman._production_pins(mo, o)["files_verified"], 2)
        with self.assertRaises(bman.Refusal) as cm:
            bman._production_pins(mo, self.d)                                   # that tree's manifest against this tree
        self.assertEqual(str(cm.exception), "instrument pins: manifests/b3_instrument_pins.json does not hash to the manifest's pin")
        (self.d / "b3/host/new.py").write_text("new\n")
        with self.assertRaises(bman.Refusal) as cm:
            bman._production_pins(self.m, self.d)
        self.assertEqual(str(cm.exception), "instrument pins: not in the table: ['b3/host/new.py'] (1 file(s) the rule reaches that the table lacks)")
        self.assertNotIsInstance(cm.exception, bp.PinRefusal)
        (self.d / "b3/host/new.py").unlink()
        bad = {"instrument_pins": dict(self.m["instrument_pins"], sha256="z" * 64)}
        with self.assertRaises(bman.Refusal) as cm:
            bman._production_pins(bad, self.d)
        self.assertTrue(str(cm.exception).startswith("instrument pins: the manifest's instrument_pins sha256 'zzzz"))

    def test_the_runner_receives_the_summary_or_a_named_refusal_for_the_root_it_was_given(self):
        auth = rn.production_authority()                    # both authority modules exist now: no refusal here
        self.assertIs(auth._modules()[1], bp)
        self.assertEqual(bp.REPO_ROOT, R)
        self.assertEqual(auth.verify_pins(self.m, self.d)["files_verified"], len(PINNED))
        o = self.other_tree()
        with self.assertRaises(rn.Refusal) as cm:
            auth.verify_pins(self.m, o)
        self.assertEqual(str(cm.exception), "instrument pins: manifests/b3_instrument_pins.json is absent")
        self.assertEqual(auth.verify_pins(pin(o), o)["files_verified"], 2)
        (self.d / "b3/host/a.py").write_text("changed\n")
        with self.assertRaises(rn.Refusal) as cm:
            auth.verify_pins(self.m, self.d)
        self.assertEqual(str(cm.exception), "instrument pins: pinned files changed: b3/host/a.py: hash differs")
        self.assertNotIsInstance(cm.exception, bp.PinRefusal)

    def test_a_defect_inside_this_module_propagates_through_both_consumers(self):
        auth = rn.production_authority()
        for exc in (TypeError("a defect"), KeyError("a defect"), ModuleNotFoundError("No module named 'no_such_dependency_b3_pins'", name="no_such_dependency_b3_pins")):
            with self.subTest(exc=type(exc).__name__):
                with mock.patch.object(bp, "discover", side_effect=exc):
                    with self.assertRaises(type(exc)) as cm:
                        bman._production_pins(self.m, self.d)
                    self.assertIs(cm.exception, exc)
                    with self.assertRaises(type(exc)) as cm:
                        auth.verify_pins(self.m, self.d)
                    self.assertIs(cm.exception, exc)
                    with self.assertRaises(type(exc)):
                        bp.verify(self.m, root=self.d)

    def test_the_refusal_classes_are_what_the_consumers_look_for(self):
        self.assertTrue(issubclass(bp.PinRefusal, bp.Refusal))
        self.assertTrue(issubclass(bp.Refusal, Exception))
        self.assertFalse(issubclass(bp.Refusal, bman.Refusal))
        self.assertFalse(issubclass(bp.Refusal, rn.Refusal))
        self.assertEqual(rn.ProductionAuthority._refusals(bp, "PinRefusal", "Refusal"), (bp.PinRefusal, bp.Refusal))
        self.assertFalse(issubclass(bp.PinRefusal, (TypeError, KeyError, ImportError, OSError, ValueError)))
        text = (R / "b3/host/b3_pins.py").read_text()
        self.assertNotIn("b2_pins", text.replace("manifests/b2_instrument_pins", ""))     # the B2 lineage is not verified here
        self.assertNotIn("b2_manifest", text)
        with mock.patch.dict(sys.modules, {"b3_manifest": None}):      # the API needs no b3_manifest: the CLI alone reads through it
            self.assertEqual(self.verify()["files_verified"], len(PINNED))
            self.assertEqual(bp.generate(self.d), self.table)


# ------------------------------------------------------------------ the command line


class TheCommandLine(Tree):
    def run_cli(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = bp.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_generate_writes_once_to_an_explicit_path(self):
        out = self.d / "out" / "pins.json"
        out.parent.mkdir()
        rc, o, e = self.run_cli("--generate", "--root", str(self.d), "--out", str(out))
        self.assertEqual((rc, e), (0, ""))
        self.assertEqual(out.read_bytes(), bp.render(self.table).encode())
        self.assertIn(f"pinned {len(PINNED)} files -> {out} sha256 {sha(out.read_bytes())}", o)
        before = out.read_bytes()
        rc, o, e = self.run_cli("--generate", "--root", str(self.d), "--out", str(out))
        self.assertEqual((rc, o), (2, ""))
        self.assertIn("REFUSED: ", e)
        self.assertIn("already exists", e)
        self.assertEqual(out.read_bytes(), before)
        rc, o, e = self.run_cli("--generate", "--root", str(self.d))
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED: --generate requires --out", e)
        self.assertEqual(sorted(os.listdir(out.parent)), ["pins.json"])
        os.symlink(self.d / "b3/host/a.py", self.d / "b3/link")
        rc, o, e = self.run_cli("--generate", "--root", str(self.d), "--out", str(self.d / "out" / "second.json"))
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED: the rule reaches what it cannot pin: b3/link is a symbolic link", e)
        self.assertFalse((self.d / "out" / "second.json").exists())

    def test_a_source_vanishing_during_discovery_on_the_command_line(self):
        """The owner's P2 on ef0ce46: rc 3, INTERNAL ERROR: FileNotFoundError. Now: REFUSED, exit 2, nothing written."""
        rel = "b3/host/a.py"
        out = self.d / "out" / "pins.json"
        out.parent.mkdir()
        real = bp.lstat_name

        def vanish_before_examining(p):
            if Path(p) == self.d / rel and (self.d / rel).exists():
                (self.d / rel).unlink()
            return real(p)
        with mock.patch.object(bp, "lstat_name", vanish_before_examining):
            rc, o, e = self.run_cli("--generate", "--root", str(self.d), "--out", str(out))
        self.assertEqual((rc, o), (2, ""))
        self.assertIn(f"REFUSED: {rel} vanished during discovery (listed by the rule, gone before it could be examined)", e)
        self.assertNotIn("Traceback", e)
        self.assertNotIn("INTERNAL ERROR", e)
        self.assertFalse(out.exists())
        self.assertEqual(os.listdir(out.parent), [])
        (self.d / rel).write_text(PINNED[rel])
        (self.d / bp.MANIFEST_REL).write_text(json.dumps(self.m))
        with mock.patch.object(bp, "lstat_name", vanish_before_examining):
            rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual((rc, o), (2, ""))
        self.assertIn(f"REFUSED: {rel} vanished during discovery", e)
        self.assertNotIn("Traceback", e)
        # an implementation defect at the same step is still an INTERNAL ERROR, exit 3
        (self.d / rel).write_text(PINNED[rel])
        with mock.patch.object(bp, "lstat_name", side_effect=TypeError("a defect")):
            rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual(rc, 3)
        self.assertIn("INTERNAL ERROR: TypeError: a defect", e)
        self.assertIn("Traceback", e)
        self.assertNotIn("REFUSED", e)

    def test_verify_exits_0_2_or_3(self):
        (self.d / bp.MANIFEST_REL).write_text(json.dumps(self.m))
        rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual((rc, e), (0, ""))
        self.assertEqual(json.loads(o), {"files_verified": len(PINNED), "pins_sha256": self.m["instrument_pins"]["sha256"], "path": bp.PIN_TABLE_REL})
        elsewhere = self.d / "m.json"
        elsewhere.write_text(json.dumps(self.m))
        self.assertEqual(self.run_cli("--root", str(self.d), "--manifest", str(elsewhere))[0], 0)
        (self.d / "b3/new").write_text("x\n")
        rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual((rc, o), (2, ""))
        self.assertIn("REFUSED: not in the table: ['b3/new']", e)
        self.assertNotIn("Traceback", e)
        (self.d / "b3/new").unlink()
        rc, o, e = self.run_cli("--root", str(self.d), "--manifest", str(self.d / "absent.json"))
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED: the manifest", e)
        self.assertIn("is absent", e)
        (self.d / "bad.json").write_text("{not json")
        rc, o, e = self.run_cli("--root", str(self.d), "--manifest", str(self.d / "bad.json"))
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED: the manifest", e)
        self.assertIn("is not readable JSON", e)
        self.assertNotIn("Traceback", e)
        with mock.patch.object(bp, "discover", side_effect=KeyError("a defect")):
            rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual((rc, o), (3, ""))
        self.assertIn("Traceback", e)
        self.assertIn("INTERNAL ERROR: KeyError: 'a defect'", e)
        self.assertNotIn("REFUSED", e)
        with mock.patch.object(bp, "discover", side_effect=ModuleNotFoundError("No module named 'x'", name="x")):
            rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual(rc, 3)
        self.assertIn("INTERNAL ERROR: ModuleNotFoundError", e)

    def test_the_cli_reads_the_manifest_as_a_trusted_reader(self):
        """The owner's P1 on b6439ea: the CLI read the manifest by name and verified against a manifest with an
        unfinished transaction beside it. Now it reads through b3_manifest.read_manifest — the shared lock and the
        unresolved-transaction refusal — and only b3_manifest.Refusal becomes REFUSED; anything else is an
        INTERNAL ERROR."""
        (self.d / bp.MANIFEST_REL).write_text(json.dumps(self.m))
        self.assertEqual(self.run_cli("--root", str(self.d))[0], 0)
        journal = self.d / "manifests" / ".b3_manifest.json.transaction"
        journal.write_text(json.dumps({"schema": "b3_manifest_transaction", "state": "exchanging", "pid": 1, "at": "t"}))
        rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual((rc, o), (2, ""))
        self.assertIn("REFUSED: the manifest", e)
        self.assertIn("a b3_manifest transition did not finish", e)
        self.assertIn(".b3_manifest.json.transaction", e)
        self.assertIn("WITHDRAWN", e)
        self.assertNotIn("Traceback", e)
        journal.unlink()
        os.symlink(self.d / "nowhere", journal)                                  # a dangling journal is unresolved too
        self.assertEqual(self.run_cli("--root", str(self.d))[0], 2)
        journal.unlink()
        part = self.d / "manifests" / ".b3_manifest.json.1.part"
        part.write_text("{}")
        rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual(rc, 2)
        self.assertIn(".b3_manifest.json.1.part", e)
        part.unlink()
        self.assertEqual(self.run_cli("--root", str(self.d))[0], 0)
        # the read goes through b3_manifest.read_manifest, and through nothing else
        seen = []
        real = bman.read_manifest

        def read_manifest(path, wait=True):
            seen.append(Path(path))
            return real(path, wait)
        with mock.patch.object(bman, "read_manifest", read_manifest):
            self.assertEqual(self.run_cli("--root", str(self.d))[0], 0)
        self.assertEqual(seen, [self.d / bp.MANIFEST_REL])
        with mock.patch.object(bman, "read_manifest", side_effect=bman.Refusal("a b3_manifest transition is being published; not read")):
            rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED: the manifest", e)
        self.assertIn("is being published; not read", e)
        with mock.patch.object(bman, "read_manifest", side_effect=RuntimeError("a defect in the reader")):
            rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual(rc, 3)
        self.assertIn("INTERNAL ERROR: RuntimeError: a defect in the reader", e)
        self.assertIn("Traceback", e)
        self.assertNotIn("REFUSED", e)
        with mock.patch.dict(sys.modules, {"b3_manifest": None}):                # an import error is not a refusal either
            rc, o, e = self.run_cli("--root", str(self.d))
        self.assertEqual(rc, 3)
        self.assertIn("INTERNAL ERROR: ModuleNotFoundError", e)
        self.assertNotIn("REFUSED", e)
        text = (R / "b3/host/b3_pins.py").read_text()
        self.assertNotIn("mpath.read_text", text)
        self.assertNotIn("mpath.read_bytes", text)

    def test_the_cli_offers_no_skip(self):
        text = (R / "b3/host/b3_pins.py").read_text()
        for flag in ("--skip", "--no-verify", "--allow-missing", "--force", "--overwrite", "--update", "--patch"):
            self.assertNotIn(flag, text)
        with mock.patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit):
                bp.main(["--force"])


if __name__ == "__main__":
    unittest.main()
