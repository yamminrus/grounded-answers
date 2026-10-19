#!/usr/bin/env bash
# Every gate, in the order a failure is cheapest to understand.
# Nothing is committed unless this exits 0.
set -u
cd "$(dirname "$0")/.." || exit 2
PY=${PY:-python3}
fail=0
run () {
  printf '\n\033[1m== %s\033[0m\n' "$1"; shift
  if "$@"; then :; else fail=$((fail+1)); fi
}

# FIRST, ALWAYS. If this is red nothing else matters, because the repo is
# public and the ecosystem is not.
run "no ecosystem code" "$PY" tools/selftest_no_ecosystem_code.py

printf '\n'
if [ "$fail" -eq 0 ]; then printf '\033[32mALL GATES GREEN\033[0m\n'
else printf '\033[31m%d GATE(S) RED\033[0m\n' "$fail"; fi
exit "$fail"
