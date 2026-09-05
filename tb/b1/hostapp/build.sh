#!/usr/bin/env bash
# Build the host application harness: the real firmware/b1/b1_app.c against hostbsp/ stubs.
set -euo pipefail
R=$(cd "$(dirname "$0")/../../.." && pwd)
OUT=${1:-$R/build/hostapp}
mkdir -p "$OUT"
cc -std=gnu11 -O1 -g -Wall -Wno-unused-function -I"$R/firmware/b1" -I"$R/tb/b1/hostapp/hostbsp" \
   "$R/tb/b1/hostapp/hostapp.c" "$R/firmware/b1/p3_derive.c" "$R/firmware/b1/b1_carto.c" "$R/firmware/b1/b1_orch.c" \
   "$R/firmware/b1/b1_wire.c" "$R/firmware/b1/p3_rectx.c" "$R/firmware/b1/p3_pull.c" -o "$OUT/hostapp"
echo "$OUT/hostapp"
