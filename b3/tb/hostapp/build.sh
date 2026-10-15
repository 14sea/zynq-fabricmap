#!/usr/bin/env bash
# Build the B3 host application harness: the REAL b3/firmware/b3_app.c, compiled with the image's own compile
# branch (-DB3_EMIT_SHA, as b3/firmware/bsp/build.sh) against hostbsp/ stubs and the system C compiler.
# Writes the binary and build.json (the compiler's resolved path, its version line and the exact command) to
# build/hostapp_b3/ (or $1). A missing compiler is a failure: nothing here is skipped.
set -euo pipefail
R=$(cd "$(dirname "$0")/../../.." && pwd)
OUT=${1:-$R/build/hostapp_b3}
CC=${CC:-cc}
CCPATH=$(command -v "$CC") || { echo "no host C compiler ($CC)" >&2; exit 2; }
FW="$R/b3/firmware"
H="$R/b3/tb/hostapp"
mkdir -p "$OUT"
CMD=("$CCPATH" -std=gnu11 -O1 -g -Wall -Wno-unused-function -DB3_EMIT_SHA -I"$FW" -I"$H/hostbsp"
     "$H/hostapp.c" "$FW/p3_derive.c" "$FW/b2_search.c" "$FW/b3_orch.c" "$FW/b3_record.c"
     "$FW/b3_online_view.c" "$FW/b3_carto.c" "$FW/b3_wire.c" "$FW/p3_rectx.c" "$FW/p3_pull.c"
     -o "$OUT/hostapp")
"${CMD[@]}"
python3 - "$OUT/build.json" "$CCPATH" "$("$CCPATH" --version | head -n 1)" "${CMD[@]}" <<'PY'
import json, sys
out, path, version, *cmd = sys.argv[1:]
json.dump({"compiler": path, "version": version, "command": cmd}, open(out, "w"), indent=1)
PY
echo "$OUT/hostapp"
