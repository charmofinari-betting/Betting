#!/bin/bash
# SessionStart hook. Cloud sessions only: build the Python venv where the skills expect it
# (.venv/Scripts/python, the Windows layout, linked to bin/ on Linux).
[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/..}" || exit 1
if [ ! -x .venv/Scripts/python ]; then
  python3 -m venv .venv && ln -sfn bin .venv/Scripts
fi
.venv/Scripts/python -m pip install -q --disable-pip-version-check -r requirements.txt >&2
[ -n "$GOOGLE_SA_JSON" ] || echo "GOOGLE_SA_JSON is not set in this cloud environment: Sheets and Drive will not work." >&2
exit 0
