#!/usr/bin/env bash
# List the licence of every installed Python package and flag anything that is
# not a well-known free/open-source licence. Exit code 1 if something needs review.
#
# Usage: bash scripts/check_licences.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"
# Use the project's virtual environment when it exists (CI installs packages
# into the runner's Python instead).
if [[ -f "$SF_ROOT/.venv/bin/activate" ]]; then
    activate_venv
fi

python - <<'PY'
import sys
from importlib.metadata import distributions

# Permissive and weak-copyleft licences that are free to use in this project.
ALLOWED = ("MIT", "BSD", "Apache", "PSF", "Python Software Foundation", "ISC",
           "LGPL", "MPL", "Mozilla Public License", "Unlicense")
SELF = {"sentinelforge"}

def licence_of(dist):
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or []
                   if c.startswith("License ::")]
    if classifiers:
        return "; ".join(classifiers)
    text = (meta.get("License") or "").strip()
    return text.splitlines()[0][:60] if text else "UNKNOWN"

rows, review = {}, []
for dist in distributions():
    name = dist.metadata["Name"]
    if name.lower() in SELF:
        continue
    rows[name] = (dist.version, licence_of(dist))

width = max(len(n) for n in rows)
for name in sorted(rows, key=str.lower):
    version, licence = rows[name]
    flag = "" if any(token in licence for token in ALLOWED) else "  <-- review"
    if flag:
        review.append(name)
    print(f"{name:<{width}}  {version:<10}  {licence}{flag}")

print()
if review:
    print(f"[ warn ] {len(review)} package(s) need a manual licence review: {', '.join(review)}")
    sys.exit(1)
print(f"[  ok  ] all {len(rows)} packages use free/open-source licences")
PY
