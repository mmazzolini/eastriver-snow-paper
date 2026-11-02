#!/bin/bash
# Copies the website data (without the reference_* check files) into the private data repository, by
# default /global/scratch/users/marcomaz/site_data_repo. Run on a compute node (about 240 MB).
set -euo pipefail
SRC=${WEB_DATA:-/global/scratch/users/marcomaz/web_data}
DST=${1:-/global/scratch/users/marcomaz/site_data_repo}
mkdir -p "$DST"
rsync -a --delete --exclude .git --exclude 'reference_*' "$SRC/" "$DST/"
cp /global/home/users/marcomaz/paper_repo/web/site_data_README.md "$DST/README.md"
echo "data files in $DST: $(ls "$DST" | wc -l) files, $(du -sh --apparent-size "$DST" --exclude .git | cut -f1)"
