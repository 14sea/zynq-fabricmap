#!/usr/bin/env bash
# Build the B4Q host driver (make host) and record the compiler's resolved path, version and command in build/b4q_firmware/build.json.
set -euo pipefail
R=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${1:-$R/build/b4q_firmware}
CC=${CC:-cc}
CCPATH=$(command -v "$CC") || { echo "no host C compiler ($CC)" >&2; exit 2; }
make -C "$R/firmware/b4q" BUILD="$OUT" CC="$CCPATH" host twin >/dev/null
python3 - "$OUT/build.json" "$CCPATH" "$("$CCPATH" --version | head -n 1)" <<'PY'
import json, sys, hashlib, pathlib
out, path, version = sys.argv[1:]
d = pathlib.Path(out).parent
json.dump({"compiler": path, "version": version, "flags": "-std=c99 -O2 -Wall -Wextra -Werror -pedantic -Wshadow -Wstrict-prototypes -Wmissing-prototypes -Wconversion",
           "binaries": {b: hashlib.sha256((d / b).read_bytes()).hexdigest() for b in ("b4q_host", "b4q_derive_twin")}}, open(out, "w"), indent=1)
PY
echo "$OUT/b4q_host"
