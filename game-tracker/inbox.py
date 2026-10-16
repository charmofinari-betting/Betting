"""Drive inbox: screenshots Paolo shares from his phone into `Betting Inbox/Tips` and `/Slips`.

Usage:
  python inbox.py                      list new files (read-only)
  python inbox.py pull                 download new files to out/inbox/ (read-only on Drive)
  python inbox.py done <id>... [--apply]   move logged files to `Done` (dry run unless --apply)
  python inbox.py results             copy result files saved by the Drive job into data/api/

"New" means still sitting in Tips or Slips. A file leaves the inbox only when it is moved to
Done after logging, so nothing is logged twice and the originals are kept.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

from inspect_sheet import SECRETS

FOLDERS = {
    "Tips": "1Esbx1se8FqlXlg87hq8Hd-ZgaP_ejOCC",
    "Slips": "1vR9k_gAW1yXpSA_u2Hvp1U9k7FRMyxW7",
}
DONE = "1nO48uECyB8uNbv_VgRvQ-zbWlcMeDNPQ"
RESULTS = "1ikv3MHSqtN9busGPGpNjt7OIxqMfjnO8"  # filled by apps-script/results_fetch.gs
CACHE = Path(__file__).resolve().parent / "data" / "api"
OUT = Path(__file__).resolve().parent / "out" / "inbox"
API = "https://www.googleapis.com/drive/v3/files"
READONLY = ["https://www.googleapis.com/auth/drive.readonly"]
READWRITE = ["https://www.googleapis.com/auth/drive"]
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic"}


def session(scopes=READONLY):
    keys = sorted(SECRETS.glob("*.json"))
    if len(keys) != 1:
        sys.exit(f"expected one key file in {SECRETS}, found {len(keys)}")
    return AuthorizedSession(Credentials.from_service_account_file(keys[0], scopes=scopes))


def list_new(s):
    """Files waiting in Tips and Slips, oldest first, each tagged with its folder."""
    out = []
    for folder, fid in FOLDERS.items():
        r = s.get(API, params={"q": f"'{fid}' in parents and trashed=false",
                               "fields": "files(id,name,mimeType,createdTime)",
                               "orderBy": "createdTime", "pageSize": 1000})
        r.raise_for_status()
        out += [dict(f, folder=folder) for f in r.json()["files"]]
    return sorted(out, key=lambda f: f["createdTime"])


def local_name(f):
    """out/inbox/<Folder>/<created>_<id><ext>: sortable by time, unique by Drive id."""
    stamp = f["createdTime"][:19].replace(":", "").replace("-", "").replace("T", "-")
    ext = EXT.get(f["mimeType"]) or Path(f["name"]).suffix or ".bin"
    return Path(f["folder"]) / f"{stamp}_{f['id']}{ext}"


def check_done(new, ids):
    """Split ids into movable files and ids that are not waiting in the inbox."""
    by_id = {f["id"]: f for f in new}
    return [by_id[i] for i in ids if i in by_id], [i for i in ids if i not in by_id]


def plan_pull(files, cache=CACHE):
    """Drive _results files -> [(file, local path)] that are missing or older locally."""
    todo = []
    for f in files:
        m = re.fullmatch(r"(football|basketball)_(\d{4}-\d{2}-\d{2})\.json", f["name"])
        if not m:
            continue
        path = cache / m[1] / f"{m[2]}.json"
        drive_ts = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00")).timestamp()
        if not path.exists() or path.stat().st_mtime < drive_ts - 1:
            todo.append((f, path, drive_ts))
    return todo


def pull_results(s=None, cache=CACHE):
    """Copy new or updated result files from Drive into the local API cache.

    The local file keeps Drive's modified time, so fixtures.fetch still knows how fresh it is.
    Returns (pulled names, status line from the Apps Script's last run).
    """
    s = s or session()
    r = s.get(API, params={"q": f"'{RESULTS}' in parents and trashed=false",
                           "fields": "files(id,name,modifiedTime)", "pageSize": 1000})
    r.raise_for_status()
    files = r.json()["files"]
    pulled = []
    for f, path, ts in plan_pull(files, cache):
        body = s.get(f"{API}/{f['id']}", params={"alt": "media"})
        body.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body.content)
        os.utime(path, (ts, ts))
        pulled.append(f["name"])
    status = "no run from the Drive job yet"
    st = next((f for f in files if f["name"] == "_status.json"), None)
    if st:
        log = s.get(f"{API}/{st['id']}", params={"alt": "media"}).json()
        status = f"last Drive job run {log['run'][:16].replace('T', ' ')}"
        if log.get("failed"):
            status += f", FAILED: {'; '.join(log['failed'])}"
    return pulled, status


def show(files):
    if not files:
        print("Inbox empty.")
    for f in files:
        print(f"{f['folder']:<6} {f['createdTime'][:16].replace('T', ' ')} UTC  {f['id']}  {f['name']}")


def main(argv):
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        show(list_new(session()))
    elif cmd == "pull":
        s = session()
        files = list_new(s)
        show(files)
        for f in files:
            path = OUT / local_name(f)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                r = s.get(f"{API}/{f['id']}", params={"alt": "media"})
                r.raise_for_status()
                path.write_bytes(r.content)
            print(f"  -> {path}")
    elif cmd == "results":
        pulled, status = pull_results()
        print(f"{len(pulled)} file(s) pulled: {', '.join(pulled) or '-'}")
        print(status)
    elif cmd == "done":
        apply = "--apply" in argv
        ids = [a for a in argv[1:] if a != "--apply"]
        s = session(READWRITE if apply else READONLY)
        move, unknown = check_done(list_new(s), ids)
        for i in unknown:
            print(f"SKIP {i}: not waiting in Tips or Slips")
        for f in move:
            print(f"{'MOVED' if apply else 'would move'} {f['folder']}/{f['name']} -> Done")
            if apply:
                r = s.patch(f"{API}/{f['id']}", params={
                    "addParents": DONE, "removeParents": FOLDERS[f["folder"]]})
                r.raise_for_status()
        if move and not apply:
            print("Dry run. Re-run with --apply to move.")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
