#!/usr/bin/env bash
# Self-check for perch's name-resolution + suggestion logic.
# Run: bash test-perch.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export PERCH_CONFIG="$TMP/projects.conf"
export PERCH_FAVORITES="$TMP/favorites"
mkdir -p "$TMP/example-mobile" "$TMP/example-web" "$TMP/shop-mobile"
cat > "$PERCH_CONFIG" <<EOF
example-metro|8092|$TMP/example-mobile|yarn start
example-web|3211|$TMP/example-web|npm run dev
shop-metro|8082|$TMP/shop-mobile|yarn start
EOF

# shellcheck source=/dev/null
source "$HERE/perch"
set +e   # perch enables `set -e`; turn it off so failed assertions don't abort

fail=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1 — want '$3', got '$2'"; fail=1; fi; }

check "exact name passes through"      "$(resolve_project example-metro)"                 "example-metro"
check "folder name -> registered name" "$(resolve_project example-mobile)"                "example-metro"
check "unknown resolves to nothing"    "$(resolve_project nope 2>/dev/null || echo NONE)" "NONE"
check "closest fixes a command typo"   "$(closest palce | head -1)"                       "place"
check "closest fixes a project typo"   "$(closest example-wbe | head -1)"                 "example-web"

[ "$fail" = "0" ] && { echo "ALL PASS"; exit 0; } || { echo "SOME FAILED"; exit 1; }
