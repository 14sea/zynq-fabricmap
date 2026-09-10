#!/usr/bin/env bash
# Build the host application harness: the real firmware/b2/b2_app.c against hostbsp/ stubs.
set -euo pipefail
R=$(cd "$(dirname "$0")/../../.." && pwd)
OUT=${1:-$R/build/hostapp_b2}
mkdir -p "$OUT"
cc -std=gnu11 -O1 -g -Wall -Wno-unused-function -I"$R/firmware/b2" -I"$R/tb/b2/hostapp/hostbsp" \
   "$R/tb/b2/hostapp/hostapp.c" "$R/firmware/b2/p3_derive.c" "$R/firmware/b2/b2_search.c" "$R/firmware/b2/b2_orch.c" \
   "$R/firmware/b2/b2_wire.c" "$R/firmware/b2/p3_rectx.c" "$R/firmware/b2/p3_pull.c" -o "$OUT/hostapp"
echo "$OUT/hostapp"
