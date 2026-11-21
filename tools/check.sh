#!/usr/bin/env bash
# Fast checks: build every test household, run Home Assistant's config check on each, scan for leaks.
# Usage: tools/check.sh [path/to/hass]   (hass is optional; skipped if not found)
set -euo pipefail
cd "$(dirname "$0")/.."
HASS="${1:-$(command -v hass || true)}"
fail=0
for h in tests/households/*.yaml; do
  name=$(basename "$h" .yaml)
  rm -rf "out/check_$name"
  python3 build.py -c "$h" -o "out/check_$name" >/dev/null
  if [ -n "$HASS" ]; then
    if "$HASS" --script check_config -c "out/check_$name" 2>&1 | grep -qiE "Incorrect config|Invalid config|^ERROR|duplicate key"; then
      echo "FAIL  $name (run: $HASS --script check_config -c out/check_$name)"; fail=1
    else
      echo "OK    $name"
    fi
  else
    echo "BUILT $name (hass not found: config check skipped)"
  fi
done
python3 tools/leakscan.py || fail=1
for f in build.py kit/dashboards.py tools/*.py; do python3 -m py_compile "$f"; done
exit $fail
