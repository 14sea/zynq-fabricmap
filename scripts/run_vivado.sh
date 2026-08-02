#!/usr/bin/env bash
# Thin wrapper: Vivado is not on PATH on this host and lives in the user's home.
# Everything downstream depends on the version, so it is echoed into the log.
set -euo pipefail
: "${VIVADO_SETTINGS:=$HOME/Xilinx/2025.2/Vivado/settings64.sh}"
[ -f "$VIVADO_SETTINGS" ] || { echo "no Vivado settings at $VIVADO_SETTINGS" >&2; exit 1; }
# shellcheck disable=SC1090
source "$VIVADO_SETTINGS"
exec vivado "$@"
