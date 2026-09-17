#!/usr/bin/env python3
"""B3 lifecycle 1, unit 1 follow-up (the owner's P2-3 and P2-4): two facts the audit's §7 stated
wrongly, now measured. (1) `Path.glob("b3/**")` yields DIRECTORIES only; the working pin rule is
`b3/**/*` filtered to regular files, and it must reach depth 1, 2 and 3+. (2) The B3 test command:
`unittest discover -s b3/tests` works without packages; `-s b3/tests -t .` needs `b3/__init__.py`
and `b3/tests/__init__.py`, otherwise `Start directory is not importable`. Plus the discovery
sentinel / removal control the B3 test report must carry. Runs in a throwaway detached worktree
of BASE; writes glob_and_discovery.json beside this file; the main tree is not touched."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = "73b68d79fd43fc032c178da73dda2b2c95764db8"
SENTINEL = "import unittest\nclass Sentinel(unittest.TestCase):\n    def test_b3_discovery_sentinel(self):\n        self.assertTrue(True)\n"


def sh(cmd, cwd, env=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    return {"cmd": " ".join(cmd), "rc": p.returncode, "tail": (p.stdout + p.stderr).strip().splitlines()[-3:]}


def main(scratch: Path) -> int:
    wt = scratch / "wt" / "glob_discovery"
    if wt.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO)
    subprocess.run(["git", "worktree", "add", "--detach", str(wt), BASE], cwd=REPO, check=True, capture_output=True,
                   env=dict(os.environ, GIT_LFS_SKIP_SMUDGE="1"))
    out = {"base": BASE, "python": sys.version.split()[0], "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    # (1) glob semantics on a three-deep b3/ tree
    for rel in ("b3/top.py", "b3/host/online.py", "b3/tests/test_x.py", "b3/tests/deep/deeper/leaf.json"):
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text("# probe\n")
    globs = {}
    for g in ("b3/**", "b3/**/*", "b3/*"):
        hits = sorted(str(p.relative_to(wt)) for p in wt.glob(g))
        files = sorted(str(p.relative_to(wt)) for p in wt.glob(g) if p.is_file())
        globs[g] = {"all": hits, "regular_files": files}
    out["glob"] = globs
    out["glob_finding"] = {"b3/** pins no file": globs["b3/**"]["regular_files"] == [],
                           "b3/**/* filtered to files reaches depth 1, 2 and 4":
                               globs["b3/**/*"]["regular_files"] == ["b3/host/online.py", "b3/tests/deep/deeper/leaf.json", "b3/tests/test_x.py", "b3/top.py"]}
    shutil.rmtree(wt / "b3")
    # (2) discovery command variants with one sentinel test
    (wt / "b3/tests").mkdir(parents=True)
    (wt / "b3/tests/test_sentinel.py").write_text(SENTINEL)
    py = [sys.executable, "-B", "-m", "unittest"]
    disc = {}
    disc["A_no_packages_-s_b3/tests"] = sh(py + ["discover", "-s", "b3/tests", "-v"], wt)
    disc["B_no_packages_-s_b3/tests_-t_."] = sh(py + ["discover", "-s", "b3/tests", "-t", "."], wt)
    (wt / "b3/__init__.py").write_text("")
    (wt / "b3/tests/__init__.py").write_text("")
    disc["C_packages_-s_b3/tests_-t_."] = sh(py + ["discover", "-s", "b3/tests", "-t", ".", "-v"], wt)
    disc["D_b2_discovery_-s_tests_does_not_see_b3"] = sh(py + ["discover", "-s", "tests", "-p", "test_sentinel*.py"], wt)
    (wt / "b3/__init__.py").unlink()
    (wt / "b3/tests/__init__.py").unlink()
    # the removal control: the same command with the sentinel removed must run fewer tests
    (wt / "b3/tests/test_sentinel.py").unlink()
    disc["E_removal_control_A_form"] = sh(py + ["discover", "-s", "b3/tests"], wt)
    out["discovery"] = disc
    out["discovery_finding"] = {
        "A works without packages": disc["A_no_packages_-s_b3/tests"]["rc"] == 0 and any("Ran 1 test" in l for l in disc["A_no_packages_-s_b3/tests"]["tail"]),
        "B fails: Start directory is not importable": any("Start directory is not importable" in l for l in disc["B_no_packages_-s_b3/tests_-t_."]["tail"]),
        "C works with packages": disc["C_packages_-s_b3/tests_-t_."]["rc"] == 0,
        "D: B2's discovery never runs a b3/ test": any("NO TESTS RAN" in l for l in disc["D_b2_discovery_-s_tests_does_not_see_b3"]["tail"]),
        "E: removing the sentinel changes the count (Ran 0)": any("Ran 0 tests" in l for l in disc["E_removal_control_A_form"]["tail"]),
    }
    subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO, check=True)
    subprocess.run(["git", "worktree", "prune"], cwd=REPO)
    out["main_tree_status_porcelain"] = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout
    (HERE / "glob_and_discovery.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out["glob_finding"], indent=1))
    print(json.dumps(out["discovery_finding"], indent=1))
    return 0 if all(out["glob_finding"].values()) and all(out["discovery_finding"].values()) else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
