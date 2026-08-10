# One-off Git LFS remote probe — 2026-08-10

The question this answered, and nothing wider: **does the remote accept LFS objects for
this repository, and does a fresh clone materialise them back to the exact bytes?**
Until it was answered, §2c's ruling had a branch nobody could take — "if remote LFS is
unavailable, stop and hand back to the consumer".

Authorised on the condition it ran on a **throwaway remote branch and never as a
commit/revert on `main`**. `main` was `cfe38a3` before and after; the branch is deleted.

`transcript.txt` is the run, unedited.

## What was pushed

| | |
|---|---|
| branch | `probe/lfs-2026-08-10` (deleted from the remote at step 11) |
| probe commit | `37b13933623bad0784fb846f9bcd9fc1f6a99352` |
| payload | `staging/probe/specimens/PROBE_base/spec.bit`, **2240 bytes** |
| payload sha256 | `a7f48b896fea9fb220170b898625ab6c58eea9d444b8b05073206d70de7b281d` |
| attribute rule | `staging/**/*.bit filter=lfs diff=lfs merge=lfs -text` (probe branch only) |

The payload is text that says what it is; it is deliberately **not** a bitstream, and no
committed specimen was involved.

## What HEAD held for it

```
version https://git-lfs.github.com/spec/v1
oid sha256:a7f48b896fea9fb220170b898625ab6c58eea9d444b8b05073206d70de7b281d
size 2240
```

blob `0f7f498cd7fac4928c2e13e3f40c862a5db85533`, 129 bytes — so **the pointer oid is the
payload sha256**, which is the equality `lfs_pointer_problems()` requires. That gate
returned `[]` on the tree, from the real HEAD blob.

## Upload

```
Uploading LFS objects: 100% (1/1), 2.2 KB | 0 B/s, done.
 * [new branch]      probe/lfs-2026-08-10 -> probe/lfs-2026-08-10
```

**Remote LFS is available for this repository.** That is the fact the LFS half of the
staging work was blocked on, and the ruling's "stop and hand back" branch is not taken.

## Fresh clone, before and after materialisation

Cloned from the remote over SSH with `GIT_LFS_SKIP_SMUDGE=1` — the pointer-only state a
clone that never fetched the objects would be in.

| | before `git lfs pull` | after |
|---|---|---|
| working file size | 129 bytes | 2240 bytes |
| working bytes sha256 | `212d4f9d…` (the pointer text) | `a7f48b89…` |
| equals the pin? | **no** | **yes** |
| `git ls-tree HEAD` | path present | path present |
| `git diff HEAD` | **clean** | clean |
| pointer gate | `[]` | `[]` |
| publication check | — | `[]` |

**This is the empirical form of the correction to §2b.** In the pointer-only tree the path
is in HEAD, `git diff HEAD` is *clean*, and the pointer gate passes — because all three
are true statements about what HEAD holds. The tree still does not have the bitstream, and
the only check that says so is **the working bytes against the manifest pin**. Anything
that read the diff as proof of materialisation would have measured a 129-byte pointer.

## Cleanup

Remote branch deleted (`- [deleted] probe/lfs-2026-08-10`), local branch deleted, temp
clone removed. Afterwards: `origin` has only `refs/heads/main` at `cfe38a3`, the worktree
is clean, and **the repository root has no `staging/` and no root `.gitattributes`** — the
probe's attribute rule lived only on the deleted branch and the real one still has to land
properly.

The root wording is deliberate: this directory carries its own scoped `.gitattributes`,
which turns off whitespace checking for `transcript.txt` alone. That file is the probe's
output captured verbatim, and six lines carry trailing whitespace that git and the LFS
server produced; stripping it would make this a transcription rather than a record, and
the claim above that the transcript is unedited has to stay true. The scoped rule sets no
filter and has nothing to do with LFS — it is the same convention the routing-probe
evidence directories already use.

**The one accepted persistent side effect** is the 2.2 KB LFS object, which stays in the
remote store: deleting a branch does not delete the objects it referenced. That was
authorised in advance.

## What this does NOT establish

* not a `.gitattributes` for this repository — the probe's rule went with its branch;
* not the fresh-clone materialisation **acceptance** for the real set: that is 184
  artifacts, 365.7 MiB, and re-hashing all of them plus running the verifier;
* nothing about staging or measurement, both still unauthorised.
