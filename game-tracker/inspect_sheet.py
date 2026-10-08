"""Read-only look at a Google Sheet: tabs, sizes, headers and sample rows.

Usage: python inspect_sheet.py <sheet_key> [rows]
Uses a read-only scope, so it cannot write anything.
"""
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SECRETS = Path(__file__).resolve().parent.parent / "secrets"
READONLY = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
READWRITE = ["https://www.googleapis.com/auth/spreadsheets"]


def client(scopes=READONLY):
    keys = sorted(SECRETS.glob("*.json"))
    if len(keys) != 1:
        sys.exit(f"expected one key file in {SECRETS}, found {len(keys)}")
    return gspread.authorize(Credentials.from_service_account_file(keys[0], scopes=scopes))


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
