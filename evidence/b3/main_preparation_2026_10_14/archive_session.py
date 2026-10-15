#!/usr/bin/env python3
"""Archive ONE finished B3 session's raw runner directory in form (c) (the owner's archival decision of
2026-09-17 for B2, ruled again for B3 on 2026-10-14): the five large exports go into one deterministic
`exports.tar.zst`, the eleven small human-readable files stay ordinary, `archive.json` lists every file by
size and sha256 together with the boundary record and the re-judge script, and the complete original
directory is kept read-only outside the repository with a hash list.

    python3 -B evidence/b3/main_preparation_2026_10_14/archive_session.py \
        --raw <the runner's --out directory> --out evidence/b3/b3_17A6_<date>-NN \
        --boundary evidence/b3/principal_boundary_<date>-NN.json [--backup-root /home/test/fabricmap_backups | --no-backup]

Run from the repository root. Refuses by name unless the raw directory holds EXACTLY the sixteen files the runner
writes, its export seal holds, its finalisation record names a B3 / B3Q session, and --out does not exist. The raw
directory is never modified. Afterwards run restore_rejudge.py on --out (the archive is not evidence of a verdict
until the fresh restore re-judges equal to adjudication.json).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import restore_rejudge as rr  # noqa: E402  (the constants and the repo root)

ROOT = rr.ROOT
sys.path.insert(0, str(ROOT / "host"))
import b1_adjudicate as b1adj  # noqa: E402

TOOL = "archive_session.py/1.0.2 (b3 lifecycle 2, main preparation 2026-10-14; follow-ups to the owner's reviews of 0850e6b and 0a86d00)"
TAR = ("tar", "--format=posix", "--sort=name", "--owner=0", "--group=0", "--numeric-owner",
       "--pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime")


class Refusal(Exception):
    pass


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def entry(p: Path) -> dict:
    return {"name": p.name, "bytes": p.stat().st_size, "sha256": sha(p)}


def check_raw(raw: Path) -> dict:
    if not raw.is_dir():
        raise Refusal(f"{raw} is not a directory")
    present = sorted(p.name for p in raw.iterdir())
    if present != list(rr.SESSION_FILES):
        raise Refusal(f"{raw} does not hold exactly the runner's sixteen files: extra {sorted(set(present) - set(rr.SESSION_FILES))}, "
                      f"missing {sorted(set(rr.SESSION_FILES) - set(present))}")
    try:
        b1adj.check_exports(raw)
    except b1adj.Refusal as exc:
        raise Refusal(f"evidence seal: {exc}") from None
    try:
        record = json.loads((raw / "runner_session.json").read_text())
    except ValueError as exc:
        raise Refusal(f"runner_session.json is not JSON: {exc}") from None
    if not isinstance(record, dict) or record.get("session") not in ("B3", "B3Q"):
        raise Refusal("runner_session.json does not name a B3 / B3Q session")
    return record


def build_tar(raw: Path, dst: Path, mtime_epoch: int) -> None:
    cmd = " ".join(f'"{c}"' for c in TAR) + f' --mtime="@{mtime_epoch}" -C "{raw}" -cf - ' + " ".join(f'"{m}"' for m in rr.MEMBERS) + \
          f' | zstd -19 -T0 -q -o "{dst}"'
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    if r.returncode != 0 or not dst.is_file():
        raise Refusal(f"building {dst.name} failed: {r.stderr.strip()[:300]}")


def backup(raw: Path, backup_root: Path, name: str) -> dict:
    backup_root = Path(backup_root).resolve()        # the hash list is checked from inside the backup: its path must be absolute (the owner's P2 on 0a86d00)
    dst = backup_root / name
    if dst.exists():
        raise Refusal(f"the backup {dst} already exists")
    backup_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(raw, dst)
    lines = []
    for p in sorted(dst.iterdir()):
        lines.append(f"{sha(p)}  {p.name}\n")
        p.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    sums = backup_root / f"{name}.SHA256SUMS"
    sums.write_text("".join(lines))
    r = subprocess.run(["sha256sum", "-c", "--quiet", str(sums)], cwd=dst, capture_output=True, text=True)   # the list lives beside the backup, not in it
    if r.returncode != 0:
        raise Refusal(f"sha256sum -c failed on the backup: {(r.stderr or r.stdout).strip()[:200]}")
    if len(lines) != len(rr.SESSION_FILES):
        raise Refusal(f"the backup holds {len(lines)} files, not the session's {len(rr.SESSION_FILES)}")
    dst.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    return {"path": str(dst), "hash_list": str(sums), "files": len(lines),
            "state": "the complete original directory: exactly the 16 original files, read-only; the hash list covers all 16 and sha256sum -c passed at archival"}


def archive(raw: Path, out: Path, boundary: Path, backup_root: Path | None, rejudge_script: Path, root: Path = ROOT) -> dict:
    raw, out = Path(raw).resolve(), Path(out).resolve()
    if out.exists():
        raise Refusal(f"--out {out} already exists (no clobber)")
    record = check_raw(raw)
    if not boundary.is_file():
        raise Refusal(f"the boundary record {boundary} is absent")
    try:
        bdoc = json.loads(boundary.read_text())
    except ValueError as exc:
        raise Refusal(f"the boundary record is not JSON: {exc}") from None
    if bdoc.get("schema") != "principal_boundary" or bdoc.get("all_passed") is not True:
        raise Refusal("the boundary record is not a passed principal_boundary")
    if not rejudge_script.is_file():
        raise Refusal(f"the re-judge script {rejudge_script} is absent")
    at = record.get("at")
    try:
        mtime = int(time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone)
    except (TypeError, ValueError):
        raise Refusal(f"runner_session.json's at {at!r} is not a UTC timestamp") from None
    out.mkdir(parents=True)
    try:
        tar = out / "exports.tar.zst"
        build_tar(raw, tar, mtime)
        for name in rr.ORDINARY:
            shutil.copyfile(raw / name, out / name)
        shutil.copyfile(rejudge_script, out / "restore_rejudge.py")
        (out / "restore_rejudge.py").chmod(0o755)
        bk = backup(raw, backup_root, out.name) if backup_root is not None else {"state": "no external backup was made (--no-backup)"}
        doc = {
            "schema": rr.ARCHIVE_SCHEMA, "schema_version": "1.0.0", "tool": TOOL,
            "session_dir": os.path.relpath(out, root), "session": record["session"], "profile_stage": record.get("profile_stage"),
            "outcome_at_archival": record.get("outcome"), "cause_at_archival": record.get("cause"),
            "why": "The five large exports are stored as one deterministic compressed archive instead of ordinary Git blobs; the eleven "
                   "small, human-readable files stay as ordinary files (form (c), the owner's archival ruling of 2026-10-14 for B3 main sessions).",
            "archive": {"path": "exports.tar.zst", "bytes": tar.stat().st_size, "sha256": sha(tar),
                        "compression": "tar (GNU tar, --format=posix, --sort=name, --owner=0 --group=0 --numeric-owner, one fixed --mtime for every "
                                       "member = runner_session.json's at, pax headers without atime/ctime) | zstd -19 -T0",
                        "member_mtime_epoch": mtime, "members": [entry(raw / m) for m in rr.MEMBERS]},
            "ordinary_files": [entry(raw / m) for m in rr.ORDINARY],
            "boundary": {"path": os.path.relpath(boundary.resolve(), root), "bytes": boundary.stat().st_size, "sha256": sha(boundary),
                         "runner_user": bdoc.get("runner_user"), "at": bdoc.get("at")},
            "restore_rejudge": {"path": "restore_rejudge.py", "sha256": sha(out / "restore_rejudge.py"),
                                "preparation_copy": os.path.relpath(rejudge_script.resolve(), root), "preparation_sha256": sha(rejudge_script),
                                "equals_preparation_copy": sha(out / "restore_rejudge.py") == sha(rejudge_script)},
            "exports_json_seal_note": "exports.json (a sealed member of the session record) names the five exports by size and sha256; those digests "
                                      "are the ones listed under archive.members, so the seal is verifiable after restore.",
            "restore": [f"Fresh restore and re-judge, executable: python3 -B {os.path.relpath(out, root)}/restore_rejudge.py (from the repository root).",
                        "What it does, in order: an EMPTY temporary directory; the five members extracted; the eleven ordinary files copied; exactly "
                        "sixteen files, each checked by size and sha256 against this document; the export seal; the archived manifest verified with "
                        "its pins; the pinned plan and prediction verified byte-for-byte before being read; the session plan REBUILT from the "
                        "authoritative inputs (the archived manifest, the pinned documents, the archived ruling's slice and disposition, the bound "
                        "instrument's arithmetic) and compared to summary.json's l6; the production judge_session, equal to adjudication.json key "
                        "for key; runner_session.json against the rebuilt plan and that verdict; the boundary record."],
            "external_backup": bk,
            "files_in_this_directory_not_part_of_the_session_record": ["exports.tar.zst", "archive.json", "README.md", "restore_rejudge.py"],
            "archived_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "These hashes are an integrity anchor for the archived bytes; they do not prove the session's verdict — the verdict is re-derived "
                    "by the production judge from the restored files.",
        }
        (out / "archive.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        return doc
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--boundary", type=Path, required=True)
    ap.add_argument("--backup-root", type=Path, default=Path("/home/test/fabricmap_backups"))
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--restore-rejudge", type=Path, default=HERE / "restore_rejudge.py")
    a = ap.parse_args(argv)
    try:
        doc = archive(a.raw, a.out, a.boundary, None if a.no_backup else a.backup_root, a.restore_rejudge)
    except Refusal as exc:
        print(json.dumps({"tool": TOOL, "verdict": "REFUSE", "refusal": str(exc)}))
        return 2
    print(json.dumps({"tool": TOOL, "verdict": "ARCHIVED", "session_dir": doc["session_dir"], "archive_sha256": doc["archive"]["sha256"],
                      "archive_bytes": doc["archive"]["bytes"], "external_backup": doc["external_backup"].get("path"),
                      "next": f"python3 -B {doc['session_dir']}/restore_rejudge.py"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
