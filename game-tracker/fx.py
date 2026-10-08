"""Fetch ₱ rates for USDT and TRX (CoinGecko public price feed) into the private book's FX tab.

Usage: python fx.py [--apply]
"""
import sys
from datetime import datetime

import requests

from fixtures import PHT
from setup_book import BOOK_KEY

COINS = {"USDT": "tether", "TRX": "tron"}
URL = "https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=php"


def rates():
    data = requests.get(URL.format(ids=",".join(COINS.values())), timeout=20).json()
    return {cur: data[cid]["php"] for cur, cid in COINS.items()}


def main():
    apply = "--apply" in sys.argv
    r = rates()
    stamp = datetime.now(PHT).strftime("%Y-%m-%d %H:%M PHT (CoinGecko)")
    from inspect_sheet import READONLY, READWRITE, client
    ws = client(READWRITE if apply else READONLY).open_by_key(BOOK_KEY).worksheet("FX")
    rows = ws.get_all_values()
    print(f"FX {'APPLY' if apply else 'dry run'}:")
    updates = []
    for i, row in enumerate(rows[1:], start=2):
        cur = row[0]
        if cur in r:
            old = row[1] if len(row) > 1 else ""
            print(f"  {cur}: {old or '(empty)'} -> {r[cur]} ₱")
            updates.append({"range": f"B{i}:C{i}", "values": [[r[cur], stamp]]})
    if apply and updates:
        ws.batch_update(updates, value_input_option="RAW")
        print("  written")


if __name__ == "__main__":
    main()
