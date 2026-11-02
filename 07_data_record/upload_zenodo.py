"""Upload the staged files of the data record to a Zenodo draft (it never publishes).

Creates a new draft deposition (or uses --deposition <id>, e.g. a new version created in the web page),
uploads every file of the upload folder written by pack_record.py (README.md, md5sums.txt and one zip per
folder of the record) through the deposition's file bucket, and sets the metadata from
zenodo_metadata.json. Review the draft on zenodo.org and publish it there. The files with ASO values
(zenodo_hold/) are never uploaded.

The personal access token (scope deposit:write) is read from the environment variable ZENODO_TOKEN;
never write it into a file of this repository.

Usage:
    export ZENODO_TOKEN=...          # in your shell, not in a script
    python 07_data_record/upload_zenodo.py [--deposition ID] [--sandbox] [--dry-run]
Environment: any Python 3 with requests (e.g. gpy-env). Network access needed (Savio compute nodes have it: sbatch_upload_zenodo.sh).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

UPLOAD = Path("/global/scratch/users/marcomaz/zenodo_upload")
META = Path(__file__).with_name("zenodo_metadata.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deposition", help="id of an existing draft (default: create a new one)")
    ap.add_argument("--sandbox", action="store_true", help="use sandbox.zenodo.org (tests)")
    ap.add_argument("--dry-run", action="store_true", help="list what would be uploaded")
    a = ap.parse_args()

    files = sorted(p for p in UPLOAD.iterdir() if p.is_file())
    print(f"{len(files)} files, {sum(p.stat().st_size for p in files) / 1e9:.2f} GB")
    if len(files) > 100:
        sys.exit("Zenodo allows at most 100 files per record")
    if a.dry_run:
        for p in files:
            print(f"  {p.stat().st_size / 1e6:9.1f} MB  {p.name}")
        return

    token = os.environ.get("ZENODO_TOKEN")
    if not token:
        sys.exit("set ZENODO_TOKEN in the environment first")
    api = "https://sandbox.zenodo.org/api" if a.sandbox else "https://zenodo.org/api"
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token}"

    if a.deposition:
        r = s.get(f"{api}/deposit/depositions/{a.deposition}")
    else:
        r = s.post(f"{api}/deposit/depositions", json={})
    r.raise_for_status()
    dep = r.json()
    bucket = dep["links"]["bucket"]
    print(f"draft {dep['id']}: {dep['links']['html']}")

    present = {f["filename"]: f for f in dep.get("files", [])}
    for p in files:
        if p.name in present and int(present[p.name].get("filesize", -1)) == p.stat().st_size:
            print(f"  skip {p.name} (already uploaded)")
            continue
        with open(p, "rb") as fh:
            r = s.put(f"{bucket}/{p.name}", data=fh)
        r.raise_for_status()
        print(f"  uploaded {p.name} ({p.stat().st_size / 1e6:.1f} MB)", flush=True)

    meta = json.loads(META.read_text())
    if any("TODO" in json.dumps(v) for v in meta["metadata"].values()):
        print("zenodo_metadata.json still contains TODO fields: metadata not set; fill them in and run again")
        return
    r = s.put(f"{api}/deposit/depositions/{dep['id']}", json=meta)
    r.raise_for_status()
    print("metadata set. Review the draft and publish it on the web page.")


if __name__ == "__main__":
    main()
