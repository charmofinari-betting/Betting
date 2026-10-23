"""Read-only look at a Google Sheet: tabs, sizes, headers and sample rows.

Usage: python inspect_sheet.py <sheet_key> [rows]
Uses a read-only scope, so it cannot write anything.
"""
import base64
import json
import os
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SECRETS = Path(__file__).resolve().parent.parent / "secrets"
KEY_ENV = "GOOGLE_SA_JSON"  # cloud sessions: the key file's JSON, raw or base64
READONLY = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
READWRITE = ["https://www.googleapis.com/auth/spreadsheets"]


def key_info(value):
    """The service-account key from the env var's value: raw JSON, or base64 of it."""
    value = value.strip()
    if not value.startswith("{"):
        value = base64.b64decode(value).decode("utf-8")
    return json.loads(value)


def credentials(scopes):
    """Google credentials: GOOGLE_SA_JSON when set (cloud), else the one key file in secrets/ (laptop)."""
    if os.environ.get(KEY_ENV):
        return Credentials.from_service_account_info(key_info(os.environ[KEY_ENV]), scopes=scopes)
    keys = sorted(SECRETS.glob("*.json"))
    if len(keys) != 1:
        sys.exit(f"expected one key file in {SECRETS} (or {KEY_ENV} set), found {len(keys)}")
    return Credentials.from_service_account_file(keys[0], scopes=scopes)


def client(scopes=READONLY):
    # BackOffHTTPClient retries Google's 429 "quota exceeded" (60 reads/min) instead of crashing mid-run.
    return gspread.authorize(credentials(scopes), http_client=gspread.BackOffHTTPClient)


def main():
    key = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    sh = client().open_by_key(key)
    print(f"# {sh.title}")
    for ws in sh.worksheets():
        values = ws.get_all_values()
        filled = [r for r in values if any(c.strip() for c in r)]
        print(f"\n## {ws.title}  (grid {ws.row_count}x{ws.col_count}, {len(filled)} non-empty rows)")
        for r in values[: n + 1]:
            print(" | ".join(c[:28] for c in r).rstrip(" |"))


if __name__ == "__main__":
    main()
