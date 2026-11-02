#!/bin/bash
# Copies the page (docs/) and the site template (web/site/: README, LICENSE, Pages workflow) into the
# site repository, by default ~/site_repo.
set -euo pipefail
REPO=/global/home/users/marcomaz/paper_repo
DST=${1:-/global/home/users/marcomaz/site_repo}
mkdir -p "$DST/js/vendor" "$DST/.github/workflows"
cp "$REPO/docs/index.html" "$REPO/docs/config.js" "$DST/"
cp "$REPO/docs/js/app.js" "$REPO/docs/js/core.js" "$DST/js/"
cp "$REPO/docs/js/vendor/d3.v7.9.0.min.js" "$DST/js/vendor/"
cp "$REPO/web/site/README.md" "$REPO/web/site/LICENSE" "$DST/"
cp "$REPO/web/site/.github/workflows/pages.yml" "$DST/.github/workflows/"
echo "site files in $DST"
