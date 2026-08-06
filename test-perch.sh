#!/usr/bin/env bash
# Self-check for perch's name-resolution + suggestion logic.
# Run: bash test-perch.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export PERCH_CONFIG="$TMP/projects.conf"
export PERCH_FAVORITES="$TMP/favorites"
mkdir -p "$TMP/jakstoc-mobile" "$TMP/jakstoc-web" "$TMP/Rentwize-Mobile-Client"
cat > "$PERCH_CONFIG" <<EOF
jakstoc-metro|8092|$TMP/jakstoc-mobile|yarn start
jakstoc-web|3211|$TMP/jakstoc-web|npm run dev
rentwize-metro|8082|$TMP/Rentwize-Mobile-Client|yarn start
EOF

# shellcheck source=/dev/null
source "$HERE/perch"
set +e   # perch enables `set -e`; turn it off so failed assertions don't abort

fail=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1 — want '$3', got '$2'"; fail=1; fi; }

check "exact name passes through"      "$(resolve_project jakstoc-metro)"                 "jakstoc-metro"
check "folder name -> registered name" "$(resolve_project jakstoc-mobile)"                "jakstoc-metro"
check "unknown resolves to nothing"    "$(resolve_project nope 2>/dev/null || echo NONE)" "NONE"
check "closest fixes a command typo"   "$(closest palce | head -1)"                       "place"
check "closest fixes a project typo"   "$(closest jakstoc-wbe | head -1)"                 "jakstoc-web"

[ "$fail" = "0" ] && { echo "ALL PASS"; exit 0; } || { echo "SOME FAILED"; exit 1; }
